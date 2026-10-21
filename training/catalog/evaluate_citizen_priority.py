"""Regression-check development-pass priority models on frozen recorded clips.

This does not tune thresholds. It combines two already frozen, previously used
test caches and treats every non-target word as a rejection example.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "daily_words"))
import train_citizen as trainer

BASE = Path("/opt/handspeak-training")
SOURCES = [BASE / "accuracy-v4/test-features.json", BASE / "vocabulary-v8/test-features.json"]
WORDS = ("DRINK", "BOOK", "HUNGRY", "HOME", "FISH")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows():
    result, seen = [], set()
    for source in SOURCES:
        for row in json.loads(source.read_text()):
            if row["sha256"] not in seen:
                seen.add(row["sha256"])
                result.append(row)
    return result


def evaluate(word, records):
    root = BASE / f"priority-citizen-balanced-{word.lower()}-temporal-v4"
    selected = json.loads((root / "temporal-validation.json").read_text())["selected"]
    checkpoint = root / "temporal-private.pt"
    if not selected["passesValidation"] or sha(checkpoint) != selected["sha256"]:
        raise ValueError(f"Unfrozen or ineligible candidate: {word}")
    saved = torch.load(checkpoint, weights_only=True)
    outputs = selected["outputLabels"]
    network = trainer.Net(selected["width"], num_classes=len(outputs),
                          temporal_bins=selected["temporalBins"])
    network.load_state_dict(saved["state"])
    network.eval()
    usable = [row for row in records if row.get("sequence") is not None]
    with torch.no_grad():
        probabilities = network(torch.tensor(np.stack(
            [trainer.encoding.features(row) for row in usable]))).softmax(1).numpy()
    ranked = np.argsort(probabilities, axis=1)
    predictions = []
    for scores, order in zip(probabilities, ranked):
        winner, second = order[-1], order[-2]
        label = outputs[winner]
        predictions.append(word if label == word and scores[winner] >= selected["threshold"]
                           and scores[winner] - scores[second] >= selected["margin"] else None)
    positives = [i for i, row in enumerate(usable) if row["label"] == word]
    negatives = [i for i, row in enumerate(usable) if row["label"] != word]
    return {
        "word": word, "correct": sum(predictions[i] == word for i in positives),
        "supportedTotal": len(positives),
        "negativeFalseAccepts": sum(predictions[i] is not None for i in negatives),
        "negativeTotal": len(negatives), "usableClips": len(usable),
        "checkpointSha256": selected["sha256"],
        "sourceSha256": {str(path): sha(path) for path in SOURCES},
        "scope": "Previously frozen recorded-clip regression; no threshold tuning or new accuracy claim.",
    }


def main():
    records = rows()
    result = {"results": [evaluate(word, records) for word in WORDS], "deployed": False}
    path = Path("/opt/handspeak/repository/reports/priority-six-citizen-regression.json")
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
