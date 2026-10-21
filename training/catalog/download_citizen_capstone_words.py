"""Download development clips for catalog words covered by CAPSTONE_ASL.

Uses official ASL Citizen train and validation participants only. Test media is
not opened before a candidate is frozen. Raw recordings stay outside the site.
"""
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
ROOT = Path("/opt/handspeak-training/citizen-capstone-nine")
LABELS = {
    "BABY2": "BABY", "HOSPITAL1": "HOSPITAL", "NIGHT1": "NIGHT",
    "CONFUSED1": "CONFUSED", "FINE1": "FINE", "MEAT1": "MEAT",
    "BREAKFAST1": "BREAKFAST", "LUNCH1": "LUNCH", "DINNER1": "DINNER",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true",
                        help="Download the untouched test partition after model freeze")
    args = parser.parse_args()
    root = Path("/opt/handspeak-training/citizen-capstone-nine-test") if args.test else ROOT
    splits = ("test",) if args.test else ("train", "val")
    members = {Path(name).name: name for name in json.loads(INDEX.read_text())
               if name.endswith(".mp4")}
    selected = []
    for split in splits:
        rows = list(csv.DictReader((META / f"{split}.csv").open()))
        seen = set()
        for row in sorted(rows, key=lambda item: (item["Gloss"], item["Participant ID"],
                                                   item["Video file"])):
            source_label = row["Gloss"]
            if source_label not in LABELS:
                continue
            identity = (source_label, row["Participant ID"])
            if identity in seen:
                continue
            seen.add(identity)
            filename = row["Video file"]
            selected.append({"label": LABELS[source_label], "sourceLabel": source_label,
                             "split": split,
                             "participant": f"citizen-{row['Participant ID']}",
                             "source": URL, "member": members[filename],
                             "file": str(root / "videos" / split /
                                         source_label.lower() / filename)})
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
        return {**row, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    complete = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for row in pool.map(download, selected):
            complete.append(row)
            print(f"{len(complete)}/{len(selected)} {row['split']} {row['sourceLabel']}",
                  flush=True)
    (root / "manifest.json").write_text(json.dumps(complete, indent=2) + "\n")
    print(json.dumps({label: {split: sum(row["label"] == label and row["split"] == split
                                         for row in complete)
                               for split in splits}
                      for label in LABELS.values()}, indent=2))


if __name__ == "__main__":
    main()
