"""Combine frozen model evidence and all-198 virtual-camera regression results.

This report never tunes a model or treats a Watch example as held-out accuracy.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REPORT_DIR = REPO / "reports/motion-repair-20261107"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def baseline_attempts(report):
    rows = [row for row in report["attempts"] if row["stage"] == "baseline 1×"]
    if len(rows) != 198 or len({r["id"] for r in rows}) != 198 or any(not r.get("finishedAt") or r.get("rate") != 1 for r in rows):
        raise ValueError("A comparison must retain one completed attempt for each of 198 labels")
    return {r["id"]: r for r in rows}


def counts(rows):
    rows = list(rows.values())
    return {"tested": len(rows), "matched": sum(r["correct"] for r in rows),
            "wrong": sum(bool(r["predicted"]) and not r["correct"] for r in rows),
            "noMatch": sum(not r["predicted"] for r in rows)}


def export(final_path):
    before_path = REPO / "reports/motion-virtual-camera-20261106/baseline-all-198.json"
    before, final = read(before_path), read(final_path)
    old, new = baseline_attempts(before), baseline_attempts(final)
    manifest = read(REPO / "models/recognition-videos.json")["items"]
    if set(old) != set(new) or set(new) != {item["id"] for item in manifest}:
        raise ValueError("Reference identities differ between before and after")
    if final["indexSha256"] != digest(REPO / "index.html"):
        raise ValueError("The tested application shell changed")
    for name, sha in final["runtimeSha256"].items():
        if digest(REPO / name) != sha:
            raise ValueError(f"Tested production file changed after fixture creation: {name}")
    config = read(REPO / "models/motion-calibration.json")
    if final["calibrationSha256"] != digest(REPO / "models/motion-calibration.json"):
        raise ValueError("Tested rejection policy changed")
    isolation = final["isolation"]
    if isolation["realCameraCalls"] != 0 or isolation["microphoneCalls"] != 0 or isolation["storage"] != "in-memory only":
        raise ValueError("Virtual-only isolation failed")
    for word in new.values():
        prior = old[word["id"]]
        if word["clipSha256"] != prior["clipSha256"] or word["clip"] != prior["clip"]:
            raise ValueError("A source clip was replaced during the comparison")
        response = word.get("response") or {}
        if response.get("checkpointSha256"):
            family = word["family"]
            if response["checkpointSha256"] != config["models"][family]["checkpointSha256"]:
                raise ValueError("The runtime did not use the frozen checkpoint")
            if response.get("calibrationId") != config["calibrationId"]:
                raise ValueError("The runtime did not use the frozen calibration")

    independent = {}
    for family in ("beginner", "capstone"):
        report = read(REPORT_DIR / f"heldout-{family}.json")
        independent[family] = {mode: {name: {k: v for k, v in report[name]["modes"][mode]["accepted"].items() if k != "perLabel"}
                                    for name in ("baseline", "selected")}
                               for mode in report["selected"]["modes"]}
    final_summary = read(final_path.parent / "summary.json")
    remaining = [w for w in final_summary["words"] if w["outcome"] != "matched"]
    transitions = Counter(("matched" if old[id]["correct"] else "wrong" if old[id]["predicted"] else "noMatch",
                           "matched" if new[id]["correct"] else "wrong" if new[id]["predicted"] else "noMatch") for id in new)
    result = {"version": 1, "calibrationId": config["calibrationId"],
              "appUrl": "http://127.0.0.1:8001/#learn",
              "scope": "Separate frozen held-out model audits and an all-198 primary-reference virtual-camera regression. These are different measurements, not physical live-user accuracy.",
              "referenceBefore": counts(old), "referenceAfter": counts(new),
              "beforeSourceSha256": digest(before_path), "afterSourceSha256": digest(final_path),
              "transitions": [{"before": a, "after": b, "count": n} for (a, b), n in sorted(transitions.items())],
              "independentModelAudits": independent,
              "remainingReferenceFailures": remaining, "isolation": isolation,
              "allWordsReliablyRecognized": False,
              "limits": [
                  "A single matching Watch reference does not prove reliable recognition of other signers.",
                  "The full-100 gate deliberately trades fewer wrong outputs for more no matches; overall recall did not improve.",
                  "Beginner unsupported false accepts increased from 166 to 174 in 1166 held-out attempts, despite fewer known-word errors.",
                  "Synthetic GOOD greeting training does not verify natural continuous greeting recognition.",
                  "Remaining failures need improved tracking or additional diverse, independently evaluated signing data, not forced expected-label outputs.",
                  "Research videos are restricted to localhost non-commercial use and have not been publicly deployed.",
              ]}
    (REPORT_DIR / "repair-summary.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (REPORT_DIR / "remaining-reference-failures.json").write_text(json.dumps({
        "scope": "Failed primary-reference virtual-camera attempts, not a training or calibration dataset.",
        "afterSourceSha256": digest(final_path), "count": len(remaining), "words": remaining,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# Motion recognition repair and all-word audit", "",
             "## What changed", "",
             "* Buffered distinct camera frames across a busy tracker, excluded countdown frames, drained inference, and bounded temporary image memory.",
             "* Fixed specialist/default routing and prevented empty-hand input from producing word predictions.",
             "* Retrained Beginner-79 with corrected MORNING and synthetic joined greeting labels, masked missing hands, and anatomical mirror averaging.",
             "* Retained the existing full-100 ensemble: the retrained candidate did not beat it on validation.",
             "* Froze checkpoint-bound rejection gates on validation only; primary Watch references were excluded from independent held-out audits.",
             "* Published exact current per-word results separately from the archived benchmarks, including 0% results and tracking misses.", "",
             "## Independent held-out recordings", "",
             "The same corrected test attempts are used in each before/after comparison. Known-word results and unsupported false accepts are separate. Tracking failures count as misses.", "",
             "| Model / setting | Attempts | Before correct / wrong / no match | After correct / wrong / no match | Unsupported false accepts: before → after |",
             "|---|---:|---|---|---|"]
    for family, modes in independent.items():
        for mode, pair in modes.items():
            b, a = pair["baseline"], pair["selected"]
            lines.append(f"| {family} / {mode} | {a['attempts']} | {b['correct']} / {b['wrong']} / {b['noMatch']} | {a['correct']} / {a['wrong']} / {a['noMatch']} | {b['negativeFalse']} → {a['negativeFalse']} / {a['negativeAttempts']} |")
    b, a = result["referenceBefore"], result["referenceAfter"]
    lines += ["", "**Tradeoff:** the full-100 recalibration reduces wrong labels but increases refusals and reduces correct acceptances. It is not an across-the-board accuracy improvement. Beginner known-word performance improves, but its unsupported false-accept count rises slightly.", "",
              "## All 198 Watch → Practice → Record checks", "",
              "Exactly one normal-speed baseline attempt per label, using the same primary reference MP4s as the earlier run. No expected label was substituted, no reviewed word was added, and no physical webcam or microphone was activated.", "",
              f"* Before: **{b['matched']} matched / {b['wrong']} wrong / {b['noMatch']} no match**.",
              f"* After: **{a['matched']} matched / {a['wrong']} wrong / {a['noMatch']} no match**.",
              f"* Complete clip playback: {final_summary['completeClipPlayback']}/198. Insufficient-tracking misses: {final_summary['insufficientTrackingMisses']}.",
              "* This is a reference-video regression, not held-out accuracy and not evidence that all 198 words are ready.", "",
              "## Remaining wrong/no-match reference words", "",
              "| Expected word | Model setting | Actual output | Result | Rejection reason | Tracked frames |",
              "|---|---|---|---|---|---:|"]
    for w in remaining:
        lines.append(f"| {w['label']} | {w['modelRoute']} | {w['prediction'] or '—'} | {w['outcome']} | {w['rejectionReason'] or '—'} | {w['trackedFrames'] if w['trackedFrames'] is not None else '—'} |")
    lines += ["", "## Evidence and access", "",
              "* `heldout-beginner.json` and `heldout-capstone.json`: scalar per-record and per-label independent audits.",
              "* `current-accuracy-provenance.json`: deployed hashes, calibration identity, source-report hashes, preserved archive confirmation.",
              "* `virtual-final/final-all-198.json`, `virtual-final/summary.json`, and `virtual-final/README.md`: full virtual-camera evidence and all 198 per-word results.",
              "* `repair-summary.json`: machine-readable comparison and remaining failure list.",
              "* `server-*-status.json` and `server-contract-tests.json`: actual updated runtime and no-hands/consent rejection checks.",
              f"* Updated local project: {result['appUrl']}. The pre-existing port-8000 process was left intact; the updated runtime uses port 8001.", "",
              "## Limitations", ""] + ["* " + limit for limit in result["limits"]]
    (REPORT_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {k: v for k, v in result.items() if k not in ("remainingReferenceFailures", "independentModelAudits", "transitions")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final-report", type=Path, default=REPORT_DIR / "virtual-final/final-all-198.json")
    print(json.dumps(export(parser.parse_args().final_report.resolve()), indent=2))
