"""Publish the per-word cutoff model and its recorded results.

Calibration was done on the validation split only (loosest per-word cutoff that keeps zero
wrong and zero DRINK false accepts, capped at 1.0); the test split was scored once and the
JavaScript recognizer verified to agree with the Python scoring. This writes the model, the
recorded-accuracy report and the evaluation report.
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, "/opt/handspeak/repository/training")
from fit_words import mirror, distance  # noqa: E402

REPO = Path("/opt/handspeak/repository")
CACHE = Path("/opt/handspeak-training/popsign/extracted-contiguous.json")
MODEL = REPO / "models/asl-words.json"
EVAL = REPO / "models/asl-words-evaluation.json"
ACCURACY = REPO / "models/motion-word-accuracy.json"
CUTOFFS = {"HELLO": .75, "THANK YOU": 1.0, "PLEASE": 1.0, "YES": 1.0, "NO": .85, "FINISH": 1.0}

model = json.loads(MODEL.read_text())
params = model["parameters"]
prototypes = model["samples"]
words = model["labels"]
refs = [np.array(p["sequence"]) for p in prototypes]
labels = np.array([p["label"] for p in prototypes])

rows = json.loads(CACHE.read_text())
val = [r for r in rows if r["split"] == "val" and r["label"] != "DRINK"]
val_neg = [r for r in rows if r["split"] == "val" and r.get("sequence") is not None and r["label"] == "DRINK"]
test = [r for r in rows if r["split"] == "test" and r["label"] != "DRINK"]
test_neg = [r for r in rows if r["split"] == "test" and r.get("sequence") is not None and r["label"] == "DRINK"]


def matrix(items):
    out = []
    for row in items:
        if row.get("sequence") is None:
            out.append(None)
            continue
        a = np.array(row["sequence"])
        m = mirror(a)
        out.append([min(distance(a, b), distance(m, b)) for b in refs])
    return out


def predict(items, matrix_rows):
    output = []
    for row, distances in zip(items, matrix_rows):
        if distances is None:
            output.append(None)
            continue
        order = np.argsort(distances, kind="stable")
        best, second = order[0], order[1]
        label = labels[best]
        other = next(distances[i] for i in order if labels[i] != label)
        separation = other / (distances[best] + 1e-6)
        votes = sum(labels[order[:3]] == label)
        limit = CUTOFFS.get(label, params["maxDistance"])
        ok = (distances[best] <= limit and separation >= params["minRatio"]
              and (votes >= params["minVotes"] or separation >= params.get("strongRatio", float("inf"))))
        output.append(str(label) if ok else None)
    return output


val_pred = predict(val, matrix(val))
test_pred = predict(test, matrix(test))
neg_pred = predict(test_neg, matrix(test_neg))

usable = [r for r in test if r.get("sequence") is not None]
usable_pred = [p for r, p in zip(test, test_pred) if r.get("sequence") is not None]
correct = sum(1 for r, p in zip(test, test_pred) if p == r["label"])
wrong = sum(1 for r, p in zip(test, test_pred) if p is not None and p != r["label"])
rejected = sum(1 for p in test_pred if p is None)
untracked = len(test) - len(usable)
false = sum(1 for p in neg_pred if p is not None)
val_correct = sum(1 for r, p in zip(val, val_pred) if p == r["label"])
val_wrong = sum(1 for r, p in zip(val, val_pred) if p is not None and p != r["label"])
val_false = sum(1 for p in predict(val_neg, matrix(val_neg)) if p is not None)

model["parameters"] = {**params, "maxDistanceByLabel": CUTOFFS}
MODEL.write_text(json.dumps(model, indent=2) + "\n")

per_word = {}
for row, value in zip(test, test_pred):
    per_word.setdefault(row["label"], Counter())["hit" if value == row["label"] else
                                                 ("rejected" if value is None else "wrong")] += 1

evaluation = json.loads(EVAL.read_text())
history = evaluation.get("protocolHistory", {})
history["globalCutoff-20261017"] = {
    "protocol": "contiguous sampling, single global cutoff 0.65",
    "test": evaluation["test"],
    "testIncludingTrackingFailures": evaluation["testIncludingTrackingFailures"],
    "unknownWordTest": evaluation["unknownWordTest"],
}
evaluation.update(
    evaluationProtocol=(
        "Contiguous frame sampling over the signing window, matching the live camera pipeline. "
        "Per-word distance cutoffs were calibrated on the validation split only (loosest cutoff "
        "that keeps zero wrong and zero false accepts, capped at 1.0); the test split was scored "
        "once and the deployed recognizer was verified to reproduce it. Model prototypes are "
        "unchanged. Test recordings are never training references; untracked clips count as "
        "failures, not rejections."
    ),
    protocolHistory=history,
    parameters={**params, "maxDistanceByLabel": CUTOFFS},
    validation={"correct": val_correct, "wrong": val_wrong, "rejected": len(val) - val_correct - val_wrong,
                "total": len(val)},
    validationUnknownWord={"label": "DRINK", "total": len(val_neg), "falseAccepts": val_false},
    test={"correct": correct, "wrong": wrong, "rejected": rejected - untracked, "total": len(usable),
          "coverage": (len(usable) - (rejected - untracked)) / len(usable),
          "accuracyAmongAccepted": correct / (len(usable) - (rejected - untracked)),
          "accuracyIncludingRejections": correct / len(usable)},
    testIncludingTrackingFailures={"correct": correct, "total": len(test)},
    unknownWordTest={"label": "DRINK", "total": len(test_neg), "falseAccepts": false,
                     "rejected": len(test_neg) - false},
    confusion={label: dict.fromkeys(words + ["rejected"], 0) for label in words},
    excludedForTracking={"test": untracked},
)
for row, value in zip(test, test_pred):
    evaluation["confusion"][row["label"]][value or "rejected"] += 1
EVAL.write_text(json.dumps(evaluation, indent=2) + "\n")

accuracy = json.loads(ACCURACY.read_text())
profile = accuracy["profiles"]["default"]
profile["model"] = "Default six-word model with per-word distance cutoffs"
profile["scope"] = ("Recorded clips sampled contiguously as the live camera pipeline does; "
                    "per-word cutoffs calibrated on validation only. Live-camera accuracy unverified.")
profile["words"] = {word: {"correct": per_word[word]["hit"], "total": sum(per_word[word].values())}
                    for word in words}
profile["note"] = ("2026-10-17: contiguous sampling, then per-word distance cutoffs calibrated on "
                   "validation. Model prototypes unchanged; recognizer verified in JavaScript. "
                   "Earlier runs retained in protocolHistory.")
ACCURACY.write_text(json.dumps(accuracy, indent=2) + "\n")

print("cutoffs:", CUTOFFS)
print(f"validation correct {val_correct}/{len(val)} wrong {val_wrong} DRINK false {val_false}/{len(val_neg)}")
print(f"test correct {correct}/{len(test)} wrong {wrong} rejected {rejected} "
      f"DRINK false {false}/{len(test_neg)}")
for word in words:
    counts = per_word[word]
    total = sum(counts.values())
    print(f"  {word:<12} {counts['hit']:>2}/{total} ({round(100*counts['hit']/total, 1)}%)"
          f"  wrong={counts['wrong']} rejected={counts['rejected']}")
