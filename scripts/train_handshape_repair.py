"""Explore a full-handshape auxiliary model, using train/validation only.

This creates a candidate, never changes active weights. Test/Watch clips are
excluded and are not inputs to checkpoint selection or rejection calibration.
"""
from __future__ import annotations
import argparse, copy, json, math, sys, time
from collections import Counter
from pathlib import Path
import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset
from asl_model_tools import REPO, digest, load_checkpoint, load_rows
sys.path.insert(0, str(REPO))
from handshape_features import VERSION, raw_arrays, encode, tensorize, mirror
from handshape_model import TemporalHandshape, predict
from calibrate_motion_models import canonical


def sources(row):
    return {Path(p).name for p in row.get("componentFiles") or [row["file"]]}


class Clips(Dataset):
    def __init__(self, rows, labels, seed):
        self.rows = [(raw_arrays(r["frames"]), labels.index(r["label"]), bool(r.get("syntheticGreeting"))) for r in rows]
        self.rng = np.random.default_rng(seed)
    def __len__(self):
        return len(self.rows)
    def __getitem__(self, i):
        (p, h, m), label, synthetic = self.rows[i]
        p, h, m = p.copy(), h.copy(), m.copy()
        aspect = self.rng.uniform(.72, 1.28)
        p[:, :, 1] *= aspect; h[:, :, :, 1] *= aspect
        if not synthetic and len(p) > 7 and self.rng.random() < .3:
            n = max(5, round(len(p) * self.rng.uniform(.85, 1)))
            start = int(self.rng.integers(0, len(p) - n + 1))
            p, h, m = p[start:start+n], h[start:start+n], m[start:start+n]
        if len(p) > 7 and self.rng.random() < .4:
            n = int(self.rng.integers(5, max(6, min(24, len(p))) + 1))
            idx = np.linspace(0, len(p)-1, min(n, len(p))).round().astype(int)
            p, h, m = p[idx], h[idx], m[idx]
        if self.rng.random() < .2:
            side = int(self.rng.integers(2))
            drop = (self.rng.random(len(p)) < .15) & (m[:, 1-side] > 0)
            m[drop, side] = 0; h[drop, side] = 0
        x = encode(p, h, m)
        x[:-2] += self.rng.normal(0, .01, x[:-2].shape).astype(np.float32)
        for side in range(2):
            x[14+side*2:16+side*2] *= x[-2+side]
            x[18+side*63:81+side*63] *= x[-2+side]
        if self.rng.random() < .5:
            x = mirror(x)
        return torch.from_numpy(x), label


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("features", "negative-features", "base", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=65)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--seed", type=int, default=43)
    parser.add_argument("--init-auxiliary", type=Path, help="Optional vocabulary-identical auxiliary for targeted fine-tuning")
    parser.add_argument("--lr", type=float, default=.001)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    torch.set_num_threads(args.threads); torch.manual_seed(args.seed); np.random.seed(args.seed)
    _, names, _ = load_checkpoint(args.base)
    labels = names + ["__UNKNOWN__"]
    forms = {canonical(n) for n in names}
    splits = {}
    watch = {s["originalFile"] for item in json.loads((REPO / "models/recognition-videos.json").read_text(encoding="utf-8"))["items"] for s in item.get("sources", [])}
    for split in ("train", "val"):
        rows = load_rows(args.features, split, names)
        negatives = [r for r in load_rows(args.negative_features, split) if canonical(r["label"]) not in forms and not r.get("syntheticGreeting")]
        for r in negatives:
            r["originalLabel"] = r["label"]; r["label"] = "__UNKNOWN__"
        merged = rows + negatives
        if any(sources(r) & watch for r in merged):
            raise ValueError("Watch leakage in training/validation")
        # Deduplicate before training; the same source cannot be two attempts.
        unique = {}
        for r in merged:
            key = r["file"]
            if key in unique and unique[key]["label"] != r["label"]:
                raise ValueError("Conflicting labels for one source")
            unique[key] = r
        splits[split] = list(unique.values())
    train_sources = set().union(*(sources(r) for r in splits["train"]))
    if any(sources(r) & train_sources for r in splits["val"]):
        raise ValueError("Train/val source leakage")
    participants = {p for r in splits["train"] for p in r.get("participants") or [r.get("participant")] if p}
    if any(participants.intersection(r.get("participants") or [r.get("participant")]) for r in splits["val"]):
        raise ValueError("Train/val participant leakage")
    train = [r for r in splits["train"] if tensorize(r) is not None]
    counts = Counter(r["label"] for r in train)
    if set(labels) - set(counts):
        raise ValueError("Missing training labels")
    val = splits["val"]; tensors, positions = [], []
    for i, r in enumerate(val):
        x = tensorize(r)
        if x is not None:
            tensors.append(x); positions.append(i)
    expected = np.asarray([labels.index(r["label"]) for r in val])
    model = TemporalHandshape(len(labels))
    if args.init_auxiliary:
        from handshape_model import load
        previous, previous_labels, previous_blob = load(args.init_auxiliary)
        if previous_labels != labels or previous_blob["featureVersion"] != VERSION:
            raise ValueError("Fine-tuning auxiliary vocabulary/feature version differs")
        model.load_state_dict(previous.state_dict())
    loader = DataLoader(Clips(train, labels, args.seed), batch_size=48, shuffle=True, num_workers=0,
                        generator=torch.Generator().manual_seed(args.seed))
    weights = np.asarray([1/math.sqrt(counts[n]) for n in labels])
    # Preserve a meaningful unknown contribution without letting its many
    # training examples overwhelm the small named classes.
    weights[-1] *= 3
    criterion = torch.nn.CrossEntropyLoss(weight=torch.tensor(weights/weights.mean(), dtype=torch.float32), label_smoothing=.025)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=.004)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, args.epochs, eta_min=args.lr*.1)
    audit = {"featuresSha256": digest(args.features), "negativeFeaturesSha256": digest(args.negative_features),
             "baseCheckpointSha256": digest(args.base), "trainAttempts": len(splits["train"]), "trainUsable": len(train),
             "valAttempts": len(val), "valTracked": len(positions), "trainCounts": dict(counts),
             "testUsedForSelection": False, "watchClipsUsedForTrainingOrCalibration": False,
             "selectionSplit": "val", "sourceAndParticipantDisjoint": True, "seed": args.seed,
             "initialAuxiliarySha256": digest(args.init_auxiliary) if args.init_auxiliary else None, "learningRate": args.lr,
             "greetingScope": "Synthetic GOOD + component greetings, not verified natural phrases."}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    history, best = [], -1
    print(json.dumps(audit), flush=True)
    for epoch in range(1, args.epochs + 1):
        start = time.perf_counter(); loss_sum = 0; model.train()
        for x, y in loader:
            optimizer.zero_grad(set_to_none=True); loss = criterion(model(x), y); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5); optimizer.step()
            loss_sum += loss.item()*len(y)
        scheduler.step(); model.eval()
        p = np.full((len(val),len(labels)), np.nan, np.float32); p[positions] = predict(model,tensors)
        correct = np.zeros(len(val), bool); correct[positions] = p[positions].argmax(1) == expected[positions]
        macro = float(np.mean([correct[expected == i].mean() for i in range(len(names))]))
        unknown_accuracy = float(correct[expected == len(names)].mean())
        objective = .85*macro + .15*unknown_accuracy
        record = {"epoch": epoch, "loss": round(loss_sum/len(train),4), "valKnownMacro": round(macro,6),
                  "valUnknownAccuracy": round(unknown_accuracy,6), "objective": round(objective,6),
                  "seconds": round(time.perf_counter()-start,1)}
        history.append(record)
        if objective > best:
            best = objective
            torch.save({"state_dict": copy.deepcopy(model.state_dict()), "labels": labels, "width":160,
                        "featureVersion": VERSION,"architecture":"temporal-handshape-v1","trainingAudit":audit,
                        "epoch":epoch,"valObjective":objective},args.out)
            np.savez_compressed(args.out.with_suffix(".val.npz"), probabilities=p,expected=np.asarray([r["label"] for r in val]),
                                files=np.asarray([r["file"] for r in val]),labels=np.asarray(labels))
        args.out.with_suffix(".history.json").write_text(json.dumps({"audit":audit,"history":history},indent=2)+"\n",encoding="utf-8")
        print(json.dumps(record),flush=True)
    print("Saved candidate only:",args.out,flush=True)


if __name__ == "__main__":
    main()
