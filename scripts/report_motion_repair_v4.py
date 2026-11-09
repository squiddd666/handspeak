"""Account for every reference result while keeping rejected candidates offline.

This is offline evidence processing. It never changes weights, rejection gates,
published accuracy, user messages, or the application used by the running test.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

try:
    from .report_motion_repair import baseline_attempts, counts
    from .summarize_motion_virtual_camera import normalized, summarize
except ImportError:
    from report_motion_repair import baseline_attempts, counts
    from summarize_motion_virtual_camera import normalized, summarize

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "reports/motion-repair-v4-20261107"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def outcome(take):
    return "matched" if take["correct"] else "wrong" if take.get("predicted") else "no match"


def diagnose(take):
    if take["correct"]:
        return "matched"
    if take.get("predicted"):
        return "accepted wrong label"
    status = take.get("status", "").lower()
    if "not enough" in status or "could not warm up" in status:
        return "insufficient tracking"
    response = take.get("response") or {}
    suggestions = response.get("suggestions") or []
    if suggestions:
        return ("correct top suggestion rejected" if normalized(suggestions[0]["label"]) == normalized(take["label"])
                else "competing top suggestion rejected")
    return "no accepted manual match" if take["family"] in {"motion-manual", "daily-manual"} else "capture or server failure"


def transitions(old, new):
    if set(old) != set(new):
        raise ValueError("Before/after reference IDs differ")
    results = []
    for key in sorted(new):
        a, b = old[key], new[key]
        if any(a[field] != b[field] for field in ("label", "clip", "clipSha256", "family", "vocabulary")):
            raise ValueError("A primary reference or capture route changed")
        results.append({"id": key, "label": b["label"], "before": outcome(a), "after": outcome(b),
                        "prediction": b.get("predicted"), "diagnosis": diagnose(b)})
    return results


def verify_runtime(final, config):
    identities = dict(final["runtimeSha256"])
    identities.update({"index.html": final["indexSha256"], "models/motion-calibration.json": final["calibrationSha256"]})
    for name, digest in identities.items():
        if sha(ROOT / name) != digest:
            raise ValueError(f"Tested runtime changed: {name}")
    for family, profile in config["models"].items():
        if final["activeModelSha256"][family] != profile["checkpointSha256"]:
            raise ValueError("Fixture base checkpoint identity differs")
        auxiliary = profile.get("auxiliary")
        if auxiliary:
            if sha(ROOT / auxiliary["checkpoint"]) != auxiliary["checkpointSha256"]:
                raise ValueError("Active auxiliary checkpoint changed")
            if final["activeAuxiliaryModelSha256"][family] != auxiliary["checkpointSha256"]:
                raise ValueError("Fixture auxiliary checkpoint identity differs")
    for take in baseline_attempts(final).values():
        response = take.get("response") or {}
        if not response.get("checkpointSha256"):
            continue
        profile = config["models"][take["family"]]
        if response["checkpointSha256"] != profile["checkpointSha256"] or response.get("calibrationId") != config["calibrationId"]:
            raise ValueError("The server used a stale checkpoint or policy")
        auxiliary = profile.get("auxiliary")
        mode = take.get("vocabulary") or "full"
        if auxiliary and auxiliary["weights"].get(mode, 0):
            if response.get("auxiliarySha256") != auxiliary["checkpointSha256"] or response.get("auxiliaryWeight") != auxiliary["weights"][mode]:
                raise ValueError("The server used a stale auxiliary checkpoint or weight")


def report(root=DEFAULT):
    raw = root / "virtual-final/final-all-198.json"
    summarize(raw)  # Validates completion, clip hashes, actual predictions and isolation.
    final, summary = read(raw), read(raw.parent / "summary.json")
    config = read(ROOT / "models/motion-calibration.json")
    verify_runtime(final, config)
    old = baseline_attempts(read(ROOT / "reports/motion-repair-v3-20261107/virtual-final/final-all-198.json"))
    new = baseline_attempts(final)
    changes = transitions(old, new)
    remaining = [dict(word, diagnosis=diagnose(new[word["id"]])) for word in summary["words"] if word["outcome"] != "matched"]
    gates = read(root / "heldout-gates.json")
    manual = read(root / "candidates/manual-24.validation.json")
    if config != read(root / "baseline-v3.json"):
        raise ValueError("This report expects the retained v3 release")
    if any(gate["eligible"] for gate in gates.values()):
        raise ValueError("Candidate promotion needs separate installation accounting")
    result = {"version": 1, "before": counts(old), "after": counts(new), "calibrationId": config["calibrationId"],
              "installedModels": "v3 retained; no v4 candidate promoted", "captureChange": "Require a finite body pose during warm-up before server-model recording starts",
              "scope": summary["scope"], "sourceReportSha256": sha(raw), "candidateDeploymentGates": gates,
              "manualCandidate": {"deployed": False, "heldoutTested": False, "validation": manual["validation"]},
              "failureDiagnosisCounts": dict(Counter(word["diagnosis"] for word in remaining)),
              "transitions": changes, "recoveredMatches": [r for r in changes if r["before"] != "matched" and r["after"] == "matched"],
              "previousMatchRegressions": [r for r in changes if r["before"] == "matched" and r["after"] != "matched"],
              "remainingFailures": remaining, "allWordsReliablyFixed": False, "liveCameraAccuracyVerified": False}
    if final.get("testSourceRecovery"):
        result["testSourceRecovery"] = final["testSourceRecovery"]
        result["scope"] = final["scope"]
    for name, value in (("repair-summary.json", result), ("remaining-reference-failures.json", remaining),
                        ("previous-match-regressions.json", result["previousMatchRegressions"])):
        (root / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (root / "remaining-reference-failures.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["label", "modelRoute", "prediction", "outcome", "diagnosis", "rejectionReason", "trackedFrames", "status"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(remaining)
    b, a = result["before"], result["after"]
    lines = ["# Targeted repair v4: frozen candidates and capture regression", "",
             "The deployed v3 weights and calibration remain unchanged. Both v4 body-model candidates failed promotion; the manual candidate remains an untested experiment.", "",
             "The capture fix requires an actual finite body pose during warm-up. Blank callbacks no longer count as readiness. This does not force a practice label or relax a rejection gate.", "",
             "## All 198 normal-speed primary-reference checks", "",
             f"* Previous: {b['matched']} matched / {b['wrong']} incorrect / {b['noMatch']} no match.",
             f"* Current: {a['matched']} matched / {a['wrong']} incorrect / {a['noMatch']} no match.",
             f"* Recovered matches: {len(result['recoveredMatches'])}; previous-match regressions: {len(result['previousMatchRegressions'])}.",
             f"* Complete playback: {summary['completeClipPlayback']}/198. Physical camera and microphone calls: zero.",
             "* Exactly one attempt per label, with unchanged clips and routes. These are reference regressions, not independent live-user accuracy; all misses remain in the denominator.", "",
             "## Candidate decision", "",
             "Beginner's reused held-out audit reduced wrong predictions from 28 to 21, but correct matches fell from 502 to 490. It failed the no-coverage-regression gate. Full-100 failed the all-mode validation gate. Neither is installed.",
             f"The hand-only manual experiment matched {manual['validation']['correct']}/{manual['validation']['attempts']} validation clips, with {manual['validation']['wrong']} wrong and {manual['validation']['noMatch']} no match. It has no held-out comparison against existing routes and is not installed.", "",
             "## Remaining work", "",
             "Tracking misses need complete, usable hand/body capture. Confusing signs need independent signer/variant data and body-location-aware recognition. A correct but rejected suggestion is not fixed by blindly lowering thresholds; validate coverage and both named-word and unsupported-sign errors before promotion.", "",
             "| Word | Route | Actual output | Diagnosis |", "|---|---|---|---|"]
    for word in remaining:
        lines.append(f"| {word['label'].replace('|', '/')} | {word['modelRoute']} | {word['prediction'] or '—'} | {word['diagnosis']} |")
    lines += ["", "Full scalar evidence is in virtual-final/final-all-198.json and virtual-final/summary.json. Candidate selection, frozen audit, failure lists and before/after transitions are retained beside this report. No published benchmark is replaced by reference-test results."]
    if result.get("testSourceRecovery"):
        recovery = result["testSourceRecovery"]
        lines += ["", "## Test-source interruption and continuation", "",
                  f"The virtual stream stopped supplying the current decoded image at NAME. The original interrupted ledger retains all {recovery['outageAttemptsPreservedSeparately']} post-onset attempts, including the canceled take. They are test-source failures, not valid model measurements.",
                  f"The aggregate retains every one of the first {recovery['retainedPrefixAttempts']} pre-outage outcomes, including wrong/no-match results, and one continuation result for each of the other {recovery['continuationAttempts']} labels. Each continuation rebinds only the virtual stream using public camera controls. Source files, hashes, segments and runner protocols are disclosed in the aggregate.",
                  "This is not a same-protocol single-run benchmark or evidence of a model accuracy improvement. No best-of retry selection is used; the source-recovery boundary was chosen from the observed stream failure, not prediction quality."]
    (root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {key: result[key] for key in ("before", "after", "installedModels", "failureDiagnosisCounts", "allWordsReliablyFixed")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT)
    print(json.dumps(report(parser.parse_args().root), indent=2))
