"""Shared, versioned feature math for offline model selection and repair."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "third_party/microsoft_asl_citizen"))
from architecture.st_gcn import STGCN
from architecture.fc import FC
from architecture.network import Network

sys.path.insert(0, str(REPO))
from sign_features import arrays, resample, tensorize, mirror_tensor

HAND_POINTS = [0, 4, 5, 8, 9, 12, 13, 16, 17, 20]
EDGES = [[2, 0], [1, 0], [0, 3], [0, 4], [3, 5], [4, 6], [5, 7], [6, 17], [7, 8], [7, 9],
    [9, 10], [7, 11], [11, 12], [7, 13], [13, 14], [7, 15], [15, 16], [17, 18], [17, 19],
    [19, 20], [17, 21], [21, 22], [17, 23], [23, 24], [17, 25], [25, 26]]
GRAPH = dict(num_nodes=27, center=0, inward_edges=EDGES)
POSE_MIRROR = [0, 2, 1, 4, 3, 6, 5]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_model(labels):
    return Network(STGCN(4, GRAPH, True), FC(256, len(labels), dropout_ratio=.15))


def load_checkpoint(path):
    blob = torch.load(path, map_location="cpu", weights_only=False)
    labels = list(blob["labels"])
    if len(set(labels)) != len(labels):
        raise ValueError("Duplicate checkpoint labels")
    states = [s["state_dict"] for s in blob.get("snapshots", [])] or [blob["state_dict"]]
    models = []
    for state in states:
        model = make_model(labels).eval();model.load_state_dict(state);models.append(model)
    return models, labels, blob


def predict(models, tensors, mirror=False, anatomical=False, batch=16):
    outputs = []
    with torch.inference_mode():
        for start in range(0, len(tensors), batch):
            values = tensors[start:start + batch]
            views = np.stack(values)
            if mirror:
                views = np.concatenate([views, np.stack([mirror_tensor(x, anatomical) for x in values])])
            x = torch.from_numpy(views)
            total = None
            for model in models:
                p = torch.softmax(model(x), 1)
                if mirror:
                    p = (p[:len(values)] + p[len(values):]) / 2
                total = p if total is None else total + p
            outputs.append((total / len(models)).numpy())
    return np.concatenate(outputs) if outputs else np.empty((0, 0), np.float32)


def load_rows(path, split, labels=None):
    allowed = set(labels) if labels else None
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        label = row.get("label") or row.get("gloss")
        if row.get("split") == split and (allowed is None or label in allowed):
            row["label"] = label;rows.append(row)
    return rows
