"""Re-freeze a single-word candidate at a stricter cutoff, keeping the original on disk.

Same weights (checkpoint hash unchanged); only the decision threshold and the development
screens computed at that threshold change. The previous candidate is preserved as
frozen-at<old-threshold>/ so the original freeze stays reproducible.
"""
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import torch

from body_tip_features import features
from camera_framing import scaled
from train_motion_residual import MotionNet, batch
from calibrate_word_thresholds import predictions, sha, write

TRAIN = Path("/opt/handspeak-training/single-word-20261010")
SCALES = [1, .5625, 1.3]


def main(word, new_threshold):
    root = TRAIN / word.lower() / "frozen"
    p = json.loads((root / "protocol.json").read_text())
    old = p["thresholdByLabel"][word]
    if new_threshold <= old:
        raise SystemExit(f"new threshold {new_threshold} is not stricter than {old}")
    backup = TRAIN / word.lower() / f"frozen-at{str(old).replace('.', '')}"
    if backup.exists():
        raise SystemExit(f"backup {backup} already exists")
    shutil.copytree(root, backup)
    print("backup:", backup)

    data = json.loads(Path(p["source"]).read_text())
    val = [r for r in data if r["split"] == "val"]
    del data

    saved = torch.load(root / "frozen.pt", weights_only=True)
    torch.set_num_threads(1)
    net = MotionNet(len(p["outputLabels"]), torch.zeros(175), torch.ones(175)).eval()
    net.load_state_dict(saved["states"][0])
    batch.trainer.LABELS = p["labels"]

    q = dict(p, threshold=new_threshold, thresholdByLabel={word: new_threshold})
    screens = []
    for factor in SCALES:
        rows = [scaled(r, factor) for r in val]
        with torch.no_grad():
            probs = net(torch.tensor(np.stack([features(r) for r in rows]))).softmax(1).numpy()
        screens.append(dict(scale=factor, metrics=batch.trainer.metrics(rows, predictions(rows, probs, q))))

    if not all(batch.trainer.gate(s["metrics"]) for s in screens):
        raise SystemExit("development gate fails at this threshold: " + json.dumps([s["metrics"] for s in screens]))

    q["threshold"] = new_threshold
    q["selection"] = (f"Stricter cutoff {new_threshold} re-frozen from the same checkpoint after the "
                      f"known-recording regression screen flagged one false suggestion at {old}; "
                      "development screens replayed at the new cutoff before any fresh test.")
    write(root / "protocol.json", q)
    write(root / "validation.json", dict(passesDevelopmentScreen=True, framingValidation=screens,
                                         checkpointSha256=q["checkpointSha256"], deployed=False))
    print(json.dumps(dict(word=word, old=old, new=new_threshold,
                          screens=[s["metrics"] for s in screens])))


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]))
