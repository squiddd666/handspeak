"""Fit a body-location-aware 24-word candidate on train/validation only.

Never installs a model or reads the held-out test recordings. A recording's
source/signers and primary Watch exclusions are checked before fitting.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import itertools
import json
from pathlib import Path
import sys
import time

import numpy as np
from prepare_native_repair_v4 import REPO, read_rows, verify_splits
from prepare_targeted_data_v4 import MANUAL
from train_native_manual_v4 import metrics
sys.path.insert(0, str(REPO))
from body_manual_features import VERSION, tensorize, mirrored, dtw_many


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(rows):
    result = []
    for row in rows:
        # Match server capture: keep only real pose+hand results, never invent
        # absent frames. Aspect is derived from the native decoder dimensions.
        frames = [f for f in row["frames"] if f.get("pose") and (f.get("left") or f.get("right"))]
        r = dict(row, frames=frames, label=row.get("manualLabel") or row["gloss"])
        sequence = tensorize(r)
        result.append({key: r[key] for key in ("file", "participant", "split", "label", "gloss")} |
                      {"sequence": sequence, "trackedFrames": len(frames)})
    return result


def matrix(rows, refs, parameters):
    sequences = np.asarray([r["sequence"] for r in refs])
    result = []
    for row in rows:
        if row["sequence"] is None:
            result.append(np.full(len(refs), np.inf))
        else:
            a = row["sequence"]
            result.append(np.minimum(dtw_many(a, sequences, **parameters), dtw_many(mirrored(a), sequences, **parameters)))
    return np.asarray(result)


def gate_statistics(distances, refs, labels):
    """Cache rankings without changing the original scalar gate semantics."""
    ref_labels = np.asarray([r['label'] for r in refs])
    ranking = np.argsort(distances, axis=1, kind='stable')
    top = ref_labels[ranking[:, 0]]
    smallest = distances[np.arange(len(distances)), ranking[:, 0]]
    other = np.where(ref_labels[None, :] != top[:, None], distances, np.inf).min(1)
    separation = np.divide(other, smallest + 1e-6, out=np.zeros(len(distances)), where=np.isfinite(smallest))
    agreement = (ref_labels[ranking[:, :3]] == top[:, None]).sum(1)
    return top, np.isin(top, labels), smallest, separation, agreement


def gate_mask(statistics, parameters):
    _, named, smallest, separation, agreement = statistics
    return (named & (smallest <= parameters['maxDistance']) &
            (separation >= parameters['minRatio']) &
            ((agreement >= parameters['minVotes']) | (separation >= parameters['strongRatio'])))


def prototypes(rows, count):
    if len(rows) <= count:
        return rows
    d = matrix(rows, rows, {})
    selected = [int(np.argmin(np.median(d, axis=1)))]
    while len(selected) < count:
        distance = d[:, selected].min(1)
        distance[selected] = -1
        selected.append(int(np.argmax(distance)))
    return [rows[i] for i in selected]


def fit(args):
    if args.out.exists():
        raise FileExistsError(args.out)
    started = time.perf_counter()
    native = [r for r in read_rows(args.native) if r["split"] in {"train", "val"}]
    watch = {s["originalFile"] for item in json.loads((REPO/"models/recognition-videos.json").read_text(encoding="utf-8"))["items"] for s in item.get("sources", [])}
    verify_splits(native, watch)
    if len({r["file"] for r in native}) != len(native):
        raise ValueError("Duplicate native sources")
    rows = prepare(native)
    labels = list(MANUAL)
    train = [r for r in rows if r["split"] == "train" and r["sequence"] is not None]
    val = [r for r in rows if r["split"] == "val"]
    counts = Counter(r["label"] for r in train)
    if any(counts[label] < 3 for label in labels):
        raise ValueError("Insufficient independently tracked training recordings")
    refs = []
    for label in labels:
        refs += prototypes([r for r in train if r["label"] == label], 5)
    groups = defaultdict(list)
    for row in train:
        if row["label"] not in labels:
            groups[row["gloss"]].append(row)
    negatives = []
    for gloss in sorted(groups):
        negatives += prototypes(groups[gloss], 2)
    negatives = sorted(negatives, key=lambda r: hashlib.sha256(r["file"].encode()).hexdigest())[:96]
    refs += [dict(row, label="OTHER MOVEMENT") for row in negatives]
    print("Tracked train labels", dict(counts), "references", len(refs), "validation", len(val), flush=True)
    best = None
    # Distance feature weights and acceptance gates are validation selections,
    # not tuned from the six erroneous Watch predictions or held-out test.
    for wrist, shape, missing in itertools.product((.5, 1., 2.), (.25, .5, 1.), (.5, 1.)):
        feature_parameters = dict(wrist_weight=wrist, shape_weight=shape, pose_weight=.15, missing_cost=missing)
        distances = matrix(val, refs, feature_parameters)
        statistics = gate_statistics(distances, refs, labels)
        top = statistics[0]
        expected = np.asarray([r['label'] for r in val])
        known = np.isin(expected, labels)
        correct = top == expected
        for limit, ratio, votes, strong in itertools.product((.2, .35, .5, .75, 1., 1.5, 2., 3.), (1., 1.1, 1.2, 1.4, 1.7, 2.), (1, 2, 3), (1.5, 2., 3., 5.)):
            if strong < ratio:
                continue
            parameters = dict(maxDistance=limit, minRatio=ratio, minVotes=votes, strongRatio=strong, mirror=True)
            accepted = gate_mask(statistics, parameters)
            hit = int((known & accepted & correct).sum())
            wrong = int((known & accepted & ~correct).sum())
            negative = int((~known & accepted).sum())
            measured = dict(attempts=int(known.sum()), correct=hit, wrong=wrong, noMatch=int((known & ~accepted).sum()),
                            negativeAttempts=int((~known).sum()), negativeFalse=negative,
                            precision=hit/max(1,hit+wrong), negativeFalseRate=negative/max(1,int((~known).sum())))
            if measured["precision"] < .95 or measured["negativeFalseRate"] > .03:
                continue
            if best is not None and hit < best[0][0]:
                continue
            macro = np.mean([int((accepted & correct & (expected==label)).sum()) / max(1,int((expected==label).sum())) for label in labels])
            key = (measured["correct"], macro, -measured["wrong"], -measured["negativeFalse"])
            if best is None or key > best[0]:
                out = [str(label) if yes else None for label,yes in zip(top,accepted)]
                best = key, feature_parameters, parameters, measured, out
        print("Feature weights", feature_parameters, "best", best[3] if best else None, flush=True)
    if best is None:
        raise ValueError("No reliable validation operating point")
    _, feature_parameters, parameters, validation, out = best
    model = dict(version=1, featureVersion=VERSION, labels=labels, featureParameters=feature_parameters, parameters=parameters,
                 samples=[dict(label=r["label"], sequence=r["sequence"].tolist()) for r in refs],
                 status="candidate-not-installed", source="ASL Citizen local noncommercial research")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(model, separators=(",", ":")), encoding="utf-8")
    audit = dict(modelSha256=digest(args.out), nativeSha256=digest(args.native), selectionSplit="val", testUsedForSelection=False,
                 watchClipsUsedForSelection=False, sourcesAndParticipantsDisjoint=True, featureVersion=VERSION,
                 trainCounts={label: counts[label] for label in labels}, validation=validation, deployed=False,
                 featureParameters=feature_parameters, parameters=parameters,
                 perLabel={label: metrics([r for r in val if r["label"] == label], [p for r, p in zip(val, out) if r["label"] == label], labels) for label in labels},
                 records=[dict(file=r["file"], expected=r["label"], prediction=p, tracked=r["sequence"] is not None, trackedFrames=r["trackedFrames"]) for r, p in zip(val, out)],
                 scope="Body-location-aware experiment; no installation or held-out claim until frozen comparison against existing routes.",
                 seconds=round(time.perf_counter()-started, 2))
    args.out.with_suffix(".validation.json").write_text(json.dumps(audit, indent=2)+"\n", encoding="utf-8")
    print("Candidate only", json.dumps(validation), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    fit(parser.parse_args())
