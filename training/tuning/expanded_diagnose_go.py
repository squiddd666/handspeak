"""Diagnose why GO fails: per-clip distances, ranks of GO prototypes, and the competing label."""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, "/opt/handspeak/repository/training")
from fit_words import mirror, distance  # noqa: E402

SITE = Path("/opt/handspeak/repository")
LABELS = ["DRINK", "WATER", "BOOK", "FOOD", "HUNGRY", "LIKE", "GO"]

model = json.loads((SITE / "models/asl-extra-words.json").read_text())
params = model["parameters"]
prototypes = model["samples"]
refl = [p["label"] for p in prototypes]
counts = Counter(refl)
print("prototypes per label:", dict(counts))

rows = json.loads(Path("/tmp/expanded-manifest.json").read_text())
for row in rows:
    row["key"] = row.get("sha256") or row["file"]
features = {r["key"]: r["sequence"] for r in json.loads(Path("/tmp/expanded-contiguous.json").read_text())
            if r.get("sequence")}

go_test = [r for r in rows if r.get("split") == "test" and r["label"] == "GO"]
go_all = [r for r in rows if r["label"] == "GO"]
print("GO clips total:", len(go_all), "splits:", Counter(r.get("split") for r in go_all))
print("GO test clips:", len(go_test), "with features:", sum(1 for r in go_test if r["key"] in features))

refs = [np.array(p["sequence"]) for p in prototypes]
print("\nper GO test clip (shipped parameters maxDistance %s, minRatio %s, minVotes %s, strongRatio %s):"
      % (params["maxDistance"], params["minRatio"], params["minVotes"], params.get("strongRatio")))
for row in go_test:
    seq = features.get(row["key"])
    if not seq:
        print("  UNTRACKED", row["file"].split("/")[-1])
        continue
    a = np.array(seq)
    m = mirror(a)
    distances = [min(distance(a, ref), distance(m, ref)) for ref in refs]
    order = sorted(range(len(refl)), key=lambda i: distances[i])
    best = order[0]
    label = refl[best]
    other = next(distances[i] for i in order if refl[i] != label)
    ratio = other / (distances[best] + 1e-6)
    votes = sum(1 for i in order[:3] if refl[i] == label)
    go_rank = next((i for i, idx in enumerate(order) if refl[idx] == "GO"), None)
    go_best = distances[go_rank] if go_rank is not None else None
    accepted = (distances[best] <= params["maxDistance"] and ratio >= params["minRatio"]
                and (votes >= params["minVotes"] or ratio >= params.get("strongRatio", float("inf"))))
    print(f"  {row['file'].split('/')[-1][:44]:<46} best={label:<8} d={distances[best]:.3f} "
          f"ratio={ratio:.2f} votes={votes} accepted={accepted} "
          f"GO_rank={go_rank} GO_d={go_best if go_best is None else round(go_best,3)}")

# How far are GO's own prototypes from a GO clip on average, versus other labels?
print("\nmean distance to each label's prototypes, averaged over GO clips:")
go_seqs = [features[r["key"]] for r in go_all if r["key"] in features]
for label in LABELS:
    idx = [i for i, l in enumerate(refl) if l == label]
    if not idx:
        continue
    totals = []
    for seq in go_seqs:
        a = np.array(seq)
        m = mirror(a)
        ds = [min(distance(a, refs[i]), distance(m, refs[i])) for i in idx]
        totals.append(min(ds))
    print(f"  {label:<8} mean nearest {np.mean(totals):.3f}  (n={len(totals)} clips, {len(idx)} prototypes)")
