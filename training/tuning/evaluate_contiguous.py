"""Evaluate the six-word model on contiguous-sampled features.

Compares the shipped prototypes and rejection parameters against prototypes rebuilt from the
same training clips re-extracted with live-style contiguous sampling. Parameters are tuned on
the validation split only (including DRINK negatives); the test split is scored once. Clips
with no usable sequence count as rejections, exactly as the shipped harness does.
"""
import itertools
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, "/opt/handspeak/repository/training")
from fit_words import mirror, distance, predict, metrics  # noqa: E402

CACHE = Path("/opt/handspeak-training/popsign/extracted-contiguous.json")
MODEL = Path("/opt/handspeak/repository/models/asl-words.json")

rows = json.loads(CACHE.read_text())
train = [r for r in rows if r["split"] == "train" and r.get("sequence") is not None]
val = [r for r in rows if r["split"] == "val" and r.get("sequence") is not None and r["label"] != "DRINK"]
val_neg = [r for r in rows if r["split"] == "val" and r.get("sequence") is not None and r["label"] == "DRINK"]
test = [r for r in rows if r["split"] == "test" and r["label"] != "DRINK"]
test_neg = [r for r in rows if r["split"] == "test" and r.get("sequence") is not None and r["label"] == "DRINK"]

model = json.loads(MODEL.read_text())
shipped_params = model["parameters"]
shipped_prototypes = model["samples"]
rebuilt_prototypes = train
print("contiguous: train", len(train), "val", len(val), "val negatives", len(val_neg),
      "test", len(test), "(usable", sum(1 for r in test if r.get("sequence") is not None), ")")
print("shipped prototypes:", len(shipped_prototypes), Counter(s["label"] for s in shipped_prototypes))
print("rebuilt prototypes:", len(rebuilt_prototypes), Counter(r["label"] for r in rebuilt_prototypes))

_cache = {}


def matrix(items, prototypes):
    key = (id(items), len(prototypes))
    if key in _cache:
        return _cache[key]
    refs = [np.array(p["sequence"]) for p in prototypes]
    out = []
    for row in items:
        if row.get("sequence") is None:
            out.append(None)
            continue
        a = np.array(row["sequence"])
        m = mirror(a)
        out.append([min(distance(a, b), distance(m, b)) for b in refs])
    _cache[key] = out
    return out


def predict_all(items, prototypes, params):
    matrix_rows = matrix(items, prototypes)
    usable = [i for i, row in enumerate(matrix_rows) if row is not None]
    if not usable:
        return [None] * len(items)
    scores = predict(np.array([matrix_rows[i] for i in usable]), prototypes, params)
    predictions = [None] * len(items)
    for position, value in zip(usable, scores):
        predictions[position] = value
    return predictions


def score(positive, negative, prototypes, params):
    predictions = predict_all(positive, prototypes, params)
    stats = metrics(positive, predictions)
    false = sum(1 for x in predict_all(negative, prototypes, params) if x is not None)
    return dict(correct=stats["correct"], wrong=stats["wrong"], rejected=stats["rejected"],
                total=stats["total"], falseAccepts=false,
                acc=round(stats["accuracyIncludingRejections"], 4))


def evaluate(name, prototypes, params):
    return {"name": name,
            "validation": score(val, val_neg, prototypes, params),
            "test": score(test, test_neg, prototypes, params)}


print("\n=== shipped prototypes + shipped parameters, contiguous features ===")
print(json.dumps(evaluate("shipped/shipped", shipped_prototypes, shipped_params), indent=2))
print("\n=== rebuilt prototypes + shipped parameters ===")
print(json.dumps(evaluate("rebuilt/shipped", rebuilt_prototypes, shipped_params), indent=2))

best = None
for limit, ratio, votes, strong in itertools.product(
        [.3, .4, .5, .65, .75, .85, 1.], [1.0, 1.1, 1.25, 1.5, 2.], [1, 2, 3], [1.5, 2., 3., 5.]):
    params = dict(maxDistance=limit, minRatio=ratio, minVotes=votes, mirror=True, strongRatio=strong)
    stats = metrics(val, predict_all(val, rebuilt_prototypes, params))
    false = sum(1 for x in predict_all(val_neg, rebuilt_prototypes, params) if x is not None)
    if stats["wrong"] or false:
        continue
    key = (-stats["correct"], stats["rejected"])
    if best is None or key < best[0]:
        best = (key, params, stats)

if best is None:
    print("\nno zero-wrong/zero-false operating point on validation")
else:
    _, params, stats = best
    print("\n=== rebuilt prototypes + validation-tuned parameters ===")
    print("parameters:", params, "validation:",
          {k: stats[k] for k in ("correct", "wrong", "rejected", "total")})
    print(json.dumps(evaluate("rebuilt/tuned", rebuilt_prototypes, params), indent=2))
    print("\nper-word on test:")
    predictions = predict_all(test, rebuilt_prototypes, params)
    per_word = {}
    for row, value in zip(test, predictions):
        per_word.setdefault(row["label"], Counter())[value or "REJECTED"] += 1
    for label in sorted(per_word):
        counts = per_word[label]
        print(f"  {label:<12}", dict(counts))
