"""Fetch only pinned, hash-verified ASL FBXs; never clone the full archive.

Run with normal Python, then run retarget_studio_galt.py inside Blender.
Raw FBXs are cached outside the website and are not needed by the browser.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.parse
import urllib.request


def default_cache(commit: str) -> Path:
    base = Path(os.environ["LOCALAPPDATA"]) / "HandSpeak" if os.environ.get("LOCALAPPDATA") else Path.home() / ".cache" / "handspeak"
    return base / "mocap-cache" / "studio-galt" / commit


def source_url(commit: str, path: str) -> str:
    return "https://raw.githubusercontent.com/StudioGalt/Sign-Language-Mocap-Archive/" + commit + "/" + urllib.parse.quote(path, safe="/")


def fetch(url: str, limit: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "HandSpeak-Kai-mocap-import"})
    with urllib.request.urlopen(request, timeout=45) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Download exceeded its expected size: " + url)
    return data


def verify(data: bytes, item: dict) -> None:
    blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    if len(data) != item["bytes"] or blob != item["gitBlob"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise ValueError("Source size/hash mismatch for " + item["id"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("studio-galt-sources.json"))
    parser.add_argument("--cache", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    commit = manifest["commit"]
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Pin a full Git commit, not a mutable branch")
    cache = (args.cache or default_cache(commit)).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    downloaded = []
    for item in manifest["clips"]:
        if not re.fullmatch(r"[a-z0-9-]+", item["id"]):
            raise ValueError("Invalid clip ID")
        target = cache / (item["id"] + ".fbx")
        url = source_url(commit, item["path"])
        data = target.read_bytes() if target.exists() else fetch(url, item["bytes"])
        verify(data, item)
        if not target.exists():
            target.write_bytes(data)
        downloaded.append({**item, "file": str(target), "url": url})
        print(f"{item['label']}: {len(data):,} bytes, SHA-256 verified")
    for name in ["LICENSE", "README.md"]:
        target = cache / name
        if not target.exists():
            target.write_bytes(fetch(source_url(commit, name), 100_000))
    report = {**manifest, "clips": downloaded}
    (cache / "manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Cache: " + str(cache))


if __name__ == "__main__":
    main()
