"""Select GO prototypes from every unused GO clip on disk, using validation only.

76 unused GO clips (PopSign and ASL-Citizen material already on the server) are extracted
contiguously; distances to the validation and test clips are computed with the same verified
numpy DTW. Greedy forward selection adds candidates only while validation wrong predictions and
false accepts stay at or below the shipped model. The test split is scored once at the end.
"""
import json
import sys
from collections import Counter
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, "/opt/handspeak/repository/training")
from fit_words import mirror, distance  # noqa: E402

SITE = Path("/opt/handspeak/repository")
LABELS = ["DRINK", "WATER", "BOOK", "FOOD", "HUNGRY", "LIKE", "GO"]
GRID = [.5, .6, .7, .8, .9, 1.0, 1.2, 1.5, 2.0]

model = json.loads((SITE / "models/asl-extra-words.json").read_text())
params = model["parameters"]
rows = json.loads(Path("/tmp/expanded-manifest.json").read_text())
for row in rows:
    row["key"] = row.get("sha256") or row["file"]
base_features = {r["key"]: r["sequence"] for r in json.loads(Path("/tmp/expanded-contiguous.json").read_text())
                 if r.get("sequence")}
extra = [r for r in json.loads(Path("/tmp/go-extra-contiguous.json").read_text()) if r.get("sequence")]
print("extra GO clips with sequences:", len(extra), "of", 76,
      Counter(r["participant"] for r in extra).most_common(3))

shipped_refs = model["samples"]
matrix = json.loads(Path("/tmp/expanded-distances.json").read_text())
refs = [np.array(s["sequence"]) for s in shipped_refs]
refl = [s["label"] for s in shipped_refs]


def work(key):
    a = np.array(base_features[key])
    m = mirror(a)
    return key, [min(distance(a, np.array(r["sequence"])), distance(m, np.array(r["sequence"])))
                 for r in extra]


with ProcessPoolExecutor(max_workers=3) as pool:
    added = {k: d for k, d in pool.map(work, sorted(matrix), chunksize=4)}
for key, values in added.items():
    matrix[key] = matrix[key] + values
refl = refl + ["GO"] * len(extra)
print("total references:", len(refl))

val = [r for r in rows if r.get("split") == "val" and r["key"] in matrix]
test = [r for r in rows if r.get("split") == "test" and r["key"] in matrix]


def predict(key, selected, cutoffs):
    distances = matrix[key]
    order = sorted(selected, key=lambda i: distances[i])
    best = order[0]
    label = refl[best]
    other = next(distances[i] for i in order if refl[i] != label)
    ratio = other / (distances[best] + 1e-6)
    votes = sum(1 for i in order[:3] if refl[i] == label)
    limit = cutoffs.get(label, params["maxDistance"])
    ok = (distances[best] <= limit and ratio >= params["minRatio"]
          and (votes >= params["minVotes"] or ratio >= params.get("strongRatio", float("inf"))))
    return label if ok else None


def score(rows, selected, cutoffs):
    counts = dict(correct=0, wrong=0, rejected=0, false=0)
    for row in rows:
        value = predict(row["key"], selected, cutoffs)
        if row["label"] in LABELS:
            if value is None:
                counts["rejected"] += 1
            elif value == row["label"]:
                counts["correct"] += 1
            else:
                counts["wrong"] += 1
        elif value is not None:
            counts["false"] += 1
    return counts


base_cutoffs = {word: params["maxDistance"] for word in LABELS}
selected = list(range(len(shipped_refs)))
baseline_val = score(val, selected, base_cutoffs)
print("\nshipped model - validation:", baseline_val, " test:", score(test, selected, base_cutoffs))

candidates = list(range(len(shipped_refs), len(refl)))
for candidate in candidates:
    trial = sorted(selected + [candidate])
    result = score(val, trial, base_cutoffs)
    current = score(val, selected, base_cutoffs)
    if (result["wrong"] <= baseline_val["wrong"] and result["false"] <= baseline_val["false"]
            and result["correct"] > current["correct"]):
        selected = trial
print("selected GO prototypes:", sum(1 for i in selected if refl[i] == "GO"),
      "of", len(candidates), "extra clips")

cutoffs = dict(base_cutoffs)
for word in LABELS:
    chosen = base_cutoffs[word]
    for limit in GRID:
        if limit <= base_cutoffs[word]:
            continue
        trial = dict(cutoffs)
        trial[word] = limit
        result = score(val, selected, trial)
        if result["wrong"] > baseline_val["wrong"] or result["false"] > baseline_val["false"]:
            break
        chosen = limit
    cutoffs[word] = chosen
print("cutoffs:", cutoffs)
print("validation:", score(val, selected, cutoffs))
final = score(test, selected, cutoffs)
print("test       :", final)
per_word = Counter()
for row in test:
    value = predict(row["key"], selected, cutoffs)
    if row["label"] in LABELS:
        per_word[(row["label"], value or "REJECTED")] += 1
for word in LABELS:
    counts = {o: c for (label, o), c in per_word.items() if label == word}
    hit = counts.get(word, 0)
    total = sum(counts.values())
    print(f"  {word:<8} {hit:>2}/{total} ({round(100*hit/max(1,total),1)}%)  {counts}")
json.dump({"selected": selected, "cutoffs": cutoffs, "test": final},
          open("/tmp/go-selection.json", "w"), indent=2)
