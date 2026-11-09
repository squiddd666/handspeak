"""Continue an interrupted reference audit without choosing best-of retries.

Retain the entire pre-outage prefix, including its wrong/no-match outcomes.
Replace every attempt after the diagnosed source outage with its single
continuation attempt. Preserve the original outage ledger separately.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

try:
    from .report_motion_repair import baseline_attempts
    from .summarize_motion_virtual_camera import assert_scalar_telemetry
except ImportError:
    from report_motion_repair import baseline_attempts
    from summarize_motion_virtual_camera import assert_scalar_telemetry


def merge(prefix, continuation, prefix_count=112):
    for report in (prefix, continuation):
        assert_scalar_telemetry(report)
        isolation = report["isolation"]
        if isolation["host"] != "127.0.0.1" or isolation["storage"] != "in-memory only" or isolation["realCameraCalls"] or isolation["microphoneCalls"]:
            raise ValueError("Source isolation differs")
    for field in ("schema", "geometry", "recognitionLabels", "indexSha256", "bootstrapSha256", "runtimeSha256",
                  "activeModelSha256", "calibrationSha256", "activeAuxiliaryModelSha256"):
        if prefix[field] != continuation[field]:
            raise ValueError(f"Production/source identity changed: {field}")
    prior = [row for row in prefix["attempts"] if row["stage"] == "baseline 1×"]
    later = [row for row in continuation["attempts"] if row["stage"] == "baseline 1×"]
    if len(prior) < prefix_count or not 0 < prefix_count < 198:
        raise ValueError("Missing pre-outage prefix")
    if any(not row.get("finishedAt") or row.get("rate") != 1 for row in prior[:prefix_count] + later):
        raise ValueError("Unfinished or non-normal-speed attempt")
    # Do not drop any pre-outage failures or pick the highest score per word.
    rows = copy.deepcopy(prior[:prefix_count] + later)
    baseline_attempts({"attempts": rows})
    for index, row in enumerate(rows):
        row["sourceSegment"] = "pre-outage prefix" if index < prefix_count else "virtual-stream continuation"
        row["sourceAttemptNumber"] = row["number"]
        row["number"] = index + 1
    result = copy.deepcopy(prefix)
    result["attempts"] = rows
    result["runnerSha256"] = None  # Mixed runner protocols are disclosed, not silently assigned one hash.
    result["isolation"]["getUserMediaCalls"] += continuation["isolation"]["getUserMediaCalls"]
    result["scope"] = ("Primary-reference virtual-camera audit assembled from the complete pre-outage prefix and a single continuation attempt for every remaining label. "
                       "The continuation rebinds the virtual stream per reference; this is a test-source recovery, not a model accuracy improvement or a same-protocol single-run benchmark.")
    result["testSourceRecovery"] = {"retainedPrefixAttempts": prefix_count, "continuationAttempts": len(later),
                                    "outageAttemptsPreservedSeparately": len(prior) - prefix_count,
                                    "prefixRunnerSha256": prefix["runnerSha256"], "continuationRunnerSha256": continuation["runnerSha256"],
                                    "selectionRule": "Keep every first-112 prefix outcome and every single continuation outcome. No best-of, no removal of model rejections.",
                                    "diagnosedOnset": "NAME: partial playback followed by obsolete virtual camera image and repeated no-pose warm-ups",
                                    "recovery": "Rebind only the isolated virtual stream through public camera controls before each remaining reference"}
    return result


def main(args):
    if args.out.exists():
        raise FileExistsError(args.out)
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in (args.prefix, args.continuation)]
    result = merge(*reports, args.prefix_count)
    result["testSourceRecovery"]["sourceReports"] = [
        {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in (args.prefix, args.continuation)]
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result["testSourceRecovery"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--continuation", type=Path, required=True)
    parser.add_argument("--prefix-count", type=int, default=112)
    parser.add_argument("--out", type=Path, required=True)
    main(parser.parse_args())
