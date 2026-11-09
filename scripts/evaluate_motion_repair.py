"""Evaluate a frozen motion release on test recordings, never tune on them.

The primary Watch references are excluded from this held-out audit. Tracking
failures remain misses. Synthetic joined greetings are reported separately and
are not described as naturally performed continuous phrases.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch

from asl_model_tools import REPO, digest, load_checkpoint, load_rows, predict, tensorize
from calibrate_motion_models import CORE, EXTRA, canonical
from motion_calibration import decide


def sources(row):
    return {Path(p).name for p in row.get("componentFiles") or [row["file"]]}


def summarize(records, names):
    known = [r for r in records if r["expected"] in names]
    negative = [r for r in records if r["expected"] not in names]
    totals = Counter(r["outcome"] for r in known)
    correct, wrong, no_match = (totals[k] for k in ("correct", "wrong", "no-match"))
    per = {}
    for label in names:
        members = [r for r in known if r["expected"] == label]
        counts = Counter(r["outcome"] for r in members)
        per[label] = {"total": len(members), "correct": counts["correct"],
                      "wrong": counts["wrong"], "noMatch": counts["no-match"],
                      "tracked": sum(r["tracked"] for r in members),
                      "syntheticGreeting": sum(r["syntheticGreeting"] for r in members)}
    return {"attempts": len(known), "correct": correct, "wrong": wrong, "noMatch": no_match,
            "tracked": sum(r["tracked"] for r in known),
            "accuracy": round(correct / max(1, len(known)), 6),
            "precision": round(correct / max(1, correct + wrong), 6),
            "negativeAttempts": len(negative),
            "negativeFalse": sum(bool(r["prediction"]) for r in negative),
            "negativeFalseRate": round(sum(bool(r["prediction"]) for r in negative) / max(1, len(negative)), 6),
            "perLabel": per}


def run_checkpoint(checkpoint, rows, family, policies, fusion=None):
    models, labels, blob = load_checkpoint(checkpoint)
    version = blob.get("preprocessorVersion", "legacy-v1")
    mirror = bool(blob.get("mirrorTta", len(models) > 1))
    tensors, positions = [], []
    for i, row in enumerate(rows):
        x = tensorize(row, version, int(blob.get("T", 32)))
        if x is not None:
            tensors.append(x); positions.append(i)
    p = np.full((len(rows), len(labels)), np.nan, np.float32)
    p[positions] = predict(models, tensors, mirror=mirror,
                           anatomical=blob.get("mirrorVersion") == "anatomical-v2")
    auxiliary_p = None
    if fusion:
        from handshape_model import load as load_auxiliary, predict as predict_auxiliary
        from handshape_features import tensorize as shape_tensorize
        auxiliary, auxiliary_labels, _ = load_auxiliary(fusion["auxiliaryCheckpoint"])
        if digest(fusion["auxiliaryCheckpoint"]) != fusion["auxiliarySha256"] or fusion["checkpointSha256"] != digest(checkpoint):
            raise ValueError("Fusion checkpoint identity mismatch")
        values = [shape_tensorize(row) for row in rows]
        observed = [i for i,x in enumerate(values) if x is not None]
        auxiliary_p = np.full((len(rows),len(auxiliary_labels)),np.nan,np.float32)
        auxiliary_p[observed] = predict_auxiliary(auxiliary,[values[i] for i in observed])
    modes = {"full": labels} if family == "beginner" else {"full": labels, "core": CORE, "extended": CORE + EXTRA}
    result = {"checkpoint": checkpoint.name, "checkpointSha256": digest(checkpoint),
              "preprocessorVersion": version, "mirrorTta": mirror,
              "mirrorVersion": blob.get("mirrorVersion", "legacy-v1"), "snapshots": len(models), "modes": {}}
    for mode, names in modes.items():
        probabilities, decision_labels = p, labels
        weight = fusion["selected"][mode]["weight"] if fusion else 0
        if weight:
            from handshape_inference import combine
            probabilities = combine(p,auxiliary_p,labels,auxiliary_labels,weight)
            decision_labels = labels + ["__UNKNOWN__"]
        allowed = [labels.index(label) for label in names]
        records, raw_records = [], []
        for i, row in enumerate(rows):
            tracked = bool(np.isfinite(probabilities[i]).all())
            base = {"file": row["file"], "expected": row["label"], "tracked": tracked,
                    "frames": len(row.get("frames") or []), "syntheticGreeting": bool(row.get("syntheticGreeting"))}
            if tracked:
                decision = decide(probabilities[i], decision_labels, allowed=allowed, policy=policies[mode])
                prediction = (decision["predictions"] or [{}])[0].get("label")
                raw_prediction = decision["suggestions"][0]["label"]
                details = {"suggestions": decision["suggestions"], "rejectionReason": decision["rejectionReason"]}
            else:
                prediction = raw_prediction = None
                details = {"suggestions": [], "rejectionReason": "insufficient-tracking"}
            outcome = "no-match" if not prediction else "correct" if prediction == row["label"] else "wrong"
            records.append({**base, "prediction": prediction, "outcome": outcome, **details})
            raw_records.append({**base, "prediction": raw_prediction,
                                "outcome": "no-match" if not raw_prediction else "correct" if raw_prediction == row["label"] else "wrong"})
        result["modes"][mode] = {"policy": policies[mode], "accepted": summarize(records, names),
                                 "raw": summarize(raw_records, names), "records": records, **({"auxiliaryWeight":weight} if fusion else {})}
    if fusion:
        result.update(auxiliarySha256=fusion["auxiliarySha256"],auxiliaryFeatureVersion=fusion["auxiliaryFeatureVersion"])
    return result


def evaluate(args):
    torch.set_num_threads(args.threads)
    _, labels, _ = load_checkpoint(args.checkpoint)
    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    if calibration["family"] != args.family or calibration["checkpointSha256"] != digest(args.checkpoint):
        raise ValueError("Calibration is not bound to this model")
    if any(policy["selectionSplit"] != "val" for policy in calibration["policies"].values()):
        raise ValueError("Only validation-selected gates may be evaluated")
    manifest = json.loads((REPO / "models/recognition-videos.json").read_text(encoding="utf-8"))
    watch_files = {s["originalFile"] for item in manifest["items"] for s in item.get("sources", [])}
    all_known = load_rows(args.features, "test", labels)
    known = [row for row in all_known if not sources(row) & watch_files]
    label_forms = {canonical(label) for label in labels}
    all_negative = [r for r in load_rows(args.neg_features, "test")
                    if canonical(r["label"]) not in label_forms and not r.get("syntheticGreeting")]
    negative = [r for r in all_negative if not sources(r) & watch_files]
    rows = known + negative
    if len({r["file"] for r in rows}) != len(rows):
        raise ValueError("Duplicate test attempts")
    for split in ("train", "val"):
        selection = load_rows(args.training_features, split)
        prior_sources = set().union(*(sources(row) for row in selection)) if selection else set()
        prior_participants = {p for r in selection for p in r.get("participants") or [r.get("participant")] if p}
        for row in rows:
            participants = {p for p in row.get("participants") or [row.get("participant")] if p}
            if sources(row) & prior_sources or participants & prior_participants:
                raise ValueError(f"Test source/participant overlaps {split}: {row['file']}")
    missing = sorted(set(labels) - {r["label"] for r in known})
    if missing:
        raise ValueError(f"No independent test recording remains for labels: {missing}")
    result = {"version": 1, "family": args.family, "split": "test",
              "calibrationSha256": digest(args.calibration), "featuresSha256": digest(args.features),
              "negativeFeaturesSha256": digest(args.neg_features), "trainingFeaturesSha256": digest(args.training_features),
              "sourcesAndParticipantsDisjoint": True, "testUsedForSelection": False,
              "watchClipsExcluded": True, "watchKnownExcluded": len(all_known) - len(known),
              "watchNegativeExcluded": len(all_negative) - len(negative),
              "knownAttempts": len(known), "negativeAttempts": len(negative),
              "scope": "Frozen-checkpoint held-out extracted-recording audit. Tracking failures count as misses; primary Watch references excluded. Not physical live-camera accuracy.",
              "greetingScope": "GOOD greetings use explicitly synthetic joined isolated components; natural continuous greetings are not verified.",
              "selected": run_checkpoint(args.checkpoint, rows, args.family, calibration["policies"],
                  json.loads(args.fusion_selection.read_text(encoding="utf-8")) if getattr(args,"fusion_selection",None) else None)}
    if args.baseline:
        _, old_labels, _ = load_checkpoint(args.baseline)
        if set(old_labels) != set(labels):
            raise ValueError("Baseline and selected label sets differ")
        policies = {"full": {"minScore": .5 if args.family == "beginner" else 0}}
        if args.family == "capstone":
            policies.update(core={"minScore": .7}, extended={"minScore": .55})
        result["baseline"] = run_checkpoint(args.baseline, rows, args.family, policies)
        result["baseline"]["scope"] = "Same corrected test attempts and legacy deployed rejection settings, not an old published denominator."
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for name in ("baseline", "selected"):
        if name in result:
            for mode, metrics in result[name]["modes"].items():
                print(name, mode, json.dumps({k: v for k, v in metrics["accepted"].items() if k != "perLabel"}), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", choices=["beginner", "capstone"], required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--neg-features", type=Path, required=True)
    parser.add_argument("--training-features", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--fusion-selection", type=Path, help="Frozen validation-only auxiliary fusion selection")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=2)
    evaluate(parser.parse_args())
