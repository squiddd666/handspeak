"""Run frozen binary candidates against previously frozen regression features."""
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from train_priority_binary import BinaryTemporal
import train_expansion_batch as batch

BASE = Path("/opt/handspeak-training")
SOURCES = [BASE / "accuracy-v4/test-features.json", BASE / "vocabulary-v8/test-features.json"]
WORDS = ("HELLO", "HUNGRY", "HOME", "FISH")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    rows, seen = [], set()
    for source in SOURCES:
        for row in json.loads(source.read_text()):
            if row["sha256"] not in seen and row.get("sequence") is not None:
                seen.add(row["sha256"]); rows.append(row)
    inputs = torch.tensor(np.stack([batch.trainer.encoding.features(row) for row in rows]))
    results = []
    for word in WORDS:
        root = BASE / f"priority-binary-{word.lower()}-popsign-v2"
        selected = json.loads((root / "validation.json").read_text())["selected"]
        checkpoint = root / "binary-private.pt"
        if not selected["passesValidation"] or sha(checkpoint) != selected["sha256"]:
            raise ValueError(f"Ineligible or modified candidate: {word}")
        model = BinaryTemporal(32)
        model.load_state_dict(torch.load(checkpoint, weights_only=True)["state"])
        model.eval()
        with torch.no_grad():
            scores = model(inputs).sigmoid().numpy()
        outputs = scores >= selected["threshold"]
        positive = np.array([row["label"] == word for row in rows])
        results.append({
            "word": word, "correct": int(np.sum(outputs & positive)),
            "supportedTotal": int(np.sum(positive)),
            "negativeFalseAccepts": int(np.sum(outputs & ~positive)),
            "negativeTotal": int(np.sum(~positive)),
            "threshold": selected["threshold"], "checkpointSha256": selected["sha256"],
        })
    result = {
        "scope": "Previously frozen recorded-clip regression; fixed development thresholds; no regression tuning.",
        "sourceSha256": {str(path): sha(path) for path in SOURCES},
        "results": results, "deployed": False,
    }
    output = Path("/opt/handspeak/repository/reports/priority-six-popsign-binary-regression.json")
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
