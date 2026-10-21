#!/usr/bin/env python3
"""Export gloss-only vocabulary files for the ASL datasets named by SignBart.

This does not manufacture SignBart checkpoint mappings. WLASL preserves the
official annotation order used for its standard prefix subsets. ASL Citizen
uses the sorted training-gloss order used by Microsoft's baseline loader.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def write_vocabulary(output: Path, stem: str, labels: list[str], source: str) -> None:
    if len(labels) != len(set(labels)):
        raise ValueError(f"{stem} contains duplicate labels")
    payload = {
        "dataset": stem,
        "source": source,
        "count": len(labels),
        "labels": labels,
        "label2id": {label: index for index, label in enumerate(labels)},
        "id2label": {str(index): label for index, label in enumerate(labels)},
    }
    (output / f"{stem}.json").write_text(json.dumps(payload, indent=2) + "\n")
    (output / f"{stem}.txt").write_text("\n".join(labels) + "\n")
    with (output / f"{stem}.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["class_id", "gloss"])
        writer.writerows(enumerate(labels))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wlasl", type=Path, required=True)
    parser.add_argument("--citizen-train", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    annotations = json.loads(args.wlasl.read_text())
    wlasl = [entry["gloss"].strip() for entry in annotations]
    if len(wlasl) != 2000:
        raise ValueError(f"expected 2,000 WLASL labels, found {len(wlasl)}")

    with args.citizen_train.open(newline="") as handle:
        citizen = sorted({row["Gloss"].strip() for row in csv.DictReader(handle)})
    if len(citizen) != 2731:
        raise ValueError(f"expected 2,731 ASL Citizen labels, found {len(citizen)}")

    wlasl_source = "WLASL_v0.3 annotation gloss order"
    for size in (100, 300, 1000, 2000):
        write_vocabulary(args.output, f"wlasl-{size}", wlasl[:size], wlasl_source)
    write_vocabulary(
        args.output,
        "asl-citizen-2731",
        citizen,
        "ASL Citizen training split, alphabetically sorted like the Microsoft baseline loader",
    )
    # Dataset capitalization differs, so merge on a case-insensitive key and
    # prefer ASL Citizen's spelling when a gloss occurs in both datasets.
    combined_by_key = {label.casefold(): label for label in wlasl}
    combined_by_key.update({label.casefold(): label for label in citizen})
    combined = sorted(combined_by_key.values(), key=str.casefold)
    write_vocabulary(
        args.output,
        "combined-asl-glosses",
        combined,
        "Union of WLASL-2000 and ASL Citizen-2731; not a checkpoint class map",
    )


if __name__ == "__main__":
    main()
