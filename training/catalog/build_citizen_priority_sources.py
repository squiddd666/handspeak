"""Build immutable experiment inputs from WLASL + ASL Citizen train data."""
import json
from pathlib import Path

ROOT = Path("/opt/handspeak-training/citizen-priority-six")
SOURCE = ROOT / "development-features.json"
OUT = Path("/opt/handspeak-training")


def main():
    rows = json.loads(SOURCE.read_text())
    # Keep the new corpus from overwhelming the established camera-domain
    # examples. Selection is deterministic and independent of outcomes.
    balanced = []
    citizen_counts = {}
    for row in rows:
        if str(row.get("participant", "")).startswith("citizen-"):
            label = row["label"]
            limit = 3 if label in ("DRINK1", "DRINK2") else 6
            if citizen_counts.get(label, 0) >= limit:
                continue
            citizen_counts[label] = citizen_counts.get(label, 0) + 1
        balanced.append(row)
    for word in ("HELLO", "BOOK", "HUNGRY", "HOME", "FISH"):
        target = OUT / f"priority-citizen-balanced-{word.lower()}-source.json"
        target.write_text(json.dumps(balanced, separators=(",", ":")))
        print(target)
    # The source dataset documents two DRINK variants. Both produce the same
    # website word, while provenance remains available in sourceLabel.
    drink = []
    for row in balanced:
        item = dict(row)
        if item["label"] in ("DRINK1", "DRINK2"):
            item["label"] = "DRINK"
        drink.append(item)
    target = OUT / "priority-citizen-balanced-drink-source.json"
    target.write_text(json.dumps(drink, separators=(",", ":")))
    print(target)


if __name__ == "__main__":
    main()
