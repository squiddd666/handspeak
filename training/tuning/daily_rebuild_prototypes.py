"""Rebuild the five-word prototypes from contiguous-sampled training clips and calibrate.

The shipped prototypes were extracted with uniform frame sampling, which the live pipeline
never does. This rebuilds every prototype from the same training clips re-extracted
contiguously, calibrates per-word cutoffs on validation only, and scores the test split once.
Distances are computed with the same numpy DTW used by daily_calibrate_cutoffs.py, which was
verified against research_words.distance.
"""
import json
import math
import sys
from collections import Counter
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, "/opt/handspeak/repository")

ROOT = Path("/opt/handspeak-training/daily-words/citizen-research")
MODEL_PATH = ROOT / "dtw-private.json"
FEATURES = ROOT / "extracted-contiguous.json"
MATRIX = ROOT / "distances-rebuilt.json"
LABELS = ["NAME", "HOME", "HAVE", "WANT", "LOVE"]
GRID = [.2, .3, .4, .5, .6, .7, .8, .9, 1.0, 1.1, 1.2, 1.4, 1.6, 2.0]

model = json.loads(MODEL_PATH.read_text())
params = model["parameters"]
dev = json.loads((ROOT / "development-manifest.json").read_text())
test = json.loads((ROOT / "test-manifest.json").read_text())
features = {r["sha256"]: r["sequence"] for r in json.loads(FEATURES.read_text()) if r.get("sequence")}

train_target = [r for r in dev if r["split"] == "train" and r["label"] in LABELS and r["sha256"] in features]
train_other = [r for r in dev if r["split"] == "train" and r["label"] not in LABELS and r["sha256"] in features]
samples = [{"label": r["label"], "sequence": features[r["sha256"]]} for r in train_target + train_other]
refl = [s["label"] for s in samples]
print("rebuilt prototypes:", len(samples), Counter(refl))

val_rows = [r for r in dev if r["split"] == "val"]
usable_val = [r for r in val_rows if r["sha256"] in features]
usable_test = [r for r in test if r["sha256"] in features]
usable_neg = [r for r in test if r["label"] not in LABELS and r["sha256"] in features]
print("scoring rows:", len(usable_val) + len(usable_test), "refs:", len(samples))

WEIGHTS = np.array([1.0, 1.0, 0.5] * 21)


def prepared(seq, mirror):
    out = np.array(seq, dtype=float)
    left, right = out[:, :64].copy(), out[:, 64:].copy()
    if mirror:
        left, right = right, left
        left[:, 1::3] *= -1
        right[:, 1::3] *= -1
    left[:, 1:64] *= WEIGHTS
    right[:, 1:64] *= WEIGHTS
    return np.concatenate([left, right], axis=1)


def dtw(a, b):
    cost = np.zeros((len(a), len(b)))
    for offset in (0, 64):
        pa, pb = a[:, offset][:, None], b[:, offset][None, :]
        both = (pa * pb).astype(bool)
        diff = np.sum((a[:, None, offset + 1:offset + 64] - b[None, :, offset + 1:offset + 64]) ** 2, axis=2)
        cost += np.where(both, np.sqrt(diff / 63), 0.0) + 2.0 * (pa != pb)
    previous = [np.inf] * (len(b) + 1)
    previous[0] = 0.0
    for i in range(1, len(a) + 1):
        low, high = max(1, i - 5), min(len(b), i + 5)
        row = cost[i - 1]
        current = [np.inf] * (len(b) + 1)
        for j in range(low, high + 1):
            current[j] = row[j - 1] + min(previous[j], current[j - 1], previous[j - 1])
        previous = current
    return previous[-1] / max(len(a), len(b))


PREP = [prepared(s["sequence"], False) for s in samples]


def work(sha):
    direct, mirrored = prepared(features[sha], False), prepared(features[sha], True)
    return sha, [min(dtw(direct, ref), dtw(mirrored, ref)) for ref in PREP]


if MATRIX.exists():
    matrix = json.loads(MATRIX.read_text())
else:
    rows = usable_val + usable_test + usable_neg
    with ProcessPoolExecutor(max_workers=3) as pool:
        matrix = {sha: d for sha, d in pool.map(work, [r["sha256"] for r in rows], chunksize=4)}
    MATRIX.write_text(json.dumps(matrix, separators=(",", ":")))
print("distance matrix:", len(matrix), "x", len(samples))


def predict(sha, cutoffs):
    distances = matrix[sha]
    order = sorted(range(len(refl)), key=lambda i: distances[i])
    best = order[0]
    label = refl[best]
    other = next(distances[i] for i in order if refl[i] != label)
    ratio = other / (distances[best] + 1e-6)
    votes = sum(1 for i in order[:3] if refl[i] == label)
    limit = cutoffs.get(label, params["maxDistance"])
    ok = (label in LABELS and distances[best] <= limit and ratio >= params["minRatio"]
          and (votes >= params["minVotes"] or ratio >= params.get("strongRatio", float("inf"))))
    return label if ok else None


def score(rows, cutoffs):
    counts = dict(correct=0, wrong=0, missed=0, false=0, positives=0, unsupported=0)
    per_word = Counter()
    for row in rows:
        untracked = row["sha256"] not in matrix
        value = None if untracked else predict(row["sha256"], cutoffs)
        if row["label"] in LABELS:
            counts["positives"] += 1
            if untracked or value is None:
                counts["missed"] += 1
            elif value == row["label"]:
                counts["correct"] += 1
            else:
                counts["wrong"] += 1
            per_word[(row["label"], value or "REJECTED")] += 1
        else:
            counts["unsupported"] += 1
            if value is not None:
                counts["false"] += 1
    return counts, per_word


base = {word: params["maxDistance"] for word in LABELS}
baseline_val, _ = score(val_rows, base)
print("rebuilt prototypes, shipped cutoff (validation):", baseline_val)
baseline_test, per_word = score(test, base)
print("rebuilt prototypes, shipped cutoff (test)      :", baseline_test)
for word in LABELS:
    counts = Counter({v: c for (label, v), c in per_word.items() if label == word})
    hit = counts.get(word, 0)
    total = sum(counts.values())
    print(f"  {word:<6} {hit:>2}/{total} ({round(100*hit/max(1,total),1)}%)")

cutoffs = dict(base)
for word in LABELS:
    chosen = base[word]
    for limit in GRID:
        if limit <= base[word]:
            continue
        trial = dict(cutoffs)
        trial[word] = limit
        result, _ = score(val_rows, trial)
        if result["wrong"] > baseline_val["wrong"] or result["false"] > baseline_val["false"]:
            break
        chosen = limit
    cutoffs[word] = chosen
print("\ncutoffs:", cutoffs)
final_val, _ = score(val_rows, cutoffs)
print("validation:", final_val)
final_test, per_word = score(test, cutoffs)
print("test       :", final_test)
for word in LABELS:
    counts = Counter({v: c for (label, v), c in per_word.items() if label == word})
    hit = counts.get(word, 0)
    total = sum(counts.values())
    print(f"  {word:<6} {hit:>2}/{total} ({round(100*hit/max(1,total),1)}%)  {dict(counts)}")
(Path("/tmp/daily-rebuild-cutoffs.json")).write_text(json.dumps(cutoffs))
print("wrote /tmp/daily-rebuild-cutoffs.json")
