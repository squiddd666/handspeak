"""Validate and summarize the CUA-driven, normal-speed reference-clip tests.

This is offline report processing, not browser automation or a new accuracy
benchmark. It does not start a camera, call a model, or change published scores.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "reports/motion-virtual-camera-20261106/baseline-all-198.json"


def normalized(label: str | None) -> str:
    label = re.sub(r"[12]$", "", label or "")
    return re.sub(r"\s+", " ", re.sub(r"[-/]+", " ", label)).strip().upper()


def tracked_frames(take: dict) -> int | None:
    """Use only this route's tracking telemetry, never a previous capture.

    Daily requests contain a resampled 20-frame sequence, not a raw tracked
    frame count. An unrelated lastCapture can still be displayed in the UI.
    """
    family = take["family"]
    if family in {"capstone", "beginner"}:
        return (take.get("request") or {}).get("frames")
    capture = take.get("camera", {}).get("lastCapture") or {}
    owner = {"motion-manual": "manual", "daily-manual": "daily"}.get(family)
    return capture.get("trackedFrames") if owner and capture.get("capture") == owner else None


def assert_scalar_telemetry(value: object, key: str = "") -> None:
    if isinstance(value, dict):
        for child_key, child in value.items():
            if child_key in {"pose", "left", "right", "landmarks", "sequence"}:
                raise ValueError(f"Raw-coordinate field must not be exported: {child_key}")
            assert_scalar_telemetry(child, child_key)
    elif isinstance(value, list):
        if key == "frames":
            raise ValueError("Raw frames must not be exported")
        for child in value:
            assert_scalar_telemetry(child)


def summarize(path: Path) -> dict:
    path = path.resolve()
    if not path.is_relative_to(ROOT / "reports"):
        raise ValueError("Input must be inside the project's reports directory")
    raw = path.read_bytes()
    report = json.loads(raw)
    assert_scalar_telemetry(report)
    if report.get("schema") != 1 or report.get("recognitionLabels") != 198:
        raise ValueError("Expected the 198-label virtual-camera report")
    isolation = report["isolation"]
    if (isolation.get("host") != "127.0.0.1"
            or isolation.get("storage") != "in-memory only"
            or isolation.get("realCameraCalls") != 0
            or isolation.get("microphoneCalls") != 0):
        raise ValueError("Virtual-only isolation was not verified")
    geometry = report["geometry"]
    if geometry.get("cropping") or geometry.get("pixelFlip"):
        raise ValueError("Baseline source geometry was altered")

    manifest = json.loads((ROOT / "models/recognition-videos.json").read_text(encoding="utf-8"))
    references = {item["id"]: item for item in manifest["items"]}
    baseline = [take for take in report["attempts"] if take.get("stage") == "baseline 1×"]
    counts = Counter(take["id"] for take in baseline)
    if set(counts) != set(references) or any(count != 1 for count in counts.values()):
        raise ValueError("Baseline needs exactly one attempt for each of the 198 recognition labels")

    groups: dict[str, Counter] = defaultdict(Counter)
    words = []
    for take in baseline:
        reference = references[take["id"]]
        if not take.get("finishedAt") or take.get("rate") != 1:
            raise ValueError(f"Unfinished or non-normal-speed baseline: {take['id']}")
        if take["clip"] != reference["video"] or take["label"] != reference["label"]:
            raise ValueError(f"Wrong primary Watch clip: {take['id']}")
        digest = hashlib.sha256((ROOT / take["clip"]).read_bytes()).hexdigest()
        if digest != take["clipSha256"] or (reference.get("videoSha256")
                and digest != reference["videoSha256"]):
            raise ValueError(f"Reference clip identity changed: {take['id']}")
        correct = bool(take.get("predicted")) and normalized(take["predicted"]) == normalized(take["label"])
        if correct != take.get("correct"):
            raise ValueError(f"Outcome is inconsistent with the actual prediction: {take['id']}")
        outcome = "matched" if correct else "wrong prediction" if take.get("predicted") else "no match"
        route = take["family"] + ("/" + take["vocabulary"] if take.get("vocabulary") else "")
        tracked_count = tracked_frames(take)
        full_playback = bool(take.get("completeSourcePlayed")) or (
            take["sourceAtEnd"]["time"] >= take["sourceAtEnd"]["duration"] - 0.03
        )
        groups[route].update({"tested": 1, outcome: 1})
        response = take.get("response") or {}
        words.append({"id": take["id"], "label": take["label"], "modelRoute": route,
                      "cameraVocabulary": take.get("camera", {}).get("vocabulary"),
                      "prediction": take.get("predicted"), "outcome": outcome,
                      "status": take["status"], "trackedFrames": tracked_count,
                      "primaryClip": take["clip"], "clipSha256": digest,
                      "completeClipPlayback": full_playback,
                      "rejectionReason": response.get("rejectionReason"),
                      "suggestions": response.get("suggestions", []),
                      "checkpointSha256": response.get("checkpointSha256"),
                      "calibrationId": response.get("calibrationId")})

    outcome_counts = Counter(word["outcome"] for word in words)
    tracking_misses = sum(word["outcome"] == "no match" and "not enough" in word["status"].lower()
                          for word in words)
    summary = {
        "version": 1,
        "scope": "One normal-speed primary Watch & Learn reference-clip attempt per recognition label through the normal production capture and model prediction paths. Not held-out or live-user accuracy.",
        "sourceReport": str(path.relative_to(ROOT)).replace("\\", "/"),
        "sourceReportSha256": hashlib.sha256(raw).hexdigest(),
        "startedAt": report["startedAt"],
        "finishedAt": max(take["finishedAt"] for take in baseline),
        "indexSha256": report["indexSha256"],
        "bootstrapSha256": report["bootstrapSha256"],
        "runtimeSha256": report.get("runtimeSha256", {}),
        "activeModelSha256": report.get("activeModelSha256", {}),
        "calibrationSha256": report.get("calibrationSha256"),
        "labelsTested": len(words),
        "matched": outcome_counts["matched"],
        "wrongPrediction": outcome_counts["wrong prediction"],
        "noMatch": outcome_counts["no match"],
        "matchedPercent": round(100 * outcome_counts["matched"] / len(words), 1),
        "insufficientTrackingMisses": tracking_misses,
        "warmupsExcluded": sum(take.get("stage") == "warm-up discard" for take in report["attempts"]),
        "completeClipPlayback": sum(word["completeClipPlayback"] for word in words),
        "isolation": isolation,
        "geometry": geometry,
        "models": dict(sorted(groups.items())),
        "words": sorted(words, key=lambda word: word["label"]),
        "limitations": [
            "Reference clips are examples, not an independent test set. Some may overlap model inputs.",
            "A fixed application recording window can cut off longer clips; incomplete playback is reported, not silently excluded.",
            "Browser/hand-and-body tracking speed and sign variants can cause short clips to miss the tracking gate.",
            "Core/extended gates and the Beginner gate can refuse predictions; all refusals remain in the denominator.",
            "All 198 labels having recorded scores does not mean all 198 are verified-ready or active in one model.",
            "Post-fix camera-badge regressions are saved separately; they never replace this baseline or archived benchmark counts.",
        ],
    }
    if report.get("testSourceRecovery"):
        summary["scope"] = report["scope"]
        summary["testSourceRecovery"] = report["testSourceRecovery"]
    observations_path = path.parent / "badge-observations.json"
    if observations_path.exists():
        observations = json.loads(observations_path.read_text(encoding="utf-8"))
        assert_scalar_telemetry(observations)
        summary["cameraBadgeChecks"] = [
            {"expectedWord": item["take"]["label"], "actualPrediction": item["take"].get("predicted"),
             "stage": item["take"]["stage"], "expectedProfile": item["expectedProfile"],
             "visible": item["badge"]["visible"], "text": item["badge"]["text"],
             "scope": item["badge"]["scope"]}
            for item in observations
        ]
    ui_path = path.parent / "watch-learn-final-ui.json"
    if ui_path.exists():
        ui = json.loads(ui_path.read_text(encoding="utf-8"))
        summary["watchLearnUI"] = {key: ui[key] for key in
                                   ["url", "videoCoverage", "scoreCoverage", "recognitionButtons", "unmeasured", "camera"]}
    (path.parent / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# Motion virtual-camera clip tests", "",
             f"**{summary['labelsTested']}/198 labels tested at normal speed:** "
             f"{summary['matched']} matched, {summary['wrongPrediction']} wrong predictions, "
             f"{summary['noMatch']} no matches (**{summary['matchedPercent']}% reference matches**).", "",
             "These are reference-video smoke tests, **not independent held-out or live-user accuracy**.",
             "All 198 recognition labels now have separately sourced recorded benchmark badges; "
             "that is measurement coverage, not proof that every word recognizes reliably.", "",
             f"Virtual stream calls: {isolation['getUserMediaCalls']}. Physical camera calls: **0**. Microphone calls: **0**.",
             f"Excluded warm-ups: {summary['warmupsExcluded']}. Insufficient-tracking misses: {tracking_misses}.",
             f"Complete primary-clip playback: {summary['completeClipPlayback']}/198; the application's fixed capture window can truncate longer clips.", "",
             "## Per-model results", "", "| Actual capture route | Tested | Matched | Wrong | No match |",
             "|---|---:|---:|---:|---:|"]
    for name, metrics in summary["models"].items():
        lines.append(f"| {name} | {metrics['tested']} | {metrics['matched']} | {metrics['wrong prediction']} | {metrics['no match']} |")
    if summary.get("testSourceRecovery"):
        lines += ["", "## Interrupted source and continuation", "", summary["scope"], "",
                  "The interrupted source ledger is preserved separately. The aggregate keeps every pre-outage outcome and one continuation attempt per remaining word; it does not choose best-of retries. Both runner hashes and source-report hashes are recorded. This is not a same-protocol single-run model benchmark."]
    if summary.get("cameraBadgeChecks"):
        lines += ["", "## Post-fix camera-badge checks", "",
                  "The displayed badge follows the **actual predicted label and model family**, not the expected reference word. "
                  "The six checked contexts cover full-100, Beginner-79, default, daily, the active category pack, and core-7. "
                  "Numeric-input replays produced wrong predictions and remain failures in the separate regression report; "
                  "they are not counted as successful numeric detections. The I / ME slash-label detection displayed its Beginner benchmark. "
                  "Known numeric/slash output-label handling is also covered by the no-camera unit tests.", "",
                  "| Expected reference | Actual prediction | Badge profile | Visible recorded result |", "|---|---|---|---|"]
        for check in summary["cameraBadgeChecks"]:
            lines.append(f"| {check['expectedWord']} | {check['actualPrediction'] or '—'} | {check['expectedProfile']} | {check['text']} |")
    if summary.get("watchLearnUI"):
        lines += ["", "## Final project page", "", summary["watchLearnUI"]["videoCoverage"], "",
                  summary["watchLearnUI"]["scoreCoverage"], "",
                  "Verified in the normal project page, with the camera off. A screenshot is saved as watch-learn-updated.png. "
                  "Disposable virtual-source fixtures are separate from index.html and excluded from Git."]
    lines += ["", "## Limitations", ""] + ["* " + item for item in summary["limitations"]]
    lines += ["", "## Per-word results", "", "| Expected | Capture route | Prediction | Result |", "|---|---|---|---|"]
    for word in summary["words"]:
        lines.append(f"| {word['label']} | {word['modelRoute']} | {word['prediction'] or '—'} | {word['outcome']} |")
    lines += ["", "## Reproduce the report summary", "", "```powershell",
              "python scripts/summarize_motion_virtual_camera.py", "```", "",
              "The scalar-only source report includes clip hashes, status messages, selected model routes, "
              "and frame counts. It contains no video bytes or raw hand/body-coordinate arrays.", ""]
    (path.parent / "README.md").write_text("\n".join(lines), encoding="utf-8")
    return {key: value for key, value in summary.items() if key != "words"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    # Windows redirected stdout may use cp1252; keep console JSON ASCII-safe.
    print(json.dumps(summarize(args.report), indent=2, ensure_ascii=True))
