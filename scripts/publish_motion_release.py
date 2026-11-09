"""Publish a frozen motion release's held-out counts, preserving old benchmarks.

This only reads evaluation evidence and publishes integer counts. It does not
select a model, change gates, or treat Watch reference smoke tests as accuracy.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GREETINGS = {"GOOD MORNING", "GOOD AFTERNOON", "GOOD NIGHT"}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_mode(mode):
    metrics, records = mode["accepted"], mode["records"]
    per = metrics["perLabel"]
    known = [r for r in records if r["expected"] in per]
    negative = [r for r in records if r["expected"] not in per]
    if len({r["file"] for r in records}) != len(records):
        raise ValueError("Duplicate benchmark attempts")
    for label, word in per.items():
        rows = [r for r in known if r["expected"] == label]
        counts = Counter(r["outcome"] for r in rows)
        expected = {"total": len(rows), "correct": counts["correct"],
                    "wrong": counts["wrong"], "noMatch": counts["no-match"],
                    "tracked": sum(r["tracked"] for r in rows),
                    "syntheticGreeting": sum(r["syntheticGreeting"] for r in rows)}
        if word != expected or word["total"] <= 0:
            raise ValueError(f"Invalid measured counts for {label}")
        for row in rows:
            outcome = "no-match" if not row["prediction"] else "correct" if row["prediction"] == label else "wrong"
            if row["outcome"] != outcome or row["prediction"] and not row["tracked"]:
                raise ValueError("Accepted prediction/outcome disagrees with tracking")
    sums = {"attempts": sum(w["total"] for w in per.values()),
            **{key: sum(w[key] for w in per.values()) for key in ("correct", "wrong", "noMatch", "tracked")},
            "negativeAttempts": len(negative), "negativeFalse": sum(bool(r["prediction"]) for r in negative)}
    if any(metrics[key] != value for key, value in sums.items()):
        raise ValueError("Benchmark summary disagrees with per-record counts")
    if sums["correct"] + sums["wrong"] + sums["noMatch"] != sums["attempts"]:
        raise ValueError("Benchmark lost failures from the denominator")
    return sums


def make_profiles(report_path, calibration_path, deployed_path, family, config, catalog):
    report, calibration = read_json(report_path), read_json(calibration_path)
    model = config["models"][family]
    identity = digest(deployed_path)
    required = {"split": "test", "family": family, "sourcesAndParticipantsDisjoint": True,
                "testUsedForSelection": False, "watchClipsExcluded": True}
    if any(report.get(key) != value for key, value in required.items()):
        raise ValueError("Only independent, frozen test evidence can be published")
    if identity != model["checkpointSha256"] or identity != report["selected"]["checkpointSha256"]:
        raise ValueError(f"{family} deployed checkpoint differs from evaluated weights")
    if report["calibrationSha256"] != digest(calibration_path) or calibration["checkpointSha256"] != identity:
        raise ValueError("Calibration evidence identity mismatch")
    if calibration["policies"] != model["policies"]:
        raise ValueError("Deployed gates differ from the frozen benchmark")
    auxiliary = model.get("auxiliary")
    if auxiliary:
        if (digest(REPO / auxiliary["checkpoint"]) != auxiliary["checkpointSha256"]
                or report["selected"].get("auxiliarySha256") != auxiliary["checkpointSha256"]
                or calibration.get("auxiliarySha256") != auxiliary["checkpointSha256"]):
            raise ValueError("Auxiliary weights differ from the frozen benchmark")
    if any(report["selected"][key] != model[key] for key in ("preprocessorVersion", "mirrorTta", "mirrorVersion")):
        raise ValueError("Deployed feature preprocessing/mirroring differs from evaluation")
    for key in ("testUsedForCalibration", "watchClipsUsedForCalibration"):
        if calibration.get(key) is not False:
            raise ValueError("Test/Watch data cannot be used for calibration")

    profiles, evidence = {}, {}
    for mode, result in report["selected"]["modes"].items():
        if result["policy"] != model["policies"][mode] or result["policy"]["selectionSplit"] != "val":
            raise ValueError("Gates were not frozen on validation")
        sums = validate_mode(result)
        per = result["accepted"]["perLabel"]
        words = {}
        if family == "beginner":
            for label, metrics in per.items():
                matches = [item for item in catalog if item["label"] == label and "beginner" in item.get("recognitionModes", [])]
                if len(matches) != 1:
                    raise ValueError(f"Ambiguous Beginner label {label}")
                words[label] = {**metrics, "answered": metrics["correct"] + metrics["wrong"], "datasetLabel": label}
                if label in GREETINGS:
                    words[label]["note"] = ("These attempts use synthetic joined GOOD + time-of-day recordings, "
                        "not natural continuous greetings. Natural full-greeting recognition remains unverified.")
            profile_name, title = "beginner", "Beginner-79 repaired ST-GCN"
        else:
            for gloss, metrics in per.items():
                matches = [item for item in catalog if "capstone-full" in item.get("recognitionModes", [])
                           and gloss in item.get("modelGlosses", [])]
                if len(matches) != 1 or matches[0]["label"] in words:
                    raise ValueError(f"Ambiguous capstone display label for {gloss}")
                words[matches[0]["label"]] = {**metrics, "answered": metrics["correct"] + metrics["wrong"], "datasetLabel": gloss}
            profile_name = {"full": "capstoneFull", "core": "capstoneCore", "extended": "capstoneExtended"}[mode]
            title = {"full": "Full 100-word", "core": "Core 7-word", "extended": "Extended 19-word"}[mode] + " ST-GCN ensemble"
        expected_size = 79 if family == "beginner" else {"full": 100, "core": 7, "extended": 19}[mode]
        if len(words) != expected_size:
            raise ValueError("Published word coverage differs from the evaluated vocabulary")
        scope = ("Current frozen-checkpoint held-out recorded test, using validation-selected rejection gates. "
                 "All known-word attempts are counted; tracking failures count as misses. "
                 "Primary Watch reference clips are excluded, and test sources/signers are separate from train/validation. "
                 "Live-camera accuracy remains unverified. "
                 f"Unsupported signs: {sums['negativeFalse']}/{sums['negativeAttempts']} falsely accepted. "
                 "Scores are recorded accuracy, not confidence in a camera suggestion.")
        profiles[profile_name] = {
            "model": title + " · current gated recorded benchmark", "scope": scope,
            "checkpoint": deployed_path.name, "evaluatedCheckpoint": report["selected"]["checkpoint"],
            "modelSha256": identity, "preprocessorVersion": model["preprocessorVersion"],
            "mirrorTta": report["selected"]["mirrorTta"], "mirrorVersion": report["selected"]["mirrorVersion"],
            "calibrationId": config["calibrationId"], "calibrationSha256": digest(REPO / "models/motion-calibration.json"),
            "selectionSplit": "val", "testUsedForSelection": False, "watchClipsExcluded": True,
            "sourceReport": report_path.relative_to(REPO).as_posix(), "sourceReportSha256": digest(report_path),
            "vocabulary": mode, "totals": sums, "words": words,
            **({"auxiliarySha256":auxiliary["checkpointSha256"],"auxiliaryWeight":auxiliary["weights"][mode],
                "auxiliaryFeatureVersion":auxiliary["featureVersion"]} if auxiliary else {}),
        }
        evidence[profile_name] = {"checkpointSha256": identity, "calibrationEvidenceSha256": digest(calibration_path),
                                  "sourceReportSha256": digest(report_path), "totals": sums,
                                  "watchKnownExcluded": report["watchKnownExcluded"],
                                  "watchNegativeExcluded": report["watchNegativeExcluded"]}
    return profiles, evidence


def publish(report_dir):
    config = read_json(REPO / "models/motion-calibration.json")
    if config.get("selectionSplit") != "val" or any(config.get(key) is not False for key in ("testUsedForCalibration", "watchClipsUsedForCalibration")):
        raise ValueError("Invalid release selection provenance")
    path = REPO / "models/motion-word-accuracy.json"
    original = path.read_bytes()
    data = read_json(path)
    archives = {name: {k: v for k, v in data["profiles"][name].items() if k != "current"}
                for name in ("beginner", "capstoneFull")}
    catalog = read_json(REPO / "models/motion-vocabulary.json")["items"]
    profiles, evidence = {}, {}
    for family, calibration, deployed in (
        ("beginner", "beginner-repaired-balanced.json", REPO / "models/beginner-repaired-v1.pt"),
        ("capstone", "capstone-baseline-balanced.json", REPO / "third_party/microsoft_asl_citizen/capstone100-v4-ensemble.pt"),
    ):
        model = config["models"][family]
        if model.get("calibrationReport"):
            calibration = model["calibrationReport"]
        if family == "beginner":
            deployed = REPO / "models" / model["checkpoint"]
        new, sources = make_profiles(report_dir / f"heldout-{family}.json", report_dir / "calibration" / calibration,
                                     deployed, family, config, catalog)
        profiles.update(new); evidence.update(sources)
    for name, profile in profiles.items():
        if name in archives:
            data["profiles"][name]["current"] = profile
        else:
            data["profiles"][name] = {"current": profile}
    for name, archived in archives.items():
        if {k: v for k, v in data["profiles"][name].items() if k != "current"} != archived:
            raise ValueError("Archived benchmark was unexpectedly changed")
    data["currentRelease"] = {"calibrationId": config["calibrationId"],
                              "provenance": (report_dir / "current-accuracy-provenance.json").relative_to(REPO).as_posix()}
    output = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if b"\r\n" in original:
        output = output.replace("\n", "\r\n")
    path.write_bytes(output.encode("utf-8"))
    provenance = {"version": 1, "publishedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "calibrationId": config["calibrationId"], "calibrationSha256": digest(REPO / "models/motion-calibration.json"),
                  "testUsedForSelection": False, "watchClipsExcluded": True, "archivesPreserved": True,
                  "profiles": evidence,
                  "note": "Frozen held-out recorded benchmarks, not Watch clip smoke tests or physical live-camera accuracy. Failures and unsupported false accepts are retained."}
    (report_dir / "current-accuracy-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    for name, profile in profiles.items():
        print(name, json.dumps(profile["totals"]))
    return provenance


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, default=REPO / "reports/motion-repair-20261107")
    publish(parser.parse_args().report_dir.resolve())
