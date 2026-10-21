"""Verify JavaScript parity and latency for one exported binary model."""
import argparse
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import torch

from train_priority_binary import BinaryTemporal
import train_expansion_batch as batch

REPO = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--source", action="append", type=Path, required=True)
    args = parser.parse_args()
    model = json.loads(args.model.read_text())
    selected = json.loads((args.experiment / "validation.json").read_text())["selected"]
    rows, seen = [], set()
    for source in args.source:
        for row in json.loads(source.read_text()):
            if row.get("sequence") is None or row.get("sha256") in seen:
                continue
            seen.add(row["sha256"])
            rows.append(dict(row, body=[None] * len(row["rawFrames"])))
    network = BinaryTemporal(32)
    network.load_state_dict(torch.load(args.experiment / "binary-private.pt",
                                       weights_only=True)["state"])
    network.eval()
    inputs = torch.tensor(np.stack([batch.trainer.encoding.features(row) for row in rows]))
    with torch.no_grad():
        expected = network(inputs).sigmoid().numpy()
    payload = [{"rawFrames": row["rawFrames"], "body": row["body"],
                "imageAspect": row["imageAspect"]} for row in rows]

    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0),
        lambda *a, **kw: Quiet(*a, directory=str(REPO), **kw))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(args=["--no-sandbox"])
            page = browser.new_page(); page.goto(f"http://127.0.0.1:{server.server_port}/")
            result = page.evaluate("""async ({rows,model})=>{
              const {binaryTemporalScore}=await import('/hello-binary.js');
              const start=performance.now(),scores=rows.map(row=>binaryTemporalScore(model,row));
              return {scores,elapsedMs:performance.now()-start};
            }""", {"rows": payload, "model": model})
            browser.close()
    finally:
        server.shutdown(); thread.join()
    actual = np.array(result["scores"])
    maximum = float(np.max(np.abs(actual - expected)))
    parity = maximum <= 2e-5 and np.array_equal(actual >= selected["threshold"],
                                                expected >= selected["threshold"])
    if not parity:
        raise ValueError(f"Browser parity failed: {maximum}")
    report = {"word": model["word"], "clips": len(rows),
              "maxScoreDifference": maximum, "decisionParity": True,
              "totalInferenceMs": result["elapsedMs"],
              "meanInferenceMs": result["elapsedMs"] / len(rows),
              "scope": "Headless Chromium over cached landmarks; excludes hand detection.",
              "deployed": False}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
