"""Evaluate a frozen six-word residual model on existing regression recordings.

This script never tunes thresholds and does not claim an independent test: the
recording pools have been inspected by earlier experiments. It provides a fixed
cross-source regression and false-accept screen before browser integration.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

import body_tip_features
import train_expansion_batch as batch
from train_motion_residual import MotionNet


DEFAULT_SOURCES = (
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
    parser.add_argument("--source", action="append", type=Path)
    args = parser.parse_args()
    sources = tuple(args.source or DEFAULT_SOURCES)

    validation = json.loads((args.experiment / "validation.json").read_text())
    if not validation["passesValidation"]:
        raise ValueError("Development screen failed")
    checkpoint = args.experiment / "motion-private.pt"
    if sha(checkpoint) != validation["checkpointSha256"]:
        raise ValueError("Checkpoint digest differs from the frozen validation")
    protocol = json.loads((args.experiment / "protocol.json").read_text())
    labels = protocol["labels"]

    rows, seen = [], set()
    for source in sources:
        for row in json.loads(source.read_text()):
            identity = row.get("sha256")
            if identity in seen or row.get("sequence") is None:
                continue
            if not row.get("body") or not any(value is not None for value in row["body"]):
                continue
            seen.add(identity)
            rows.append(row)
    if not rows:
        raise ValueError("No body-enabled regression recordings")

    saved = torch.load(checkpoint, weights_only=True)
    output_labels = saved["outputLabels"]
    features = np.stack([body_tip_features.features(row) for row in rows])
    # The normalization buffers are saved in every member state.
    probabilities = []
    for state in saved["states"]:
        model = MotionNet(len(output_labels), state["mean"].reshape(-1),
                          state["scale"].reshape(-1))
        model.load_state_dict(state)
        model.eval()
        with torch.no_grad():
            probabilities.append(model(torch.tensor(features)).softmax(1).numpy())
    probabilities = np.mean(probabilities, axis=0)

    batch.trainer.LABELS = labels
    selected = validation["selected"]
    predictions = batch.trainer.outputs(
        rows, probabilities, selected["threshold"], selected["margin"])
    metrics = batch.trainer.metrics(rows, predictions)
    result = {
        "scope": ("Previously frozen, previously inspected recorded clips from existing "
                  "signers; fixed model and development thresholds; no tuning."),
        "experimentCheckpointSha256": validation["checkpointSha256"],
        "sourceSha256": {str(source): sha(source) for source in sources},
        "metrics": metrics,
        "perWord": metrics["perWord"],
        "passesRegressionGate": batch.trainer.gate(metrics),
        "deployed": False,
        "predictions": [
            {"sha256": row["sha256"], "expected": row["label"], "predicted": prediction}
            for row, prediction in zip(rows, predictions)
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items()
                      if key != "predictions"}, indent=2))


if __name__ == "__main__":
    main()
