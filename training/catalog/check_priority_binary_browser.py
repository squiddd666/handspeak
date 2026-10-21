"""Verify browser JavaScript parity and inference time for exported HELLO model."""
import json
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_priority_binary import BinaryTemporal
import train_expansion_batch as batch

REPO = Path(__file__).resolve().parents[2]
ROOT = Path("/opt/handspeak-training/priority-binary-hello-popsign-v2")


def main():
    model = json.loads((REPO / "models/hello-binary.json").read_text())
    selected = json.loads((ROOT / "validation.json").read_text())["selected"]
    rows, seen = [], set()
    for source in (Path("/opt/handspeak-training/accuracy-v4/test-features.json"),
                   Path("/opt/handspeak-training/vocabulary-v8/test-features.json")):
        for row in json.loads(source.read_text()):
            if row["sha256"] not in seen and row.get("sequence") is not None:
                seen.add(row["sha256"])
                rows.append(dict(row, body=[None] * len(row["rawFrames"])))
    network = BinaryTemporal(32)
    network.load_state_dict(torch.load(ROOT / "binary-private.pt", weights_only=True)["state"])
    network.eval()
    inputs = torch.tensor(np.stack([batch.trainer.encoding.features(row) for row in rows]))
    with torch.no_grad():
        expected = network(inputs).sigmoid().numpy()
    payload = [{"rawFrames": row["rawFrames"], "body": row["body"],
                "imageAspect": row["imageAspect"]} for row in rows]
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), lambda *args, **kwargs: Quiet(*args, directory=str(REPO), **kwargs))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(args=["--no-sandbox"])
            page = browser.new_page(); page.goto(f"http://127.0.0.1:{server.server_port}/")
            result = page.evaluate("""async ({rows,model})=>{
              const {helloBinaryScore}=await import('/hello-binary.js');
              const started=performance.now(),scores=rows.map(row=>helloBinaryScore(model,row));
              return {scores,elapsedMs:performance.now()-started};
            }""", {"rows": payload, "model": model})
            browser.close()
    finally:
        server.shutdown(); thread.join()
    actual = np.array(result["scores"])
    maximum = float(np.max(np.abs(actual - expected)))
    if maximum > 2e-5 or not np.array_equal(actual >= selected["threshold"], expected >= selected["threshold"]):
        raise ValueError(f"Browser parity failed: {maximum}")
    report = {"clips": len(rows), "maxScoreDifference": maximum,
              "decisionParity": True, "totalInferenceMs": result["elapsedMs"],
              "meanInferenceMs": result["elapsedMs"] / len(rows),
              "scope": "Headless Chromium JavaScript runtime over cached browser-compatible landmarks; excludes landmark detection.",
              "deployed": False}
    path = REPO / "reports/priority-six-hello-browser-parity.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
