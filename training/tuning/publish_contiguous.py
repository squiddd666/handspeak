"""Refresh the published six-word recorded results onto the deployment-faithful protocol.

The model, its prototypes and its rejection parameters are unchanged. Only the measurement
basis changes: frames are sampled contiguously around the signing window (what the live camera
pipeline captures) instead of uniformly across the whole clip. The previous numbers are kept
in protocolHistory so the change is auditable.
"""
import json
from collections import Counter
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, "/opt/handspeak/repository/training")
from fit_words import mirror, distance, predict, metrics  # noqa: E402

REPO = Path("/opt/handspeak/repository")
CACHE = Path("/opt/handspeak-training/popsign/extracted-contiguous.json")
EVAL = REPO / "models/asl-words-evaluation.json"
ACCURACY = REPO / "models/motion-word-accuracy.json"

rows = json.loads(CACHE.read_text())
model = json.loads((REPO / "models/asl-words.json").read_text())
prototypes, params, words = model["samples"], model["parameters"], model["labels"]

refs = [np.array(p["sequence"]) for p in prototypes]


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


def predictions(items):
    scored = matrix(items)
    usable = [i for i, row in enumerate(scored) if row is not None]
    if not usable:
        return [None] * len(items)
    values = predict(np.array([scored[i] for i in usable]), prototypes, params)
    output = [None] * len(items)
    for position, value in zip(usable, values):
        output[position] = value
    return output


def block(positive, negative):
    pred = predictions(positive)
    stats = metrics(positive, pred)
    false = sum(1 for value in predictions(negative) if value is not None)
    return {
        "correct": stats["correct"],
        "wrong": stats["wrong"],
        "rejected": stats["rejected"],
        "total": stats["total"],
        "coverage": (stats["total"] - stats["rejected"]) / stats["total"],
        "accuracyAmongAccepted": (stats["correct"] / (stats["total"] - stats["rejected"])
                                  if stats["total"] - stats["rejected"] else 0),
        "accuracyIncludingRejections": stats["accuracyIncludingRejections"],
    }, false, pred


val = [r for r in rows if r["split"] == "val" and r["label"] != "DRINK"]
val_neg = [r for r in rows if r["split"] == "val" and r.get("sequence") is not None and r["label"] == "DRINK"]
test = [r for r in rows if r["split"] == "test" and r["label"] != "DRINK"]
test_neg = [r for r in rows if r["split"] == "test" and r.get("sequence") is not None and r["label"] == "DRINK"]

val_stats, val_false, _ = block(val, val_neg)
usable_test = sum(1 for r in test if r.get("sequence") is not None)
test_rows = [r for r in test if r.get("sequence") is not None]
test_stats, test_false, test_pred = block(test_rows, test_neg)
all_stats, _, all_pred = block(test, test_neg)

confusion = {label: dict.fromkeys(words + ["rejected"], 0) for label in words}
for row, value in zip(all_pred if False else [None] * len(test), all_pred):
    pass
for row, value in zip(test, all_pred):
    confusion[row["label"]][value or "rejected"] += 1

per_word = {}
for row, value in zip(test, all_pred):
    correct = value == row["label"]
    per_word.setdefault(row["label"], Counter())["hit" if correct else ("rejected" if value is None else "wrong")] += 1

evaluation = json.loads(EVAL.read_text())
accuracy = json.loads(ACCURACY.read_text())
previous = evaluation.get("protocolHistory", {}).get("uniformSampling-20261010") or {
    "protocol": "uniform 30-frame sampling across the whole clip",
    "test": evaluation["test"],
    "testIncludingTrackingFailures": evaluation["testIncludingTrackingFailures"],
    "unknownWordTest": evaluation["unknownWordTest"],
    "validation": evaluation["validation"],
    "usable": evaluation["usable"],
}

evaluation.update(
    evaluationProtocol=(
        "Frames are sampled contiguously over the signing window, matching the live camera "
        "pipeline, instead of uniformly across the whole clip. The model, its prototypes and "
        "its rejection parameters are unchanged from the earlier uniform-sampling run; the "
        "parameters were originally selected on validation under uniform sampling and were not "
        "re-tuned for this protocol, so this is a measurement change only and the numbers are "
        "not directly comparable with the previous published run. Test recordings are never "
        "training references; only sufficiently tracked clips are classified."
    ),
    protocolHistory={"uniformSampling-20261010": previous},
    usable={"train": sum(1 for r in rows if r["split"] == "train" and r.get("sequence") is not None),
            "val": len(val), "test": usable_test},
    trainingPerWord=dict(Counter(s["label"] for s in prototypes)),
    validation=val_stats,
    validationUnknownWord={"label": "DRINK", "total": len(val_neg), "falseAccepts": val_false},
    test=test_stats,
    testIncludingTrackingFailures={"correct": test_stats["correct"], "total": len(test)},
    unknownWordTest={"label": "DRINK", "total": len(test_neg), "falseAccepts": test_false,
                     "rejected": len(test_neg) - test_false},
    confusion=confusion,
    excludedForTracking={"train": sum(1 for r in rows if r["split"] == "train" and r.get("sequence") is None),
                         "val": sum(1 for r in rows if r["split"] == "val" and r.get("sequence") is None),
                         "test": sum(1 for r in test if r.get("sequence") is None)},
    limitations=("Six-word subset. Frame sampling now matches the live pipeline; results are not "
                 "comparable with the earlier uniform-sampling numbers kept in protocolHistory. "
                 "No live-camera benchmark. Unsupported-word evaluation covers DRINK only. "
                 "Distance is not a probability; review suggestions before adding them."),
)
EVAL.write_text(json.dumps(evaluation, indent=2) + "\n")

profile = accuracy["profiles"]["default"]
profile["model"] = "Default six-word model (deployment-faithful frame sampling)"
profile["scope"] = ("Recorded clips sampled contiguously over the signing window, as the live "
                    "camera pipeline does; live-camera accuracy still unverified. Protocol "
                    "changed 2026-10-17; earlier numbers are in protocolHistory.")
profile["words"] = {word: {"correct": per_word[word]["hit"], "total": sum(per_word[word].values())}
                    for word in words}
accuracy["profiles"]["default"]["note"] = (
    "Updated 2026-10-17 from uniform to contiguous frame sampling. Model, prototypes and "
    "rejection parameters unchanged. See models/asl-words-evaluation.json protocolHistory.")
ACCURACY.write_text(json.dumps(accuracy, indent=2) + "\n")

print("test:", test_stats)
print("test including tracking failures:", test_stats["correct"], "/", len(test))
print("validation:", val_stats, "false:", val_false)
print("DRINK test negatives:", len(test_neg), "accepted:", test_false)
for word in words:
    counts = per_word[word]
    print(f"  {word:<12} {counts['hit']:>2}/{sum(counts.values())}"
          f"  wrong={counts['wrong']} rejected={counts['rejected']}")
