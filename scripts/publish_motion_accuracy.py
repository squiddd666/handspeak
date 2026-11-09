"""Publish existing recorded-test counts, never invented camera-accuracy scores.

Reads the local hs-eval reports, verifies the evaluated checkpoint identities,
and adds full-100 / Beginner-79 profiles without replacing older small-model
benchmarks. This does not train a model, change a threshold, or start a camera.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BEGINNER_BENCHMARK_SHA256 = "3149785c4fdd6ac18d0da1a559b767e7b8f9e6d0ba378cbf568739a8231682d7"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def state_digest(state) -> str:
    h = hashlib.sha256()
    for name, tensor in sorted(state.items()):
        h.update(name.encode())
        h.update(str(tensor.dtype).encode())
        h.update(str(tuple(tensor.shape)).encode())
        h.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def checkpoint_info(path: Path):
    import torch

    # These are the locally trained, already loaded project checkpoints.
    blob = torch.load(path, map_location="cpu", weights_only=False)
    states = [item["state_dict"] for item in blob.get("snapshots", [])] or [blob["state_dict"]]
    return blob["labels"], {
        "checkpoint": path.name,
        "sha256": digest(path),
        "snapshots": len(states),
        "stateSha256": [state_digest(state) for state in states],
    }


def rounded_count(rate: float, total: int) -> int:
    if not isinstance(total, int) or isinstance(total, bool) or total <= 0:
        raise ValueError("A measured word requires a positive integer test count")
    if not isinstance(rate, (int, float)) or not 0 <= rate <= 1:
        raise ValueError("Invalid recorded test fraction")
    correct = round(rate * total)
    # Recover an integer only when it reproduces the report's four-place ratio.
    if round(correct / total, 4) != rate:
        raise ValueError("Rounded rate does not uniquely agree with an integer count")
    return correct


def build_profiles(eval_dir: Path, catalog: list, full: dict, beginner: dict):
    full_path = REPO / "third_party/microsoft_asl_citizen/capstone100-v4-ensemble.pt"
    full_labels, full_identity = checkpoint_info(full_path)
    components = [checkpoint_info(eval_dir / name)[1] for name in full["models"]]
    if Counter(full_identity["stateSha256"]) != Counter(h for item in components for h in item["stateSha256"]):
        raise ValueError("The deployed full ensemble differs from the evaluated snapshots")
    if full.get("min_frames") != 5 or not full.get("mirror_tta") or full["checkpoints"] != full_identity["snapshots"]:
        raise ValueError("Unexpected full-100 evaluation protocol")
    rows = full["results"]
    if len(full_labels) != 100 or set(full_labels) != {row["gloss"] for row in rows}:
        raise ValueError("The recorded evaluation does not cover the full 100 labels")
    if full["clips"] != len(rows) or full["correct"] != sum(row.get("prediction") == row["gloss"] for row in rows):
        raise ValueError("Full-100 result totals disagree")
    if full["answered"] != sum(bool(row.get("prediction")) for row in rows):
        raise ValueError("Full-100 answer count disagrees")

    by_gloss = defaultdict(lambda: {"correct": 0, "total": 0, "answered": 0})
    for row in rows:
        word = by_gloss[row["gloss"]]
        word["total"] += 1
        word["correct"] += row.get("prediction") == row["gloss"]
        word["answered"] += bool(row.get("prediction"))
    full_words = {}
    for item in catalog:
        if "capstone-full" not in item.get("recognitionModes", []):
            continue
        glosses = [name for name in item.get("modelGlosses", []) if name in by_gloss]
        if len(glosses) != 1 or item["label"] in full_words:
            raise ValueError(f"Ambiguous full-model label mapping: {item['label']}")
        metrics = dict(by_gloss[glosses[0]])
        metrics["datasetLabel"] = glosses[0]
        full_words[item["label"]] = metrics
    if len(full_words) != 100 or sum(m["total"] for m in full_words.values()) != len(rows):
        raise ValueError("Full-model display-label mapping lost or duplicated test clips")

    beginner_path = eval_dir / "models/beginner-need79-v1.pt"
    beginner_labels, beginner_identity = checkpoint_info(beginner_path)
    if beginner_identity["sha256"] != BEGINNER_BENCHMARK_SHA256:
        raise ValueError("Beginner checkpoint changed; re-evaluate before publishing scores")
    if Path(beginner["checkpoint"]).name != beginner_path.name or beginner.get("split") != "test":
        raise ValueError("Wrong Beginner checkpoint or evaluation split")
    if len(beginner_labels) != 79 or set(beginner_labels) != set(beginner["perLabel"]):
        raise ValueError("Beginner evaluation does not cover the selected 79-label checkpoint")
    beginner_words = {}
    for label, metrics in sorted(beginner["perLabel"].items()):
        word = {"correct": rounded_count(metrics["top1"], metrics["total"]), "total": metrics["total"]}
        item = next((item for item in catalog if item["label"] == label and "beginner" in item.get("recognitionModes", [])), None)
        if item is None:
            raise ValueError(f"No catalog entry for Beginner label {label}")
        if label in {"GOOD MORNING", "GOOD AFTERNOON", "GOOD NIGHT"}:
            component = ", ".join(item.get("modelGlosses", []))
            word["note"] = f"This benchmark tests the isolated {component} component labeled {label}, not the complete greeting sequence."
        beginner_words[label] = word
    total = sum(m["total"] for m in beginner_words.values())
    correct = sum(m["correct"] for m in beginner_words.values())
    if total != beginner["clips"] or round(correct / total, 4) != beginner["top1"]:
        raise ValueError("Beginner per-word counts disagree with the recorded overall result")

    profiles = {
        "capstoneFull": {
            "model": "Full 100-word ST-GCN ensemble · recorded benchmark",
            "scope": "Held-out recorded test clips, full 100-word vocabulary and mirror averaging. All reported attempts are counted; clips without sufficient tracking count as misses. This is not the gated core/extended benchmark or live-camera accuracy.",
            "checkpoint": full_identity["checkpoint"],
            "modelSha256": full_identity["sha256"],
            "words": full_words,
        },
        "beginner": {
            "model": "Beginner-79 ST-GCN need79-v1 · recorded benchmark",
            "scope": "Held-out extracted landmark clips for the selected 79-label checkpoint. These scores do not measure a physical live camera; live-camera accuracy remains unverified. Greeting labels are component tests, not complete phrase tests.",
            "checkpoint": beginner_identity["checkpoint"],
            "modelSha256": beginner_identity["sha256"],
            "words": beginner_words,
        },
    }
    evidence = {
        "full": {**full_identity, "evaluatedComponents": components, "evaluatedWeightsMatch": True, "attempted": len(rows), "answered": full["answered"], "correct": full["correct"]},
        "beginner": {**beginner_identity, "attempted": total, "correct": correct, "split": "test"},
    }
    return profiles, evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-dir", type=Path, default=REPO.parent / "hs-eval")
    args = parser.parse_args()
    profile_path = REPO / "models/motion-word-accuracy.json"
    previous_bytes = profile_path.read_bytes()
    data = read_json(profile_path)
    catalog = read_json(REPO / "models/motion-vocabulary.json")["items"]
    full_path = args.eval_dir / "report-v35.json"
    beginner_path = args.eval_dir / "beginner-100/eval-need79-test.json"
    new_profiles, evidence = build_profiles(args.eval_dir, catalog, read_json(full_path), read_json(beginner_path))
    # Refresh archived counts without deleting a newer frozen-release benchmark.
    for name, profile in new_profiles.items():
        current = data["profiles"].get(name, {}).get("current")
        if current:
            profile["current"] = current
    data["profiles"].update(new_profiles)
    packs = read_json(REPO / "models/motion-categories/index.json")["groups"]
    covered = {label for profile in data["profiles"].values()
               for label in (profile.get("current") or profile).get("words", {})}
    covered.update(label for pack in packs for label in pack["labels"] if pack.get("test"))
    manifest = read_json(REPO / "models/recognition-videos.json")["items"]
    recognized = {item["label"] for item in manifest}
    missing = sorted(recognized - covered)
    if len(recognized) != 198 or missing:
        raise ValueError(f"Recorded-result coverage is incomplete: {missing}")
    output = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if b"\r\n" in previous_bytes:
        output = output.replace("\n", "\r\n")
    profile_path.write_bytes(output.encode("utf-8"))
    report_dir = REPO / "reports/recorded-word-accuracy"
    report_dir.mkdir(parents=True, exist_ok=True)
    evidence.update({
        "version": 1,
        "publishedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "recognitionLabelsWithRecordedResults": len(recognized),
        "missingLabels": missing,
        "sourceReports": [{"path": "hs-eval/report-v35.json", "sha256": digest(full_path)}, {"path": "hs-eval/beginner-100/eval-need79-test.json", "sha256": digest(beginner_path)}],
        "note": "Scores are archived recorded benchmarks, not reference-video smoke tests, live-camera accuracy, or a claim that all 198 words meet a deployable accuracy threshold. Models and thresholds were not changed.",
    })
    (report_dir / "provenance.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"Published recorded test counts for all {len(recognized)} recognition labels; no model or threshold changes.")
    print(f"Full benchmark: {evidence['full']['correct']}/{evidence['full']['attempted']} attempts, including tracking misses.")
    print(f"Beginner benchmark: {evidence['beginner']['correct']}/{evidence['beginner']['attempted']} extracted test clips.")


if __name__ == "__main__":
    main()
