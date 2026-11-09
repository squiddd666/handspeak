"""Fit global rejection gates on validation only, including unknown signs.

Never selects expected Watch words or tunes on reference videos/test samples.
The objective recovers correct suggestions subject to a validation precision
and unknown-sign false-accept ceiling. These are empirical gates, not a
claim that an individual softmax score is a calibrated probability.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import torch

from asl_model_tools import REPO, digest, load_checkpoint, load_rows, predict, tensorize

CORE = ["BELT1", "EAT1", "EMPTY2", "PEG2", "SOCCER2", "SQUEEZE", "VLOG"]
EXTRA = ["BASEBALLCAP", "DEAF1", "DEMAND1", "DRAG1", "DUCK2", "EDIT1", "LOCK1", "MECHANIC1", "MICROSCOPE1", "OTHER", "PARTY1", "WHATFOR1"]


def canonical(label):
    return re.sub(r"\s+", " ", re.sub(r"[-/]+", " ", re.sub(r"[12]$", "", label))).strip().upper()


def summarize(correct, accepted, known):
    hit = correct & accepted & known
    wrong = accepted & known & ~correct
    fp = accepted & ~known
    total, negative = int(known.sum()), int((~known).sum())
    return {"attempts": total, "correct": int(hit.sum()), "wrong": int(wrong.sum()), "noMatch": int((known & ~accepted).sum()),
        "accuracy": round(float(hit.sum() / max(1, total)), 6),
        "precision": round(float(hit.sum() / max(1, (accepted & known).sum())), 6),
        "overallPrecision": round(float(hit.sum() / max(1, accepted.sum())), 6),
        "negativeAttempts": negative, "negativeFalse": int(fp.sum()), "negativeFalseRate": round(float(fp.sum() / max(1, negative)), 6)}


def fit(probabilities, expected, labels, names, precision=.9, negative_ceiling=.10, baseline_score=None):
    allowed = np.asarray([labels.index(label) for label in names])
    valid = np.isfinite(probabilities).all(1)
    p = np.nan_to_num(probabilities, nan=0)[:, allowed]
    mass = p.sum(1)
    q = p / np.maximum(mass[:, None], 1e-15)
    ranking = np.argsort(q, 1)[:, ::-1]
    score = q[np.arange(len(q)), ranking[:, 0]]
    margin = score - (q[np.arange(len(q)), ranking[:, 1]] if len(names) > 1 else 0)
    predicted = np.asarray(names)[ranking[:, 0]]
    known = np.isin(expected, names)
    correct = predicted == expected
    if baseline_score is None:
        baseline_score = .5 if len(names) > 24 else .55 if len(names) > 8 else .7
    baseline = summarize(correct, valid & (score >= baseline_score), known)
    grid = sorted(set([0, .05, .1, .15, .2, .25, .3, .35, .4, .45, .5, .55, .6, .65, .7, .75, .8, .9, .999999]))
    best, choices = None, []
    for gate in grid:
        for gap in [0, .02, .04, .06, .08, .1, .15, .2, .3]:
            for minimum_mass in ([0] if len(names) == len(labels) else [0, .01, .03, .05, .1, .2]):
                accepted = valid & (score >= gate) & (margin >= gap) & (mass >= minimum_mass)
                metrics = summarize(correct, accepted, known)
                if metrics["wrong"] and metrics["precision"] < precision:
                    continue
                if metrics["negativeFalseRate"] > negative_ceiling:
                    continue
                key = (metrics["correct"], -metrics["wrong"], -metrics["negativeFalse"], -gap, -minimum_mass, -gate)
                policy = {"minScore": gate, "minMargin": gap, "minVocabularyMass": minimum_mass,
                    "validation": metrics, "selectionSplit": "val", "targetKnownWordPrecision": precision, "negativeFalseCeiling": negative_ceiling}
                choices.append(policy)
                if best is None or key > best[0]:
                    best = (key, policy)
    if best is None or not best[1]["validation"]["correct"]:
        raise ValueError(f"No nonempty reliable operating point for {len(names)} signs")
    return {**best[1], "baselineValidation": baseline}, choices


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", choices=["beginner", "capstone"], required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--neg-features", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--known-precision", type=float, default=.9)
    parser.add_argument("--negative-ceiling", type=float, default=.1,
                        help="Validation unsupported-sign acceptance ceiling; never selected on Watch or test clips")
    args = parser.parse_args()
    if not 0 < args.known_precision <= 1 or not 0 <= args.negative_ceiling <= 1:
        parser.error("Precision must be in (0, 1] and negative ceiling in [0, 1]")
    torch.set_num_threads(args.threads)
    models, labels, blob = load_checkpoint(args.checkpoint)
    evidence = json.loads(args.archive.with_suffix(".json").read_text(encoding="utf-8"))
    if evidence["split"] != "val" or evidence["checkpointSha256"] != digest(args.checkpoint) or evidence["probabilitiesSha256"] != digest(args.archive):
        raise ValueError("Validation probabilities are not bound to this checkpoint")
    mirror = bool(blob.get("mirrorTta", len(models) > 1))
    if evidence["mirrorTta"] != mirror:
        raise ValueError("Validation/inference mirror policy differs")
    data = np.load(args.archive, allow_pickle=False)
    if list(data["labels"]) != labels:
        raise ValueError("Validation label order differs from checkpoint")
    version = blob.get("preprocessorVersion", "legacy-v1")
    all_neg = load_rows(args.neg_features, "val")
    watch_manifest = json.loads((REPO / "models/recognition-videos.json").read_text(encoding="utf-8"))
    watch_files = {s["originalFile"] for item in watch_manifest["items"] for s in item.get("sources", [])}
    if any({Path(p).name for p in r.get("componentFiles") or [r["file"]]} & watch_files for r in all_neg):
        raise ValueError("A Watch reference is in the validation negatives")
    existing = {canonical(label) for label in labels}
    neg = [r for r in all_neg if canonical(r["label"]) not in existing and not r.get("syntheticGreeting")]
    tensors, positions = [], []
    for i, row in enumerate(neg):
        x = tensorize(row, version, int(blob.get("T", 32)))
        if x is not None:
            tensors.append(x); positions.append(i)
    negative_p = np.full((len(neg), len(labels)), np.nan, np.float32)
    negative_p[positions] = predict(models, tensors, mirror=mirror, anatomical=blob.get("mirrorVersion") == "anatomical-v2")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.out.with_suffix(".negatives.npz"), probabilities=negative_p,
        expected=np.asarray([r["label"] for r in neg]), files=np.asarray([r["file"] for r in neg]), labels=np.asarray(labels))
    p = np.concatenate([data["probabilities"], negative_p])
    expected = np.concatenate([data["expected"], np.asarray(["__UNKNOWN__"] * len(neg))])
    modes = {"full": labels} if args.family == "beginner" else {"full": labels, "core": CORE, "extended": CORE + EXTRA}
    policies = {}
    for mode, names in modes.items():
        policy, _ = fit(p, expected, labels, names, precision=args.known_precision,
                        negative_ceiling=args.negative_ceiling,
                        baseline_score=0 if args.family == "capstone" and mode == "full" else None)
        policies[mode] = policy
        print(mode, json.dumps(policy), flush=True)
    result = {"family": args.family, "checkpoint": args.checkpoint.name, "checkpointSha256": digest(args.checkpoint),
        "labels": labels, "preprocessorVersion": version, "mirrorTta": mirror,
        "mirrorVersion": blob.get("mirrorVersion", "legacy-v1"), "policies": policies,
        "sourceValidationProbabilitiesSha256": digest(args.archive), "negativeFeaturesSha256": digest(args.neg_features),
        "negativeValidationAttempts": len(neg), "negativeTracked": len(positions), "testUsedForCalibration": False,
        "watchClipsUsedForCalibration": False, "scoreScope": "Empirical validation rejection gates; softmax is not calibrated confidence."}
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
