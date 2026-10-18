"""Select the GO prototype subset on validation only, then score the test split once.

The full distance matrix over every candidate reference already exists; ranking a subset is
just a sort over that subset's columns, so greedy forward selection is cheap. The shipped 10
GO prototypes are the starting point and the remaining 17 contiguous-sampled GO training
clips are the candidates. Selection keeps validation wrong predictions and DRINK false
accepts at or below the shipped model's while maximising correct predictions.
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

SITE = Path("/opt/handspeak/repository")
LABELS = ["DRINK", "WATER", "BOOK", "FOOD", "HUNGRY", "LIKE", "GO"]
GRID = [.5, .6, .7, .8, .9, 1.0, 1.2, 1.5, 2.0]

model = json.loads((SITE / "models/asl-extra-words.json").read_text())
params = model["parameters"]
rows = json.loads(Path("/tmp/expanded-manifest.json").read_text())
for row in rows:
    row["key"] = row.get("sha256") or row["file"]
features = {r["key"]: r["sequence"] for r in json.loads(Path("/tmp/expanded-contiguous.json").read_text())
            if r.get("sequence")}

shipped = [s for s in model["samples"]]
shipped_go = [i for i, s in enumerate(shipped) if s["label"] == "GO"]
others = [i for i, s in enumerate(shipped) if s["label"] != "GO"]

# Merge two distance matrices: the shipped 145 references, then the 17 contiguous GO clips
# (the experiment matrix stores non-GO prototypes first, so its last 17 columns are the GO clips).
shipped_matrix = json.loads(Path("/tmp/expanded-distances.json").read_text())
go_matrix = json.loads(Path("/tmp/go-expanded-distances.json").read_text())
non_go = sum(1 for s in shipped if s["label"] != "GO")
keys = sorted(set(shipped_matrix) & set(go_matrix))
merged = {k: list(shipped_matrix[k]) + list(go_matrix[k][non_go:]) for k in keys}
matrix_rows = merged
go_clips = [r for r in rows if r["label"] == "GO" and r["split"] == "train" and r["key"] in features]
expanded_refs = shipped + [{"label": "GO", "sequence": features[r["key"]]} for r in go_clips]
refl = [s["label"] for s in expanded_refs]
candidates = [i for i in range(len(shipped), len(expanded_refs))]
print("merged matrix:", len(matrix_rows), "x", len(refl))
print("shipped GO prototypes:", len(shipped_go), "contiguous GO candidates:", len(candidates))

val = [r for r in rows if r.get("split") == "val" and r["key"] in matrix_rows]
test = [r for r in rows if r.get("split") == "test" and r["key"] in matrix_rows]
matrix = {r["key"]: matrix_rows[r["key"]] for r in val + test}


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
start = others + shipped_go
baseline_val = score(val, start, base_cutoffs)
baseline_test = score(test, start, base_cutoffs)
print("shipped model on this basis - validation:", baseline_val, " test:", baseline_test)

selected = list(start)
for candidate in list(candidates):
    trial = sorted(selected + [candidate])
    result = score(val, trial, base_cutoffs)
    if (result["wrong"] <= baseline_val["wrong"] and result["false"] <= baseline_val["false"]
            and result["correct"] > score(val, selected, base_cutoffs)["correct"]):
        selected = trial
        print(f"  keep GO clip {candidate}: validation {result}")
chosen = [i for i in selected if refl[i] == "GO"]
print("selected GO prototypes:", len(chosen))

cutoffs = dict(base_cutoffs)
for word in LABELS:
    limit_chosen = base_cutoffs[word]
    for limit in GRID:
        if limit <= base_cutoffs[word]:
            continue
        trial = dict(cutoffs)
        trial[word] = limit
        result = score(val, selected, trial)
        if result["wrong"] > baseline_val["wrong"] or result["false"] > baseline_val["false"]:
            break
        limit_chosen = limit
    cutoffs[word] = limit_chosen
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
    print(f"  {word:<8} {hit:>2}/{sum(counts.values())} ({round(100*hit/max(1,sum(counts.values())),1)}%)  {counts}")
print("\nselected GO columns:", chosen)
