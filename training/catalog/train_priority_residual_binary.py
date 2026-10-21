"""Train six independent body-and-hands residual decisions in one shared model."""
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn

import body_tip_features
import train_expansion_batch as batch
from train_motion_residual import augmented_batch


class BinaryResidual(nn.Module):
    def __init__(self, outputs, mean, scale):
        super().__init__()
        channels = torch.as_tensor(mean).numel()
        self.register_buffer("mean", torch.as_tensor(mean).reshape(1, channels, 1))
        self.register_buffer("scale", torch.as_tensor(scale).reshape(1, channels, 1))
        self.project = nn.Conv1d(channels * 2, 64, 1)
        self.blocks = nn.ModuleList([
            nn.Sequential(nn.Conv1d(64, 64, 3, padding=d, dilation=d),
                          nn.GroupNorm(8, 64), nn.GELU(), nn.Dropout(.2),
                          nn.Conv1d(64, 64, 3, padding=d, dilation=d))
            for d in (1, 2, 4)
        ])
        self.output = nn.Linear(128, outputs)

    def forward(self, value):
        value = ((value - self.mean) / self.scale).clamp(-8, 8)
        delta = torch.cat((torch.zeros_like(value[:, :, :1]),
                           value[:, :, 1:] - value[:, :, :-1]), 2)
        value = self.project(torch.cat((value, delta), 1))
        for block in self.blocks:
            value = nn.functional.gelu(value + block(value))
        return self.output(torch.cat((value.mean(2), value.amax(2)), 1))


def choose(rows, scores, word):
    positive = np.array([row["label"] == word for row in rows])
    trials = []
    negative_scores = scores[~positive]
    thresholds = set((.5, .65, .75, .85, .9, .95, .97, .98, .99, .995,
                      1.0000001))
    thresholds.update(float(score) + 1e-7 for score in negative_scores)
    for threshold in sorted(thresholds):
        output = scores >= threshold
        result = {"threshold": threshold,
                  "correct": int(np.sum(output & positive)),
                  "total": int(np.sum(positive)),
                  "negativeFalse": int(np.sum(output & ~positive)),
                  "negativeTotal": int(np.sum(~positive))}
        trials.append(result)
    eligible = [trial for trial in trials if trial["negativeFalse"] == 0]
    selected = max(eligible, key=lambda trial: (trial["correct"], -trial["threshold"]))
    selected["passesValidation"] = selected["correct"] >= selected["total"] * .5
    return selected, trials


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base = json.loads((args.baseline / "protocol.json").read_text())
    source = Path(base["source"])
    if hashlib.sha256(source.read_bytes()).hexdigest() != base["sourceSha256"]:
        raise ValueError("Development source changed")
    labels = base["labels"]
    train, val = batch.prepare(source, args.output, labels=labels,
                               separate_negatives=True)
    augmented = train + [batch.trainer.encoding.mirrored(row) for row in train]
    x = torch.tensor(np.stack([body_tip_features.features(row) for row in augmented]))
    vx = torch.tensor(np.stack([body_tip_features.features(row) for row in val]))
    y = torch.tensor([[float(row["label"] == word) for word in labels]
                      for row in augmented])
    mean, scale = x.mean((0, 2)), x.std((0, 2)).clamp(min=.1)
    positives = y.sum(0)
    pos_weight = ((len(y) - positives) / positives.clamp(min=1)).clamp(max=12)
    best = None
    torch.set_num_threads(2)
    for seed in (17, 29, 43):
        torch.manual_seed(seed)
        model = BinaryResidual(len(labels), mean, scale)
        optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.02)
        schedule = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, 60, eta_min=.00005)
        for epoch in range(1, 61):
            model.train()
            for ids in torch.randperm(len(x)).split(64):
                optimizer.zero_grad()
                loss = nn.functional.binary_cross_entropy_with_logits(
                    model(augmented_batch(x[ids], masked=True)), y[ids],
                    pos_weight=pos_weight)
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 5)
                optimizer.step()
            schedule.step()
            if epoch not in (20, 40, 60):
                continue
            model.eval()
            with torch.no_grad():
                scores = model(vx).sigmoid().numpy()
            selected, trials = {}, {}
            for index, word in enumerate(labels):
                selected[word], trials[word] = choose(val, scores[:, index], word)
            passes = all(item["passesValidation"] for item in selected.values())
            rank = (passes, sum(item["correct"] for item in selected.values()),
                    -sum(item["threshold"] for item in selected.values()))
            entry = {"seed": seed, "epoch": epoch, "words": selected,
                     "passesValidation": passes, "trials": trials}
            if best is None or rank > best[0]:
                best = (rank, entry)
                torch.save({"state": copy.deepcopy(model.state_dict()),
                            "labels": labels, "selected": selected},
                           args.output / "binary-residual-private.pt")
            print(json.dumps({"seed": seed, "epoch": epoch,
                              "passes": passes, "words": selected}), flush=True)
    checkpoint = args.output / "binary-residual-private.pt"
    result = {"selected": best[1],
              "checkpointSha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
              "sourceSha256": base["sourceSha256"], "deployed": False}
    (args.output / "binary-residual-validation.json").write_text(
        json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
