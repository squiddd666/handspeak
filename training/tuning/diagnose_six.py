"""Read-only diagnosis of the shipped six-word DTW model on its held-out test clips.

Reproduces the recorded screen with the shipped prototypes and validation-tuned
parameters, then separates tracking failures (no usable sequence) from classifier errors.
"""
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

train = [r for r in rows if r["split"] == "train" and r.get("sequence") is not None]
test_rows = [r for r in rows if r["split"] == "test"]
usable = [r for r in test_rows if r.get("sequence") is not None and r["label"] != "DRINK"]
untracked = [r for r in test_rows if r.get("sequence") is None and r["label"] != "DRINK"]
negatives = [r for r in test_rows if r.get("sequence") is not None and r["label"] == "DRINK"]

model = json.loads(MODEL.read_text())
params = model["parameters"]
print("shipped parameters:", params)
print("train prototypes:", len(model["samples"]), "| test usable:", len(usable),
      "| test untracked:", len(untracked), "| drink negatives:", len(negatives))


def matrix(items):
    out = []
    for r in items:
        a = np.array(r["sequence"])
        m = mirror(a)
        out.append([min(distance(a, np.array(b["sequence"])), distance(m, np.array(b["sequence"])))
                    for b in model["samples"]])
    return np.array(out)


m_test = matrix(usable)
pred_test = predict(m_test, model["samples"], params)
m_neg = matrix(negatives)
pred_neg = predict(m_neg, model["samples"], params)

stats = metrics(usable, pred_test)
print("\ntrackable test clips (57):", stats)
per_word = {}
for row, out in zip(usable, pred_test):
    per_word.setdefault(row["label"], Counter())[out or "REJECTED"] += 1
for label in sorted(per_word):
    counts = per_word[label]
    print(f"  {label:<12}", dict(counts))

print("\nDRINK false accepts:", sum(1 for x in pred_neg if x is not None), "/", len(negatives))
accepted = [(r["label"], d) for r, d in zip(negatives, m_neg) if x is not None]
print("untracked (tracking failure) clips:", Counter(r["label"] for r in untracked))
print("total twelve-per-word basis: 71 usable + 15 untracked = 86 attempted"
      if False else "usable:", len(usable), "untracked:", len(untracked))
