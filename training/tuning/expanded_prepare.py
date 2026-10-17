"""Assemble the seven expanded words and measure the current recorded numbers with the
deployed JavaScript recognizer.

v5 provides DRINK / WATER / BOOK / APPLE / MILK clips with content hashes; v6 provides
FOOD / GO / HUNGRY / LIKE clips, downloaded from the official PopSign archive into
vocabulary-v6/videos/<label>/ and keyed by file path.
"""
import json
from collections import Counter
from pathlib import Path

import quickjs

SITE = Path("/opt/handspeak/repository")
TRAIN = Path("/opt/handspeak-training")
LABELS = ["DRINK", "WATER", "BOOK", "FOOD", "HUNGRY", "LIKE", "GO"]

rows = []
for row in json.loads((TRAIN / "vocabulary-v5/development-manifest.json").read_text()):
    rows.append(row)
for row in json.loads((TRAIN / "vocabulary-v5/test-manifest.json").read_text()):
    rows.append(row)
for label in ["FOOD", "GO", "HUNGRY", "LIKE"]:
    for name in ["train", "val", "test"]:
        path = TRAIN / f"vocabulary-v6/{name}-{label.lower()}-manifest.json"
        if not path.exists():
            continue
        for row in json.loads(path.read_text()):
            row = dict(row)
            row["file"] = str(TRAIN / "vocabulary-v6/videos" / label / Path(row["member"]).name)
            row["sha256"] = None
            rows.append(row)

unique, seen = [], set()
for row in rows:
    key = row.get("sha256") or row["file"]
    if key in seen:
        continue
    seen.add(key)
    unique.append(row)
print("unique clips:", len(unique), "labels:", Counter(r["label"] for r in unique))
print("splits:", Counter(r.get("split") for r in unique))
print("on disk:", sum(1 for r in unique if Path(r["file"]).exists()), "/", len(unique))
Path("/tmp/expanded-manifest.json").write_text(json.dumps(unique, separators=(",", ":")))

features = {}
for path in [TRAIN / "vocabulary-v5/development-features.json",
             TRAIN / "vocabulary-v5/test-features.json",
             TRAIN / "vocabulary-v6/development-features.json",
             TRAIN / "vocabulary-v6/test-features.json"]:
    if not path.exists():
        print("missing features:", path)
        continue
    data = json.loads(path.read_text())
    items = data if isinstance(data, list) else data.get("rows") or []
    for row in items:
        if not isinstance(row.get("sequence"), list):
            continue
        if row.get("sha256"):
            features[("sha", row["sha256"])] = row["sequence"]
        if row.get("file"):
            features[("file", row["file"])] = row["sequence"]
        if row.get("member"):
            features[("member", Path(row["member"]).name)] = row["sequence"]
print("feature sequences:", len(features))


def sequence_for(row):
    if row.get("sha256") and ("sha", row["sha256"]) in features:
        return features[("sha", row["sha256"])]
    if ("file", row["file"]) in features:
        return features[("file", row["file"])]
    return features.get(("member", Path(row.get("member", "")).name))


model = json.loads((SITE / "models/asl-extra-words.json").read_text())
js = quickjs.Context()
js.eval((SITE / "gesture-model.js").read_text().replace("export ", ""))
js.eval((SITE / "temporal-motion/motion-model.js").read_text().replace("export ", ""))
js.eval("var model=" + json.dumps(model, separators=(",", ":")) + ";")
js.eval("var parameters=model.parameters;")

test = [r for r in unique if r.get("split") == "test"]
print("\ntest clips:", len(test), Counter(r["label"] for r in test))
per_word = Counter()
false = untracked = 0
for row in test:
    seq = sequence_for(row)
    if not seq:
        untracked += 1
        per_word[(row["label"], "UNTRACKED")] += 1
        continue
    value = js.eval("JSON.stringify(recognizeMotion(" + json.dumps(seq) + ",model.samples,parameters))")
    prediction = json.loads(value)
    prediction = prediction["label"] if prediction else None
    if row["label"] in LABELS:
        outcome = "hit" if prediction == row["label"] else ("REJECTED" if prediction is None else "WRONG")
        per_word[(row["label"], outcome)] += 1
    elif prediction is not None:
        false += 1
print(f"untracked {untracked}, unsupported false accepts {false}")
print("current recorded numbers (uniform features, shipped model):")
hits = totals = 0
for label in LABELS:
    counts = {o: c for (label_, o), c in per_word.items() if label_ == label}
    hit = counts.get("hit", 0)
    total = sum(counts.values())
    hits += hit
    totals += total
    print(f"  {label:<8} {hit:>2}/{total} ({round(100*hit/max(1,total),1)}%)  {counts}")
print(f"  total {hits}/{totals} ({round(100*hits/max(1,totals),1)}%)")
