"""Validation-only model comparison. Test data is never read by this command."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch

from asl_model_tools import REPO, digest, load_checkpoint, load_rows, predict, tensorize


def stats(probabilities, labels, rows, gate=0):
    valid = np.isfinite(probabilities).all(1)
    idx = {name: i for i, name in enumerate(labels)}
    expected = np.asarray([idx[r["label"]] for r in rows])
    best = np.nan_to_num(probabilities, nan=-1).argmax(1)
    scores = np.nan_to_num(probabilities, nan=-1).max(1)
    accepted = valid & (scores >= gate)
    correct = accepted & (best == expected)
    wrong = accepted & (best != expected)
    per = {label: {"total": sum(r["label"] == label for r in rows),
        "correct": int(correct[expected == i].sum()), "wrong": int(wrong[expected == i].sum())}
        for i, label in enumerate(labels)}
    supported = [m["correct"] / m["total"] for m in per.values() if m["total"]]
    return {"attempts": len(rows), "tracked": int(valid.sum()), "correct": int(correct.sum()), "wrong": int(wrong.sum()),
        "noMatch": int((~accepted).sum()), "accuracy": round(float(correct.mean()), 6),
        "macroAccuracy": round(float(np.mean(supported)), 6),
        "precision": round(float(correct.sum() / max(1, accepted.sum())), 6), "perLabel": per}


def evaluate(path, features, out, name, mirror, version="legacy-v1", split="val"):
    models, labels, blob = load_checkpoint(path)
    rows = load_rows(features, split, labels)
    version = blob.get("preprocessorVersion", version)
    tensors, positions = [], []
    for i, row in enumerate(rows):
        value = tensorize(row, version=version, length=int(blob.get("T", 32)))
        if value is not None:
            tensors.append(value);positions.append(i)
    probabilities = np.full((len(rows), len(labels)), np.nan, np.float32)
    probabilities[positions] = predict(models, tensors, mirror=mirror,
        anatomical=blob.get("mirrorVersion") == "anatomical-v2")
    out.mkdir(parents=True, exist_ok=True)
    archive = out / (name + ".npz")
    np.savez_compressed(archive, probabilities=probabilities, labels=np.asarray(labels),
        expected=np.asarray([r["label"] for r in rows]), files=np.asarray([r["file"] for r in rows]),
        frames=np.asarray([len(r.get("frames") or []) for r in rows]),
        syntheticGreeting=np.asarray([r.get("syntheticGreeting", False) for r in rows]))
    result = {"candidate": name, "checkpoint": str(path), "checkpointSha256": digest(path),
        "features": str(features), "featuresSha256": digest(features), "split": split,
        "minFrames": 5, "preprocessorVersion": version, "mirrorTta": mirror,
        "mirrorVersion": blob.get("mirrorVersion", "legacy-v1"), "snapshots": len(models),
        "probabilities": str(archive), "probabilitiesSha256": digest(archive),
        "raw": stats(probabilities, labels, rows), "gate050": stats(probabilities, labels, rows, .5)}
    (out / (name + ".json")).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", choices=["beginner", "full"], required=True)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--eval-root", type=Path, default=REPO.parent / "hs-eval")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--name", default="retrained")
    args = parser.parse_args()
    torch.set_num_threads(args.threads)
    if args.checkpoint:
        candidates = [(args.name, args.checkpoint, False), (args.name + "-tta", args.checkpoint, True)]
    elif args.family == "beginner":
        candidates = [(f"beginner-v{v}", args.eval_root / f"models/beginner-need79-v{v}.pt", False) for v in range(1, 10)]
        candidates += [("beginner-v1-tta", args.eval_root / "models/beginner-need79-v1.pt", True)]
    else:
        candidates = [("full-deployed", REPO / "third_party/microsoft_asl_citizen/capstone100-v4-ensemble.pt", True),
            ("full-v3", args.eval_root / "models/capstone100-v3.pt", False),
            ("full-v4", args.eval_root / "models/capstone100-v4.pt", True),
            ("full-v5", args.eval_root / "models/capstone100-v5.pt", True),
            ("full-v5-snapshots", args.eval_root / "models/capstone100-v5-snapshots-s1.pt", True)]
    summary = []
    for name, path, mirror in candidates:
        if not path.exists():
            continue
        start = time.perf_counter()
        result = evaluate(path, args.features, args.out, name, mirror)
        compact = {k: v for k, v in result.items() if k not in {"raw", "gate050"}}
        compact.update({k: {m: n for m, n in result[k].items() if m != "perLabel"} for k in ("raw", "gate050")})
        summary.append(compact)
        print(f"{name}: {result['raw']['correct']}/{result['raw']['attempts']} raw; "
            f"gate .5: {result['gate050']['correct']} correct / {result['gate050']['wrong']} wrong / "
            f"{result['gate050']['noMatch']} no match ({time.perf_counter()-start:.1f}s)", flush=True)
        (args.out / "comparison.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
