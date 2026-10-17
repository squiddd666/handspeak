"""Score and calibrate the five-word research model on contiguous-sampled features.

Distances come from a numpy DTW that is checked against research_words.distance before use,
so the numbers published here are the numbers the deployed server matcher will produce.
The cutoff grid is scored on validation only; the test split is evaluated once.
"""
import json
import math
import sys
from collections import Counter
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, "/opt/handspeak/repository")
import research_words  # noqa: E402  (reference implementation used for verification)

ROOT = Path("/opt/handspeak-training/daily-words/citizen-research")
MODEL_PATH = ROOT / "dtw-private.json"
FEATURES = ROOT / "extracted-contiguous.json"
MATRIX = ROOT / "distances-contiguous.json"
LABELS = ["NAME", "HOME", "HAVE", "WANT", "LOVE"]
GRID = [.2, .3, .4, .5, .6, .7, .8, .9, 1.0, 1.1, 1.2, 1.4, 1.6, 2.0]

model = json.loads(MODEL_PATH.read_text())
params = model["parameters"]
refl = [s["label"] for s in model["samples"]]
refs = [s["sequence"] for s in model["samples"]]
dev = json.loads((ROOT / "development-manifest.json").read_text())
test = json.loads((ROOT / "test-manifest.json").read_text())
features = {r["sha256"]: r["sequence"] for r in json.loads(FEATURES.read_text())}
rows = [r for r in dev if r["split"] == "val"] + test
usable = [r for r in rows if features.get(r["sha256"])]
print("rows:", len(rows), "usable:", len(usable))

WEIGHTS = np.array([1.0, 1.0, 0.5] * 21)


def prepared(seq, mirror):
    """Same layout and weights as research_words.prepared."""
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
    # The reference recurrence is sequential: current[j-1] uses the value computed
    # earlier in the same row, so the band cannot be vectorised.
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


PREP_REFS = None


def work(sha):
    global PREP_REFS
    if PREP_REFS is None:
        PREP_REFS = [prepared(ref, False) for ref in refs]
    direct, mirrored = prepared(features[sha], False), prepared(features[sha], True)
    return sha, [min(dtw(direct, ref), dtw(mirrored, ref)) for ref in PREP_REFS]


if MATRIX.exists():
    matrix = json.loads(MATRIX.read_text())
else:
    with ProcessPoolExecutor(max_workers=3) as pool:
        pairs = list(pool.map(work, [r["sha256"] for r in usable], chunksize=4))
    matrix = {sha: distances for sha, distances in pairs}
    MATRIX.write_text(json.dumps(matrix, separators=(",", ":")))
print("distance matrix:", len(matrix), "x", len(refl))

# Verify the numpy DTW against the implementation the server uses.
check_sha = next(iter(matrix))
a = research_words.prepared(features[check_sha])
b = research_words.prepared(features[check_sha], True)
errors = []
for index in range(len(refs)):
    reference = (research_words.distance(a, research_words.prepared(refs[index])),
                 research_words.distance(b, research_words.prepared(refs[index])))
    mine = (dtw(prepared(features[check_sha], False), prepared(refs[index], False)),
            dtw(prepared(features[check_sha], True), prepared(refs[index], False)))
    errors.append(max(abs(reference[0] - mine[0]), abs(reference[1] - mine[1])))
print("max deviation from research_words.distance:", max(errors))
if max(errors) > 1e-6:
    raise SystemExit("distance mismatch; refusing to score")


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
            if value is None or untracked:
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
val_rows = [r for r in dev if r["split"] == "val"]
baseline_val, _ = score(val_rows, base)
print("model parameters:", params)
print("baseline validation:", baseline_val)
baseline_test, per_word = score(test, base)
print("baseline test      :", baseline_test)
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
    print(f"  cutoff {word:<6} {base[word]} -> {chosen}")

final_val, _ = score(val_rows, cutoffs)
print("\nafter validation:", final_val)
final_test, per_word = score(test, cutoffs)
print("after test       :", final_test)
for word in LABELS:
    counts = Counter({v: c for (label, v), c in per_word.items() if label == word})
    hit = counts.get(word, 0)
    total = sum(counts.values())
    print(f"  {word:<6} {hit:>2}/{total} ({round(100*hit/max(1,total),1)}%)  {dict(counts)}")
print("\nCUTOFFS:", json.dumps(cutoffs))
