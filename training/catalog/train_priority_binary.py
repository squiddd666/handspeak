"""Train compact per-word binary temporal candidates on development data only."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn

import train_expansion_batch as batch

WORDS = ("HELLO", "DRINK", "BOOK", "HUNGRY", "HOME", "FISH")
torch.set_num_threads(2)


class BinaryTemporal(nn.Module):
    def __init__(self, width=32):
        super().__init__()
        self.input = nn.Conv1d(153, width, 5, padding=2)
        self.blocks = nn.ModuleList([
            nn.Conv1d(width, width, 3, padding=dilation, dilation=dilation)
            for dilation in (1, 2, 4)
        ])
        self.output = nn.Linear(width * 2, 1)

    def forward(self, value):
        value = torch.relu(self.input(value))
        for layer in self.blocks:
            value = torch.relu(value + layer(value))
        pooled = torch.cat((value.mean(2), value.amax(2)), 1)
        return self.output(pooled).squeeze(1)


def mirrored(row):
    return batch.trainer.encoding.mirrored(row)


def metrics(rows, scores, word, threshold):
    outputs = scores >= threshold
    positive = np.array([row["label"] == word for row in rows])
    return {
        "correct": int(np.sum(outputs & positive)), "total": int(np.sum(positive)),
        "missed": int(np.sum(~outputs & positive)),
        "negativeFalse": int(np.sum(outputs & ~positive)),
        "negativeTotal": int(np.sum(~positive)),
    }


def choose(rows, scores, word):
    negatives = scores[[row["label"] != word for row in rows]]
    # Candidate thresholds are development outcomes plus conservative fixed points.
    values = sorted(set([.5, .7, .8, .9, .95, .97, .98, .99, .995]
                        + [float(value) + 1e-7 for value in negatives]))
    # A threshold just above 1 is the valid reject-all fallback when a checkpoint
    # assigns a saturated score to a negative example.
    values.append(1.0000001)
    trials = [{"threshold": value, "validation": metrics(rows, scores, word, value)}
              for value in sorted(set(values)) if value <= 1.0000001]
    eligible = [trial for trial in trials if trial["validation"]["negativeFalse"] == 0]
    best = max(eligible, key=lambda trial: (trial["validation"]["correct"], -trial["threshold"]))
    best["passesValidation"] = (best["validation"]["correct"] >= best["validation"]["total"] * .5
                                        and best["validation"]["negativeFalse"] == 0)
    return best, trials


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("word", help="Single uppercase-compatible vocabulary label")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--tag", default="v1")
    args = parser.parse_args()
    word = args.word.upper()
    if not word or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ -'" for character in word):
        parser.error("word must contain only letters, spaces, apostrophes, or hyphens")
    source = args.source or Path(f"/opt/handspeak-training/priority-citizen-balanced-{args.word}-source.json")
    root = Path(f"/opt/handspeak-training/priority-binary-{args.word}-{args.tag}")
    root.mkdir(parents=True, exist_ok=True)
    rows = json.loads(source.read_text())
    train = [row for row in rows if row["split"] == "train" and row.get("sequence") is not None]
    val = [row for row in rows if row["split"] == "val"]
    if {row["participant"] for row in train} & {row["participant"] for row in val}:
        raise ValueError("Participant overlap")
    augmented = train + [mirrored(row) for row in train]
    x = torch.tensor(np.stack([batch.trainer.encoding.features(row) for row in augmented]))
    y = torch.tensor([float(row["label"] == word) for row in augmented])
    vx = torch.tensor(np.stack([batch.trainer.encoding.features(row) for row in val]))
    positives = int(y.sum())
    pos_weight = torch.tensor(min(12.0, (len(y) - positives) / max(1, positives)))
    protocol = {
        "word": word, "source": str(source),
        "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "architecture": "dilated residual temporal binary classifier, mean+max pooling",
        "trainClips": len(train), "validationClips": len(val),
        "positiveTrain": sum(row["label"] == word for row in train),
        "positiveValidation": sum(row["label"] == word for row in val),
        "selection": "Threshold and checkpoint selected on development validation only; zero negative accepts required.",
        "releaseGate": "At least 50% development positives, zero development negative accepts, then frozen regression and browser checks.",
        "deployed": False,
    }
    (root / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    best, all_trials = None, []
    for seed in (17, 29):
        torch.manual_seed(seed)
        model = BinaryTemporal(32)
        optimizer = torch.optim.AdamW(model.parameters(), lr=.002, weight_decay=.01)
        for epoch in range(1, 61):
            model.train()
            for ids in torch.randperm(len(x)).split(64):
                value = x[ids] + torch.randn_like(x[ids]) * .012
                optimizer.zero_grad()
                loss = nn.functional.binary_cross_entropy_with_logits(
                    model(value), y[ids], pos_weight=pos_weight)
                loss.backward(); optimizer.step()
            if epoch not in (10, 20, 40, 60):
                continue
            model.eval()
            with torch.no_grad():
                scores = model(vx).sigmoid().numpy()
            selected, trials = choose(val, scores, word)
            entry = {"seed": seed, "epoch": epoch, **selected}
            all_trials.extend({"seed": seed, "epoch": epoch, **trial} for trial in trials)
            if best is None or (entry["passesValidation"], entry["validation"]["correct"],
                                -entry["threshold"]) > (best["passesValidation"],
                                best["validation"]["correct"], -best["threshold"]):
                best = entry
                torch.save({"state": copy.deepcopy(model.state_dict()), "config": entry}, root / "binary-private.pt")
            print(word, seed, epoch, best["validation"], flush=True)
    best["sha256"] = hashlib.sha256((root / "binary-private.pt").read_bytes()).hexdigest()
    (root / "validation.json").write_text(json.dumps({"selected": best, "trials": all_trials}, indent=2) + "\n")
    print(json.dumps(best), flush=True)


if __name__ == "__main__":
    main()
