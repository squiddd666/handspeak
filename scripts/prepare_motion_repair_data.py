"""Repair dataset semantics without consuming Watch clips as training data.

MORNING was overwritten as GOOD MORNING in the latest merged features even
though both are model labels. Greeting labels used isolated AFTERNOON/NIGHT
components. Restore isolated MORNING, and form explicitly marked greeting
training examples from GOOD + a component within the SAME original split.
These composites are not recordings of naturally performed phrases.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(eval_root: Path, output: Path):
    source = eval_root / "beginner-100/features-need79.jsonl"
    labels = json.loads((REPO / "models/beginner-100-label-map.json").read_text(encoding="utf-8"))["trainLabels"]
    gloss_by_file = {}
    split_by_file = {}
    for split in ("train", "val", "test"):
        with (eval_root / "cache" / f"{split}.csv").open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                gloss_by_file[row["Video file"]] = row["Gloss"]
                split_by_file[row["Video file"]] = split
    manifest = json.loads((REPO / "models/recognition-videos.json").read_text(encoding="utf-8"))
    watch_files = {s["originalFile"] for item in manifest["items"] for s in item.get("sources", [])}
    rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    seen = defaultdict(set)
    originals, components = [], defaultdict(list)
    excluded = Counter()
    for record in rows:
        row = dict(record)
        split = row.get("split")
        file = Path(row.get("file", "")).name
        if split not in {"train", "val", "test"} or not file:
            raise ValueError("Every source needs an original identity and split")
        if file in split_by_file and split != split_by_file[file]:
            raise ValueError(f"Source split changed: {file}")
        seen[file].add(split)
        if file in watch_files and split in {"train", "val"}:
            excluded[(split, "Watch source")] += 1
            continue
        if split != "train" and "augment" in file.lower():
            excluded[(split, "augmentation")] += 1
            continue
        label = row.get("label") or row.get("gloss")
        gloss = gloss_by_file.get(file) or {"GOOD MORNING": "MORNING", "GOOD AFTERNOON": "AFTERNOON", "GOOD NIGHT": "NIGHT1"}.get(label, label)
        row["sourceGloss"] = gloss
        row["syntheticGreeting"] = False
        if label in {"GOOD MORNING", "GOOD AFTERNOON", "GOOD NIGHT", "MORNING"}:
            component = "MORNING" if "MORNING" in gloss else "AFTERNOON" if "AFTERNOON" in gloss else "NIGHT"
            components[(split, component)].append(row)
            if component == "MORNING":
                row["label"] = row["gloss"] = "MORNING"
                originals.append(row)
        else:
            row["label"] = label
            originals.append(row)
    if any(len(splits) != 1 for splits in seen.values()):
        raise ValueError("A source video appears in multiple splits")
    prefixes = defaultdict(list)
    for row in originals:
        if row["label"] == "GOOD" and not row.get("error") and len(row.get("frames") or []) >= 3:
            prefixes[row["split"]].append(row)
    combined = list(originals)
    for (split, component), members in sorted(components.items()):
        choices = sorted(prefixes[split], key=lambda r: r["file"])
        if not choices:
            raise ValueError(f"No GOOD prefix in the {split} split")
        for member in members:
            same = [p for p in choices if p.get("participant") == member.get("participant")]
            prefix = (same or choices)[int(hashlib.sha256(member["file"].encode()).hexdigest()[:8], 16) % len(same or choices)]
            ok = not member.get("error") and len(member.get("frames") or []) >= 3
            combined.append({"file": f"composite::{prefix['file']}::{member['file']}",
                "label": "GOOD " + component, "gloss": "GOOD " + component, "split": split,
                "participant": member.get("participant"),
                "participants": sorted({p for p in [prefix.get('participant'), member.get('participant')] if p}),
                "duration": float(prefix.get("duration", 0)) + float(member.get("duration", 0)),
                "frames": list(prefix.get("frames") or []) + list(member.get("frames") or []) if ok else [],
                "syntheticGreeting": True, "componentFiles": [prefix["file"], member["file"]],
                "error": None if ok else "Insufficient component tracking",
                "scope": "Joined isolated recorded components, not a natural continuous phrase recording"})
    source_sets, participant_sets = defaultdict(set), defaultdict(set)
    for row in combined:
        source_sets[row["split"]].update(row.get("componentFiles") or [row["file"]])
        participant_sets[row["split"]].update(row.get("participants") or [row.get("participant")])
    for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
        if source_sets[a] & source_sets[b] or (participant_sets[a] & participant_sets[b]) - {None}:
            raise ValueError(f"Source/participant leakage between {a} and {b}")
    counts = Counter(row["label"] for row in combined if row["split"] == "train" and not row.get("error") and len(row.get("frames") or []) >= 3)
    missing = sorted(set(labels) - set(counts))
    if missing:
        raise ValueError(f"Untrained labels: {missing}")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(output)
    output.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in combined), encoding="utf-8")
    evidence = {"source": str(source), "sourceSha256": digest(source), "output": str(output), "outputSha256": digest(output),
        "labels": labels, "splits": dict(Counter(row["split"] for row in combined)),
        "trainCounts": dict(sorted(counts.items())), "untrainedLabels": missing,
        "excluded": {str(k): v for k, v in excluded.items()},
        "sourcesAndParticipantsDisjoint": True, "watchClipsUsedForTrainingOrCalibration": False,
        "greetingScope": "Synthetic concatenations of isolated GOOD + component landmark recordings, paired strictly within the original split. Natural continuous greeting accuracy remains unverified."}
    output.with_suffix(".audit.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return {k: v for k, v in evidence.items() if k not in {"labels", "trainCounts"}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-root", type=Path, default=REPO.parent / "hs-eval")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.eval_root, args.out), indent=2))
