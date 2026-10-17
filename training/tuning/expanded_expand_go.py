"""GO-focused experiment: expand GO prototypes to every usable training clip.

Signers are disjoint between splits: GO's 17 usable training clips come from 10 signers,
its 3 validation clips from 3 others, its 6 test clips from 4 more. The shipped model uses
only 10 GO prototypes, so this adds the remaining 7 and lets the validation split decide
whether the expansion earns promotion. The test split is scored once.
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
features = {r["key"]: r["sequence"] for r in json.loads(Path("/tmp/expanded-contiguous.json").read_text())
            if r.get("sequence")}

go_train = [r for r in rows if r["label"] == "GO" and r["split"] == "train" and r["key"] in features]
used_go = {json.dumps(s["sequence"]) for s in model["samples"] if s["label"] == "GO"}
extra = [r for r in go_train if json.dumps(features[r["key"]]) not in used_go]
print("GO training clips usable:", len(go_train), "already represented:", len(go_train) - len(extra),
      "to add:", len(extra))

samples = [s for s in model["samples"] if s["label"] != "GO"]
samples += [{"label": "GO", "sequence": features[r["key"]]} for r in go_train]
refl = [s["label"] for s in samples]
refs = [np.array(s["sequence"]) for s in samples]
print("expanded GO prototypes:", sum(1 for l in refl if l == "GO"), "total refs:", len(refs))

val = [r for r in rows if r.get("split") == "val" and r["key"] in features]
test = [r for r in rows if r.get("split") == "test" and r["key"] in features]


def work(key):
    a = np.array(features[key])
    m = mirror(a)
    return key, [min(distance(a, ref), distance(m, ref)) for ref in refs]


with ProcessPoolExecutor(max_workers=3) as pool:
    matrix = {k: d for k, d in pool.map(work, [r["key"] for r in val + test], chunksize=4)}
Path("/tmp/go-expanded-distances.json").write_text(json.dumps(matrix, separators=(",", ":")))
print("matrix:", len(matrix))


def predict(key, cutoffs):
    distances = matrix[key]
    order = sorted(range(len(refl)), key=lambda i: distances[i])
    label = refl[order[0]]
    other = next(distances[i] for i in order if refl[i] != label)
    ratio = other / (distances[order[0]] + 1e-6)
    votes = sum(1 for i in order[:3] if refl[i] == label)
    limit = cutoffs.get(label, params["maxDistance"])
    ok = (distances[order[0]] <= limit and ratio >= params["minRatio"]
          and (votes >= params["minVotes"] or ratio >= params.get("strongRatio", float("inf"))))
    return label if ok else None


def score(rows, cutoffs):
    counts = dict(correct=0, wrong=0, rejected=0, false=0)
    per_word = Counter()
    for row in rows:
        value = predict(row["key"], cutoffs)
        if row["label"] in LABELS:
            outcome = "hit" if value == row["label"] else ("REJECTED" if value is None else "WRONG")
            counts["correct" if outcome == "hit" else outcome.lower()] += 1
            per_word[(row["label"], outcome)] += 1
        elif value is not None:
            counts["false"] += 1
    return counts, per_word


base = {word: params["maxDistance"] for word in LABELS}
baseline_val, _ = score(val, base)
print("\nGO-expanded, shipped cutoff (validation):", baseline_val)
baseline_test, per_word = score(test, base)
print("GO-expanded, shipped cutoff (test)      :", baseline_test)
for word in ["GO", "FOOD", "BOOK", "DRINK"]:
    counts = {o: c for (label, o), c in per_word.items() if label == word}
    hit = counts.get("hit", 0)
    print(f"  {word:<6} {hit}/{sum(counts.values())}  {counts}")

cutoffs = dict(base)
for word in LABELS:
    chosen = base[word]
    for limit in GRID:
        if limit <= base[word]:
            continue
        trial = dict(cutoffs)
        trial[word] = limit
        result, _ = score(val, trial)
        if result["wrong"] > baseline_val["wrong"] or result["false"] > baseline_val["false"]:
            break
        chosen = limit
    cutoffs[word] = chosen
print("\ncutoffs:", cutoffs)
final_val, _ = score(val, cutoffs)
print("validation:", final_val)
final_test, per_word = score(test, cutoffs)
print("test       :", final_test)
for word in LABELS:
    counts = {o: c for (label, o), c in per_word.items() if label == word}
    hit = counts.get("hit", 0)
    total = sum(counts.values())
    print(f"  {word:<8} {hit:>2}/{total} ({round(100*hit/max(1,total),1)}%)  {counts}")
