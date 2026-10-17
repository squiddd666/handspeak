"""Validation-only search for a better rejection operating point on the shipped model.

Parameters are tuned on the validation split only (including DRINK negatives). The held-out
test split is evaluated once at the end and reported against the shipped numbers.
"""
import itertools
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, "/opt/handspeak/repository/training")
from fit_words import mirror, distance, predict, metrics  # noqa: E402

CACHE = Path("/opt/handspeak-training/popsign/extracted.json")
MODEL = Path("/opt/handspeak/repository/models/asl-words.json")

rows = json.loads(CACHE.read_text())
for r in rows:
    if r.get("label") == "THANKYOU":
        r["label"] = "THANK YOU"

model = json.loads(MODEL.read_text())
refs = [np.array(s["sequence"]) for s in model["samples"]]
labels = [s["label"] for s in model["samples"]]
shipped = model["parameters"]


def matrix(items):
    out = []
    for r in items:
        a = np.array(r["sequence"])
        m = mirror(a)
        out.append([min(distance(a, b), distance(m, b)) for b in refs])
    return np.array(out)


val = [r for r in rows if r["split"] == "val" and r.get("sequence") is not None and r["label"] != "DRINK"]
neg = [r for r in rows if r["split"] == "val" and r.get("sequence") is not None and r["label"] == "DRINK"]
test = [r for r in rows if r["split"] == "test" and r.get("sequence") is not None and r["label"] != "DRINK"]
tneg = [r for r in rows if r["split"] == "test" and r.get("sequence") is not None and r["label"] == "DRINK"]
print("val:", len(val), "val negatives:", len(neg), "test:", len(test), "test negatives:", len(tneg))

vm, nm = matrix(val), matrix(neg)
tm, tnm = matrix(test), matrix(tneg)


def evaluate(p, m, rows_, nm_):
    out = predict(m, model["samples"], p)
    stats = metrics(rows_, out)
    false = sum(1 for x in predict(nm_, model["samples"], p) if x is not None)
    return dict(correct=stats["correct"], wrong=stats["wrong"], rejected=stats["rejected"],
                total=stats["total"], falseAccepts=false, acc=stats["accuracyIncludingRejections"])


print("shipped on validation:", evaluate(shipped, vm, val, nm))
print("shipped on test       :", evaluate(shipped, tm, test, tnm))

best = None
for limit, ratio, votes, strong in itertools.product(
        [.3, .4, .5, .65, .75, .85, 1.], [1.0, 1.1, 1.25, 1.5, 2.], [1, 2, 3], [1.5, 2., 3., 5.]):
    p = dict(maxDistance=limit, minRatio=ratio, minVotes=votes, mirror=True, strongRatio=strong)
    v = evaluate(p, vm, val, nm)
    if v["wrong"] or v["falseAccepts"]:
        continue
    key = (-v["correct"], v["rejected"])
    if best is None or key < best[0]:
        best = (key, p, v)

if best is None:
    print("\nno zero-wrong / zero-false operating point on validation")
else:
    key, p, v = best
    print("\nvalidation-optimal candidate:", p)
    print("  validation:", v)
    print("  test       :", evaluate(p, tm, test, tnm))
    print("  shipped    :", evaluate(shipped, tm, test, tnm))
