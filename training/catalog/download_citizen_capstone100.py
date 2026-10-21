"""Privately stream the CAPSTONE_ASL top-100 train/validation videos.

The 45.9 GB research archive is never downloaded as a whole. Raw participant
videos remain under /opt/handspeak-training and are never served by the site.
The official ASL-Citizen test split is deliberately excluded until a candidate
has been frozen from train/validation evidence.
"""
from __future__ import annotations

import concurrent.futures
import argparse
import csv
import hashlib
import json
import struct
import sys
import zipfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "daily_words"))
from remote_zip import RangeReader, URL

META = Path("/opt/handspeak-training/daily-words/metadata/ASL_Citizen/splits")
INDEX = Path("/opt/handspeak-training/daily-words/archive-index.json")
LABEL_MAP = Path(__file__).resolve().parents[2] / "third_party/capstone_asl/data/recognition_label_map_with_split_counts.csv"
ROOT = Path("/opt/handspeak-training/capstone100-retrain")


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test",action="store_true")
    args=parser.parse_args()
    root=Path("/opt/handspeak-training/capstone100-test") if args.test else ROOT
    splits=("test",) if args.test else ("train","val")
    labels = {row["gloss"] for row in csv.DictReader(LABEL_MAP.open())}
    members = {Path(name).name: name for name in json.loads(INDEX.read_text()) if name.endswith(".mp4")}
    selected = []
    for split in splits:
        for row in csv.DictReader((META / f"{split}.csv").open()):
            label = row["Gloss"]
            if label not in labels:
                continue
            filename = row["Video file"]
            selected.append({
                "label": label,
                "split": split,
                "participant": f"citizen-{row['Participant ID']}",
                "source": URL,
                "member": members[filename],
                "file": str(root / "videos" / split / label.lower() / filename),
            })
    expected=1286 if args.test else 2167
    if len(selected) != expected:
        raise ValueError(f"Expected {expected} selected clips, found {len(selected)}")

    root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(RangeReader()) as archive:
        info = {row["member"]: archive.getinfo(row["member"]) for row in selected}

    def download(row):
        path = Path(row["file"])
        if not path.exists():
            entry = info[row["member"]]
            reader = RangeReader(); reader.seek(entry.header_offset)
            header = reader.read(30)
            filename_size, extra_size = struct.unpack_from("<HH", header, 26)
            reader.seek(entry.header_offset + 30 + filename_size + extra_size)
            compressed = reader.read(entry.compress_size)
            data = zlib.decompress(compressed, -15) if entry.compress_type == 8 else compressed
            if len(data) != entry.file_size or zlib.crc32(data) & 0xffffffff != entry.CRC:
                raise ValueError(f"Archive checksum mismatch: {entry.filename}")
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".partial")
            temporary.write_bytes(data); temporary.replace(path)
        return {**row, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}

    complete = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for row in pool.map(download, selected):
            complete.append(row)
            if len(complete) % 25 == 0 or len(complete) == len(selected):
                print(f"{len(complete)}/{len(selected)} clips · {sum(x['bytes'] for x in complete)/1e9:.2f} GB", flush=True)
    manifest_name="test-manifest.json" if args.test else "development-manifest.json"
    (root / manifest_name).write_text(json.dumps(complete, indent=2) + "\n")
    print(json.dumps({
        "labels": len({row["label"] for row in complete}),
        "train": sum(row["split"] == "train" for row in complete),
        "val": sum(row["split"] == "val" for row in complete),
        "test": sum(row["split"] == "test" for row in complete),
        "bytes": sum(row["bytes"] for row in complete),
    }, indent=2))


if __name__ == "__main__":
    main()
