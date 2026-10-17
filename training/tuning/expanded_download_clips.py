"""Download the PopSign clips described by vocabulary-v6 manifests (range requests)."""
import http.client
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

TRAIN = Path("/opt/handspeak-training/vocabulary-v6")
LABELS = ["FOOD", "GO", "HUNGRY", "LIKE"]


def request(url, offset, size):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "signdata.cc.gatech.edu":
        raise ValueError("Only the official archive is allowed")
    connection = http.client.HTTPSConnection(parsed.netloc, timeout=60)
    try:
        connection.request("GET", parsed.path,
                           headers={"Range": f"bytes={offset}-{offset + size - 1}"})
        response = connection.getresponse()
        if response.status != 206:
            raise ValueError(f"unexpected status {response.status}")
        data = response.read(size + 1)
        if len(data) != size:
            raise ValueError("incomplete range")
        return data
    finally:
        connection.close()


rows = []
for label in LABELS:
    for name in ["train", "val", "test"]:
        path = TRAIN / f"{name}-{label.lower()}-manifest.json"
        if path.exists():
            rows.extend(json.loads(path.read_text()))
seen, unique = set(), []
for row in rows:
    key = (row["source"], row["member"])
    if key in seen:
        continue
    seen.add(key)
    unique.append(row)
print("clips to fetch:", len(unique), flush=True)


def fetch(row):
    target = TRAIN / "videos" / row["label"] / Path(row["member"]).name
    if target.exists() and target.stat().st_size == row["size"]:
        return f"cached {row['label']}"
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".partial")
    temp.write_bytes(request(row["source"], row["offset"], row["size"]))
    temp.replace(target)
    return f"fetched {row['label']} {target.name}"


done = 0
with ThreadPoolExecutor(max_workers=3) as pool:
    for message in pool.map(fetch, unique):
        done += 1
        if done % 12 == 0:
            print(f"{done}/{len(unique)}", flush=True)
print("complete:", len(unique), flush=True)
