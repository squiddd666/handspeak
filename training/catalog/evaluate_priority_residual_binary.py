"""Frozen regression check for the six-word body-and-hands binary model."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

import body_tip_features
from train_priority_residual_binary import BinaryResidual

SOURCES = (
    Path("/opt/handspeak-training/accuracy-v4/test-features.json"),
    Path("/opt/handspeak-training/vocabulary-expansion-fresh-test/test-features.json"),
    Path("/opt/handspeak-training/daily-words/citizen-research/test-features.json"),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    validation = json.loads((args.experiment / "binary-residual-validation.json").read_text())
    checkpoint = args.experiment / "binary-residual-private.pt"
    if sha(checkpoint) != validation["checkpointSha256"]:
        raise ValueError("Frozen checkpoint changed")
    rows, seen = [], set()
    for source in SOURCES:
        for row in json.loads(source.read_text()):
            identity = row.get("sha256")
            if identity in seen or row.get("sequence") is None:
                continue
            if not row.get("body") or not any(value is not None for value in row["body"]):
                continue
            seen.add(identity); rows.append(row)
    saved = torch.load(checkpoint, weights_only=True)
    state, labels = saved["state"], saved["labels"]
    model = BinaryResidual(len(labels), state["mean"].reshape(-1), state["scale"].reshape(-1))
    model.load_state_dict(state); model.eval()
    values = torch.tensor(np.stack([body_tip_features.features(row) for row in rows]))
    with torch.no_grad():
        scores = model(values).sigmoid().numpy()
    results = {}
    for index, word in enumerate(labels):
        threshold = saved["selected"][word]["threshold"]
        output = scores[:, index] >= threshold
        positive = np.array([row["label"] == word for row in rows])
        results[word] = {"correct": int(np.sum(output & positive)),
                         "total": int(np.sum(positive)),
                         "negativeFalse": int(np.sum(output & ~positive)),
                         "negativeTotal": int(np.sum(~positive)),
                         "threshold": threshold,
                         "passes": (int(np.sum(output & positive)) >= int(np.sum(positive)) * .5
                                    and int(np.sum(output & ~positive)) == 0
                                    and int(np.sum(positive)) > 0)}
    result = {"scope": "Previously frozen, inspected clips; fixed development thresholds; no tuning.",
              "checkpointSha256": validation["checkpointSha256"],
              "sourceSha256": {str(path): sha(path) for path in SOURCES},
              "words": results, "passesRegressionGate": all(v["passes"] for v in results.values()),
              "deployed": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
