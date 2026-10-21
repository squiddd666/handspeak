"""Download signer-separated ASL Citizen training clips for priority words.

The official archive supports HTTP byte ranges, so this fetches selected members
without storing the 43 GiB archive. Recordings remain outside the served site.
"""
import concurrent.futures
import csv
import hashlib
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "daily_words"))
from remote_zip import RangeReader, URL

META = Path("/opt/handspeak-training/daily-words/metadata/ASL_Citizen/splits/train.csv")
INDEX = Path("/opt/handspeak-training/daily-words/archive-index.json")
ROOT = Path("/opt/handspeak-training/citizen-priority-six")
SOURCE_LABELS = {
    "HELLO": "HELLO", "BOOK": "BOOK", "HUNGRY": "HUNGRY",
    "HOME": "HOME", "FISH": "FISH", "DRINK1": "DRINK1",
    "DRINK2": "DRINK2",
}


def main():
    rows = list(csv.DictReader(META.open()))
    members = {Path(name).name: name for name in json.loads(INDEX.read_text())
               if name.endswith(".mp4")}
    selected = []
    seen = set()
    for row in sorted(rows, key=lambda item: (item["Gloss"], item["Participant ID"], item["Video file"])):
        source_label = row["Gloss"]
        if source_label not in SOURCE_LABELS:
            continue
        identity = (source_label, row["Participant ID"])
        if identity in seen:
            continue
        seen.add(identity)
        filename = row["Video file"]
        selected.append({
            "label": SOURCE_LABELS[source_label], "sourceLabel": source_label,
            "split": "train", "participant": f"citizen-{row['Participant ID']}",
            "source": URL, "member": members[filename],
            "file": str(ROOT / "videos" / source_label.lower() / filename),
        })

    ROOT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(RangeReader()) as archive:
        info = {row["member"]: archive.getinfo(row["member"]) for row in selected}

    def download(row):
        path = Path(row["file"])
        if not path.exists():
            entry = info[row["member"]]
            reader = RangeReader()
            reader.seek(entry.header_offset)
            header = reader.read(30)
            import struct, zlib
            filename_size, extra_size = struct.unpack_from("<HH", header, 26)
            reader.seek(entry.header_offset + 30 + filename_size + extra_size)
            compressed = reader.read(entry.compress_size)
            data = zlib.decompress(compressed, -15) if entry.compress_type == 8 else compressed
            if len(data) != entry.file_size or zlib.crc32(data) & 0xffffffff != entry.CRC:
                raise ValueError(f"Archive checksum mismatch: {entry.filename}")
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".partial")
            temporary.write_bytes(data)
            temporary.replace(path)
        return {**row, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    complete = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for row in pool.map(download, selected):
            complete.append(row)
            print(f"{len(complete)}/{len(selected)} {row['sourceLabel']} {row['participant']}", flush=True)
    (ROOT / "manifest.json").write_text(json.dumps(complete, indent=2) + "\n")
    print(json.dumps({label: sum(row["label"] == label for row in complete)
                      for label in sorted(SOURCE_LABELS.values())}))


if __name__ == "__main__":
    main()
