"""Calibrate per-word cutoffs for the seven expanded words on validation only.

Distance matrix is computed with the same DTW used by training/fit_words (verified against the
deployed JavaScript recognizer for the six-word model); the final numbers are re-verified with
the recognizer itself before anything is published.
"""
import itertools
import json
import sys
from collections import Counter
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, "/opt/handspeak/repository/training")
from fit_words import mirror, distance  # noqa: E402

SITE = Path("/opt/handspeak/repository")
MANIFEST = Path("/tmp/expanded-manifest.json")
FEATURES = Path("/tmp/expanded-contiguous.json")
MATRIX = Path("/tmp/expanded-distances.json")
LABELS = ["DRINK", "WATER", "BOOK", "FOOD", "HUNGRY", "LIKE", "GO"]

model = json.loads((SITE / "models/asl-extra-words.json").read_text())
params = model["parameters"]
prototypes = model["samples"]
refl = np.array([p["label"] for p in prototypes])
refs = [np.array(p["sequence"]) for p in prototypes]
rows = json.loads(MANIFEST.read_text())
for row in rows:
    row["key"] = row.get("sha256") or row["file"]
features = {r["key"]: r["sequence"] for r in json.loads(FEATURES.read_text()) if r.get("sequence")}

val = [r for r in rows if r.get("split") == "val" and r["key"] in features]
test = [r for r in rows if r.get("split") == "test" and r["key"] in features]
neg_val = [r for r in val if r["label"] not in LABELS]
neg_test = [r for r in test if r["label"] not in LABELS]
print("val positives:", sum(1 for r in val if r["label"] in LABELS),
      "test positives:", sum(1 for r in test if r["label"] in LABELS),
      "test negatives:", len(neg_test))
print("val labels:", Counter(r["label"] for r in val if r["label"] in LABELS))


def work(key):
    a = np.array(features[key])
    m = mirror(a)
    return key, [min(distance(a, ref), distance(m, ref)) for ref in refs]


keys = [r["key"] for r in val + test]
if MATRIX.exists():
    matrix = json.loads(MATRIX.read_text())
else:
    with ProcessPoolExecutor(max_workers=3) as pool:
        matrix = {k: d for k, d in pool.map(work, keys, chunksize=4)}
    MATRIX.write_text(json.dumps(matrix, separators=(",", ":")))
print("distance matrix:", len(matrix), "x", len(refs))


def predict(key, cutoffs):
    distances = matrix[key]
    order = np.argsort(distances, kind="stable")
    best = order[0]
    label = str(refl[best])
    other = next(distances[i] for i in order if refl[i] != label)
    separation = other / (distances[best] + 1e-6)
    votes = sum(1 for i in order[:3] if refl[i] == label)
    limit = cutoffs.get(label, params["maxDistance"])
    ok = (distances[best] <= limit and separation >= params["minRatio"]
          and (votes >= params["minVotes"] or separation >= params.get("strongRatio", float("inf"))))
    return label if ok else None


def score(rows, cutoffs):
    counts = dict(correct=0, wrong=0, rejected=0, false=0, untracked=0)
    per_word = Counter()
    for row in rows:
        value = predict(row["key"], cutoffs)
        if row["label"] in LABELS:
            if value is None:
                counts["rejected"] += 1
            elif value == row["label"]:
                counts["correct"] += 1
            else:
                counts["wrong"] += 1
            per_word[(row["label"], value or "REJECTED")] += 1
        elif value is not None:
            counts["false"] += 1
    return counts, per_word


untracked_val = sum(1 for r in rows if r.get("split") == "val" and r["key"] not in features)
base = {word: params["maxDistance"] for word in LABELS}
baseline_val, per_word = score(val, base)
print("\nshipped parameters on contiguous features (validation):", baseline_val)
baseline_test, per_word = score(test, base)
print("shipped parameters on contiguous features (test)      :", baseline_test)
for word in LABELS:
    counts = {o: c for (label, o), c in per_word.items() if label == word}
    hit = counts.get(word, 0)
    total = sum(counts.values())
    print(f"  {word:<8} {hit:>2}/{total} ({round(100*hit/max(1,total),1)}%)  {counts}")

best = None
for word in LABELS:
    pass
cutoffs = dict(base)
for word in LABELS:
    chosen = base[word]
    for limit in [.5, .6, .7, .8, .9, 1.0, 1.2, 1.5, 2.0]:
        if limit <= base[word]:
            continue
        trial = dict(cutoffs)
        trial[word] = limit
        result, _ = score(val, trial)
        if result["wrong"] > baseline_val["wrong"] or result["false"] > baseline_val["false"]:
            break
        chosen = limit
    cutoffs[word] = chosen
print("\ncutoffs (validation only):", cutoffs)
final_val, _ = score(val, cutoffs)
print("validation:", final_val)
final_test, per_word = score(test, cutoffs)
print("test       :", final_test)
for word in LABELS:
    counts = {o: c for (label, o), c in per_word.items() if label == word}
    hit = counts.get(word, 0)
    total = sum(counts.values())
    print(f"  {word:<8} {hit:>2}/{total} ({round(100*hit/max(1,total),1)}%)  {counts}")
print("\nCUTOFFS:", json.dumps(cutoffs))
Path("/tmp/expanded-cutoffs.json").write_text(json.dumps(cutoffs))
