"""Fine-tune a sign model on audited training data; select on validation only.

Watch & Learn references are never training/calibration inputs. The repaired
Beginner greetings are explicitly synthetic GOOD + component recordings, not
evidence of accuracy on naturally performed continuous phrases.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

from asl_model_tools import REPO, arrays, digest, load_checkpoint, load_rows, make_model, mirror_tensor, predict, resample, tensorize


class TrainingClips(Dataset):
    def __init__(self, rows, labels, version, seed, aspect_jitter=0):
        self.rows = [(arrays(r["frames"], version), labels.index(r["label"]), bool(r.get("syntheticGreeting"))) for r in rows]
        self.rng = np.random.default_rng(seed)
        self.version = version
        self.aspect_jitter = aspect_jitter

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        (coords, masks), label, greeting = self.rows[index]
        c, m = coords.copy(), masks.copy()
        # Training extraction stretched sources to 640x480; physical cameras and
        # contained/letterboxed videos need tolerance to vertical scaling.
        # Apply only to training, never infer a source aspect from a word label.
        if self.aspect_jitter:
            c[:, :, 1] *= self.rng.uniform(1 - self.aspect_jitter, 1 + self.aspect_jitter)
        # Do not crop a synthetic greeting down to just one of its components.
        if not greeting and len(c) > 7 and self.rng.random() < .35:
            size = max(5, round(len(c) * self.rng.uniform(.85, 1)))
            start = int(self.rng.integers(0, len(c) - size + 1))
            c, m = c[start:start + size], m[start:start + size]
        # Reproduce sparse camera sampling without copying or inventing frames.
        if len(c) > 7 and self.rng.random() < .45:
            size = int(self.rng.integers(5, max(6, min(24, len(c))) + 1))
            indices = np.linspace(0, len(c) - 1, min(size, len(c))).round().astype(int)
            c, m = c[indices], m[indices]
        if self.version == "masked-v2" and self.rng.random() < .18:
            side = int(self.rng.integers(0, 2))
            block = slice(7 + side * 10, 17 + side * 10)
            other = slice(17 - side * 10, 27 - side * 10)
            drop = (self.rng.random(len(c)) < .15) & (m[:, other].sum((1, 2)) > 0)
            c[drop, block] = 0; m[drop, block] = 0
        c, m = resample(c, m, version=self.version)
        present = np.concatenate([np.ones((len(c), 7, 1), np.float32), m[:, 7:].sum(-1, keepdims=True)], 1)
        c += self.rng.normal(0, .004, c.shape).astype(np.float32) * present
        x = np.concatenate([c.transpose(2, 0, 1), m.transpose(2, 0, 1)], 0).astype(np.float32)
        if self.rng.random() < .5:
            x = mirror_tensor(x, anatomical=self.version == "masked-v2")
        return torch.from_numpy(x), label


def initialize(path, labels):
    _, old_labels, blob = load_checkpoint(path)
    state = (blob.get("snapshots") or [{"state_dict": blob["state_dict"]}])[0]["state_dict"]
    model = make_model(labels)
    target = model.state_dict()
    head_keys = {"decoder.classifier.weight", "decoder.classifier.bias"}
    for key, value in state.items():
        if key not in head_keys and key in target and value.shape == target[key].shape:
            target[key] = value.clone()
    copied = []
    for index, label in enumerate(labels):
        # Old checkpoints learned isolated MORNING under GOOD MORNING.
        source = "GOOD MORNING" if label == "MORNING" and label not in old_labels else label
        if source in old_labels:
            for key in head_keys:
                target[key][index] = state[key][old_labels.index(source)].clone()
            copied.append({"target": label, "source": source})
    model.load_state_dict(target)
    return model, copied


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--init", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--family", choices=["beginner", "full"], required=True)
    parser.add_argument("--version", choices=["legacy-v1", "masked-v2"], default="masked-v2")
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--lr", type=float, default=1.5e-4)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--aspect-jitter", type=float, default=0,
                        help="Training-only vertical coordinate jitter for camera aspect robustness (0 to .5)")
    args = parser.parse_args()
    if not 0 <= args.aspect_jitter <= .5:
        parser.error("aspect-jitter must be between 0 and .5")
    if args.out.exists():
        raise FileExistsError(args.out)
    torch.set_num_threads(args.threads)
    torch.manual_seed(args.seed); np.random.seed(args.seed)
    if args.family == "beginner":
        labels = json.loads((REPO / "models/beginner-100-label-map.json").read_text(encoding="utf-8"))["trainLabels"]
    else:
        _, labels, _ = load_checkpoint(args.init)
    train_all = load_rows(args.features, "train", labels)
    val = load_rows(args.features, "val", labels)
    watch_manifest = json.loads((REPO / "models/recognition-videos.json").read_text(encoding="utf-8"))
    watch_files = {s["originalFile"] for item in watch_manifest["items"] for s in item.get("sources", [])}
    def sources(row):
        return {Path(p).name for p in row.get("componentFiles") or [row["file"]]}
    if any(sources(row) & watch_files for row in train_all + val):
        raise ValueError("A Watch source appears in training or calibration")
    if set().union(*(sources(row) for row in train_all)) & set().union(*(sources(row) for row in val)):
        raise ValueError("Training/validation source leakage")
    train = [r for r in train_all if tensorize(r, args.version) is not None]
    counts = Counter(r["label"] for r in train)
    missing = set(labels) - set(counts)
    if missing:
        raise ValueError(f"Labels without valid training examples: {sorted(missing)}")
    valid_indices, val_tensors = [], []
    for i, row in enumerate(val):
        x = tensorize(row, args.version)
        if x is not None:
            valid_indices.append(i); val_tensors.append(x)
    expected = np.asarray([labels.index(r["label"]) for r in val])
    model, mapping = initialize(args.init, labels)
    loader = DataLoader(TrainingClips(train, labels, args.version, args.seed, args.aspect_jitter), batch_size=args.batch,
        shuffle=True, generator=torch.Generator().manual_seed(args.seed), num_workers=0)
    weights = torch.tensor([1 / math.sqrt(counts[label]) for label in labels], dtype=torch.float32)
    weights /= weights.mean()
    criterion = torch.nn.CrossEntropyLoss(weight=weights, label_smoothing=.03)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=args.lr * .15)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    audit = {"featureSha256": digest(args.features), "initialCheckpoint": str(args.init),
        "initialCheckpointSha256": digest(args.init), "trainingSplit": "train", "selectionSplit": "val",
        "testUsedForSelection": False, "watchClipsUsedForTrainingOrCalibration": False,
        "trainAttempts": len(train_all), "trainUsable": len(train), "trainCounts": dict(sorted(counts.items())),
        "valAttempts": len(val), "valTracked": len(valid_indices), "syntheticTrainGreetings": sum(bool(r.get("syntheticGreeting")) for r in train),
        "syntheticValGreetings": sum(bool(r.get("syntheticGreeting")) for r in val), "initialLabelMapping": mapping,
        "greetingScope": "Synthetic joined isolated components; natural continuous greetings are not verified.",
        "seed": args.seed, "epochsRequested": args.epochs, "aspectJitter": args.aspect_jitter, "preprocessorVersion": args.version,
        "mirrorVersion": "anatomical-v2" if args.version == "masked-v2" else "legacy-v1"}
    best, history = -1, []
    print(f"{args.family}/{args.version}: {len(train)} usable train, {len(val)} validation attempts ({len(valid_indices)} tracked), {len(labels)} labels", flush=True)
    for epoch in range(1, args.epochs + 1):
        start = time.perf_counter(); model.train(); loss_sum = 0
        for x, y in loader:
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(x), y); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5)
            optimizer.step(); loss_sum += loss.item() * len(y)
        scheduler.step(); model.eval()
        probabilities = predict([model], val_tensors, mirror=True, anatomical=args.version == "masked-v2")
        correct = np.zeros(len(val), bool)
        correct[valid_indices] = probabilities.argmax(1) == expected[valid_indices]
        macro = np.mean([correct[expected == i].mean() for i in range(len(labels)) if (expected == i).any()])
        row = {"epoch": epoch, "loss": round(loss_sum / len(train), 4), "valCorrect": int(correct.sum()),
            "valAttempts": len(val), "valAccuracy": round(float(correct.mean()), 6), "valMacroAccuracy": round(float(macro), 6),
            "seconds": round(time.perf_counter() - start, 1),
            "greetings": {label: [int(correct[expected == labels.index(label)].sum()), int((expected == labels.index(label)).sum())]
                for label in ["MORNING", "GOOD MORNING", "GOOD AFTERNOON", "GOOD NIGHT"] if label in labels}}
        history.append(row)
        if macro > best:
            best = macro
            torch.save({"state_dict": copy.deepcopy(model.state_dict()), "labels": labels, "T": 32,
                "version": "motion-repair-20261107", "family": args.family, "epoch": epoch,
                "valAcc": float(correct.mean()), "valMacroAcc": float(macro), "mirrorTta": True,
                "preprocessorVersion": args.version, "mirrorVersion": audit["mirrorVersion"], "trainingAudit": audit}, args.out)
        args.out.with_suffix(".history.json").write_text(json.dumps({"audit": audit, "history": history}, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(row), flush=True)
    print(f"Saved validation-selected candidate: {args.out} (macro {best:.1%})", flush=True)


if __name__ == "__main__":
    main()
