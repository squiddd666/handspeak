"""Evaluate frozen CAPSTONE-overlap candidates on untouched Citizen test signers."""
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

import body_tip_features
from train_priority_residual_binary import BinaryResidual

ROOT = Path("/opt/handspeak-training/capstone-nine-residual-binary-v1")
TEST = Path("/opt/handspeak-training/citizen-capstone-nine-test/test-features.json")
REGRESSION = (
    Path("/opt/handspeak-training/accuracy-v4/test-features.json"),
    Path("/opt/handspeak-training/vocabulary-expansion-fresh-test/test-features.json"),
    Path("/opt/handspeak-training/daily-words/citizen-research/test-features.json"),
)
OUTPUT = Path("/opt/handspeak/repository/reports/capstone-nine-20261021.json")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    validation = json.loads((ROOT / "binary-residual-validation.json").read_text())
    checkpoint = ROOT / "binary-residual-private.pt"
    if sha(checkpoint) != validation["checkpointSha256"]:
        raise ValueError("Frozen checkpoint changed")
    citizen = json.loads(TEST.read_text())
    rows, seen = [], set()
    for source in REGRESSION:
        for row in json.loads(source.read_text()):
            if row.get("sha256") in seen or row.get("sequence") is None:
                continue
            if not row.get("body") or not any(value is not None for value in row["body"]):
                continue
            seen.add(row["sha256"]); rows.append(row)
    rows.extend(row for row in citizen if row["sha256"] not in seen)
    saved = torch.load(checkpoint, weights_only=True)
    state, labels = saved["state"], saved["labels"]
    model = BinaryResidual(len(labels), state["mean"].reshape(-1), state["scale"].reshape(-1))
    model.load_state_dict(state); model.eval()
    inputs = torch.tensor(np.stack([body_tip_features.features(row) for row in rows]))
    with torch.no_grad():
        scores = model(inputs).sigmoid().numpy()
    results = {}
    for index, word in enumerate(labels):
        development = saved["selected"][word]
        accepted = scores[:, index] >= development["threshold"]
        positive = np.array([row["label"] == word for row in rows])
        correct = int(np.sum(accepted & positive))
        total = int(np.sum(positive))
        false = int(np.sum(accepted & ~positive))
        results[word] = {"developmentPassed": development["passesValidation"],
                         "correct": correct, "total": total,
                         "negativeFalse": false,
                         "negativeTotal": int(np.sum(~positive)),
                         "passesTestGate": (development["passesValidation"] and
                                            correct >= total * .5 and false == 0)}
    result = {"scope": ("Frozen model and development thresholds evaluated on untouched ASL Citizen "
                        "test signers plus previously frozen cross-source negatives. No tuning."),
              "checkpointSha256": validation["checkpointSha256"],
              "testSourceSha256": sha(TEST),
              "regressionSourceSha256": {str(path): sha(path) for path in REGRESSION},
              "words": results,
              "passingWords": [word for word, result in results.items()
                               if result["passesTestGate"]],
              "deployed": False}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
