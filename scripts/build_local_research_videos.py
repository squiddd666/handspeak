"""Export the missing Watch & Learn references for the localhost research demo.

Uses existing ASL Citizen caches only; never downloads or republishes videos.
Preserves the original 51 references and their existing 3D reconstructions.
Run --dry-run first, then --update-catalog to publish a completely built library.
ASL Citizen media is restricted to local, non-commercial research by its terms.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_URL = "https://www.microsoft.com/en-us/research/project/asl-citizen/"
TERMS_URL = PROJECT_URL + "dataset-license/"
DEFAULT = ["HELLO", "THANK YOU", "PLEASE", "YES", "NO", "FINISH"]
EXTRA = ["DRINK", "WATER", "BOOK", "FOOD", "HUNGRY", "LIKE", "GO"]
DAILY = ["NAME", "HOME", "HAVE", "WANT", "LOVE"]
CORE = ["BELT", "EAT", "EMPTY", "PEG", "SOCCER", "SQUEEZE", "VLOG"]
EXTENDED = ["BASEBALLCAP", "DEAF", "DEMAND", "DRAG", "DUCK", "EDIT", "LOCK",
            "MECHANIC", "MICROSCOPE", "OTHER", "PARTY", "WHATFOR"]
GREETINGS = {"GOOD MORNING", "GOOD AFTERNOON", "GOOD NIGHT"}
CACHE_DIRS = ["cache/videos", "cache/train-val", "beginner-100/clips",
              "daily-words/videos", "daily-words/pack-clips"]


def friendly(gloss: str) -> str:
    return re.sub(r"[12]$", "", gloss).replace("-", " ").replace("/", " / ")


def slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def norm(label: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", label.upper())


def recognition_labels() -> tuple[dict, dict]:
    modes, glosses = defaultdict(set), defaultdict(set)
    with (ROOT / "third_party/capstone_asl/data/recognition_label_map_with_split_counts.csv").open(newline="") as stream:
        for row in csv.DictReader(stream):
            label = friendly(row["gloss"])
            modes[label].add("capstone-full")
            glosses[label].add(row["gloss"])
    beginner = json.loads((ROOT / "models/beginner-100-label-map.json").read_text(encoding="utf-8"))
    for item in beginner["entries"]:
        modes[item["label"]].add("beginner")
        glosses[item["label"]].update(item["citizenGlosses"])
    for name, labels in (("default", DEFAULT), ("extra", EXTRA), ("daily", DAILY)):
        for label in labels:
            modes[label].add(name)
    packs = json.loads((ROOT / "models/motion-categories/index.json").read_text(encoding="utf-8"))
    for pack in packs["groups"]:
        for label in pack["labels"]:
            modes[label].add("category")
    for label in CORE:
        modes[label].add("capstone-core")
    for label in CORE + EXTENDED:
        modes[label].add("capstone-extended")
    if len(modes) != 198:
        raise ValueError(f"Expected 198 distinct recognition labels, found {len(modes)}")
    return dict(modes), dict(glosses)


def cached_rows(cache_root: Path) -> list[dict]:
    files = {}
    for directory in CACHE_DIRS:
        for path in sorted((cache_root / directory).rglob("*.mp4")):
            files.setdefault(path.name, path)
    rows = []
    for split in ("test", "val", "train"):
        with (cache_root / "cache" / f"{split}.csv").open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                path = files.get(row["Video file"])
                if path:
                    rows.append({"path": path, "originalFile": row["Video file"],
                                 "participant": row["Participant ID"], "gloss": row["Gloss"],
                                 "lexCode": row["ASL-LEX Code"], "split": split})
    order = {"test": 0, "val": 1, "train": 2}
    return sorted(rows, key=lambda row: (order[row["split"]], row["gloss"], row["originalFile"]))


def plan(cache_root: Path) -> dict:
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    durations = {}

    def usable(row: dict) -> bool:
        path = row["path"]
        if path not in durations:
            durations[path] = video_duration(ffmpeg, path)
        # A decodable, four-frame cached download is not a learning reference.
        return durations[path] >= 1.0

    catalog = json.loads((ROOT / "models/motion-vocabulary.json").read_text(encoding="utf-8"))
    existing = {item["label"]: item for item in catalog["items"]}
    modes, model_glosses = recognition_labels()
    rows = cached_rows(cache_root)
    good = [row for row in rows if row["gloss"] == "GOOD"]
    items, missing = [], []
    for label in sorted(modes):
        item_id = existing.get(label, {}).get("id") or slug(label)
        legacy = f"media/signs/{item_id}.mp4"
        entry = {"id": item_id, "label": label, "recognitionModes": sorted(modes[label]),
                 "modelGlosses": sorted(model_glosses.get(label, []))}
        if (ROOT / legacy).is_file():
            entry.update(kind="existing-local", video=legacy, referenceOnly=False, localResearchOnly=False)
        else:
            glosses = model_glosses.get(label) or {
                row["gloss"] for row in rows if norm(friendly(row["gloss"])) == norm(label)}
            candidates = [row for row in rows if row["gloss"] in glosses]
            if not candidates:
                missing.append({"label": label, "glosses": sorted(glosses)})
                continue
            selected_row = next((row for row in candidates if usable(row)), None)
            if selected_row is None:
                raise ValueError(f"No complete, at-least-one-second cached recording for {label}")
            selected = [selected_row]
            note = "Isolated ASL Citizen reference matched to the model's dataset gloss. Sign variants and context may differ."
            if label in GREETINGS:
                if not good:
                    raise ValueError("No cached GOOD recording for the greeting learning sequences")
                good_sources = [row for row in good if usable(row)]
                if not good_sources:
                    raise ValueError("No usable GOOD recording for greeting sequences")
                same_signer = next((row for row in good_sources if row["participant"] == selected[0]["participant"]), good_sources[0])
                selected.insert(0, same_signer)
                component = label.removeprefix("GOOD ")
                note = (f"Learning sequence: GOOD, then {component}, joined from two complete isolated recordings; "
                        f"not a continuous phrase performance. The legacy Beginner checkpoint trained {label} "
                        f"on {component} only. Repaired Beginner weights use synthetic joined greeting training; "
                        f"natural continuous full-greeting recognition remains unverified.")
            entry.update(kind="research-local", video=f"media/research-signs/{item_id}.mp4",
                         referenceOnly=True, localResearchOnly=True,
                         sequence=label in GREETINGS, referenceNote=note, sources=selected)
        items.append(entry)
    if missing:
        raise ValueError(f"Missing cached sources: {json.dumps(missing)}")
    counts = {"labels": len(items), "existingLocal": sum(x["kind"] == "existing-local" for x in items),
              "researchLocal": sum(x["kind"] == "research-local" for x in items)}
    if counts != {"labels": 198, "existingLocal": 51, "researchLocal": 147}:
        raise ValueError(f"Unexpected reference coverage: {counts}")
    if len({item["id"] for item in items}) != len(items):
        raise ValueError("Conflicting vocabulary ids")
    return {"version": 1, "language": "ASL", "checkedDate": date.today().isoformat(),
            "counts": counts, "simultaneousRecognition": False,
            "scope": "References for separate existing recognition vocabularies; not a unified 198-label recognizer.",
            "attribution": {"source": "ASL Citizen (Microsoft Research)", "url": PROJECT_URL,
                            "termsUrl": TERMS_URL, "use": "Local non-commercial research only. No public redistribution.",
                            "archiveUrl": "https://download.microsoft.com/download/b/8/8/b88c0bae-e6c1-43e1-8726-98cf5af36ca4/ASL_Citizen.zip"},
            "items": items}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def video_duration(ffmpeg: str, path: Path) -> float:
    output = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True, text=True, check=False).stderr
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", output)
    if not match:
        raise ValueError(f"No video duration: {path}")
    return int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3])


def export(entry: dict, ffmpeg: str) -> dict:
    output = ROOT / entry["video"]
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.stem + ".building.mp4")
    sources = []
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
    for row in entry["sources"]:
        path = row["path"]
        source = {key: value for key, value in row.items() if key != "path"}
        source.update(sha256=sha256(path), duration=video_duration(ffmpeg, path))
        sources.append(source)
        command += ["-i", str(path)]
    transform = "scale=640:480:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=640:480:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,setpts=PTS-STARTPTS"
    if len(sources) == 1:
        command += ["-map", "0:v:0", "-vf", transform]
    else:
        filters = [f"[{i}:v:0]{transform}[v{i}]" for i in range(len(sources))]
        filters.append("".join(f"[v{i}]" for i in range(len(sources))) + f"concat=n={len(sources)}:v=1:a=0[out]")
        command += ["-filter_complex", ";".join(filters), "-map", "[out]"]
    command += ["-an", "-c:v", "libx264", "-profile:v", "main", "-pix_fmt", "yuv420p",
                "-crf", "23", "-preset", "fast", "-threads", "1", "-movflags", "+faststart", str(temporary)]
    subprocess.run(command, check=True, capture_output=True)
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-xerror", "-i", str(temporary),
                    "-map", "0:v:0", "-f", "null", "-"], check=True, capture_output=True)
    duration = video_duration(ffmpeg, temporary)
    temporary.replace(output)
    return {**entry, "sources": sources, "videoSha256": sha256(output), "bytes": output.stat().st_size,
            "duration": duration,
            "changes": "Audio removed; complete source motion retained without trimming; fit/padded to 640×480, 30 fps, H.264/yuv420p with faststart. "
                       + ("Two isolated clips concatenated as an explicitly labelled learning sequence." if len(sources) > 1 else "No phrase synthesis.")}


def update_catalog(manifest: dict) -> tuple[int, int]:
    path = ROOT / "models/motion-vocabulary.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    by_label = {item["label"]: item for item in catalog["items"]}
    added = 0
    if not any(category["id"] == "capstone-100" for category in catalog["categories"]):
        catalog["categories"].append({"id": "capstone-100", "name": "100-word ASL model"})
    for reference in manifest["items"]:
        label, modes = reference["label"], reference["recognitionModes"]
        item = by_label.get(label)
        if item is None:
            item = {"id": reference["id"], "label": label, "categories": [], "cameraGroups": [],
                    "sourceLabel": None, "sourceVersion": None, "note": "",
                    "learningUrl": PROJECT_URL, "learningScope": "ASL Citizen source and terms"}
            catalog["items"].append(item)
            by_label[label] = item
            added += 1
        if "capstone-full" in modes and "capstone-100" not in item["categories"]:
            item["categories"].append("capstone-100")
        if "beginner" in modes and "beginner-100" not in item["categories"]:
            item["categories"].append("beginner-100")
        if item.get("recognition") not in {"default-preview", "existing-preview", "daily-preview", "category-preview"}:
            item["recognition"] = "capstone-preview" if "capstone-full" in modes else "beginner-preview" if "beginner" in modes else "not-pretrained"
        item.update(video=reference["video"], recognitionModes=modes, modelGlosses=reference["modelGlosses"],
                    referenceOnly=reference["referenceOnly"], localResearchOnly=reference["localResearchOnly"])
        if reference["kind"] == "research-local":
            item.update(videoSource="ASL Citizen · local research", referenceNote=reference["referenceNote"],
                        videoTermsUrl=TERMS_URL)
    catalog["recognitionVideoCoverage"] = {**manifest["counts"], "manifest": "models/recognition-videos.json",
                                          "simultaneousRecognition": False}
    write_json(path, catalog)
    return added, len(catalog["items"])


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".building")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, default=ROOT.parent / "hs-eval")
    parser.add_argument("--output", type=Path, default=ROOT / "models/recognition-videos.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--update-catalog", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    manifest = plan(args.cache_root)
    if args.dry_run:
        print(json.dumps({"counts": manifest["counts"], "sources": [{"label": item["label"],
              "glosses": [row["gloss"] for row in item.get("sources", [])],
              "files": [row["originalFile"] for row in item.get("sources", [])]}
              for item in manifest["items"] if item["kind"] == "research-local"]}, indent=2))
        return
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    exported = {}
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 4))) as pool:
        futures = {pool.submit(export, item, ffmpeg): item for item in manifest["items"] if item["kind"] == "research-local"}
        for future in as_completed(futures):
            item = future.result()
            exported[item["id"]] = item
            print(f"{len(exported):3}/147 {item['label']} · {item['duration']:.2f}s · decoded", flush=True)
    manifest["items"] = [exported.get(item["id"], item) for item in manifest["items"]]
    write_json(args.output, manifest)
    added, total = update_catalog(manifest) if args.update_catalog else (0, 0)
    print(json.dumps({"output": str(args.output.resolve()), "counts": manifest["counts"],
                      "catalogAdded": added, "catalogEntries": total}), flush=True)


if __name__ == "__main__":
    main()
