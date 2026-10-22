"""In-memory adapter for the Beginner-100 ST-GCN (missing words only).

Loads hs-eval/models/beginner100-v1.pt when present. Skipped words that already
have default/daily/extra/category models are intentionally absent from this
checkpoint's label list.
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent
ROOT = REPO / "third_party" / "microsoft_asl_citizen"
CKPT_CANDIDATES = [
    REPO.parent.parent / "hs-eval" / "models" / "beginner100-v1.pt",
    Path(r"C:\Users\Squid\Desktop\capstone\hs-eval\models\beginner100-v1.pt"),
    REPO / "models" / "beginner100-v1.pt",
]
LABEL_MAP = Path(r"C:\Users\Squid\Desktop\capstone\hs-eval\beginner-100\label-map.json")
HAND_POINTS = [0, 4, 5, 8, 9, 12, 13, 16, 17, 20]
EDGES = [
    [2, 0], [1, 0], [0, 3], [0, 4], [3, 5], [4, 6], [5, 7], [6, 17], [7, 8], [7, 9],
    [9, 10], [7, 11], [11, 12], [7, 13], [13, 14], [7, 15], [15, 16], [17, 18], [17, 19],
    [19, 20], [17, 21], [21, 22], [17, 23], [23, 24], [17, 25], [25, 26],
]
LOCK = threading.Lock()
_runtime = None
T = 32


class BeginnerASLError(ValueError):
    pass


def _checkpoint_path() -> Path | None:
    for path in CKPT_CANDIDATES:
        if path.exists():
            return path
    return None


def available() -> bool:
    return _checkpoint_path() is not None


def labels() -> list[str]:
    path = _checkpoint_path()
    if path and path.exists():
        try:
            import torch

            blob = torch.load(path, map_location="cpu", weights_only=False)
            return list(blob.get("labels") or [])
        except Exception:
            pass
    if LABEL_MAP.exists():
        return json.loads(LABEL_MAP.read_text(encoding="utf-8")).get("trainLabels", [])
    return []


def status() -> dict:
    labs = labels()
    return {
        "available": available(),
        "labels": labs,
        "vocabularySize": len(labs),
        "model": "HandSpeak ST-GCN beginner100-v1 (missing Beginner words)",
        "experimental": True,
        "liveCameraAccuracyVerified": False,
    }


def _load():
    global _runtime
    if _runtime:
        return _runtime
    with LOCK:
        if _runtime:
            return _runtime
        path = _checkpoint_path()
        if not path:
            raise BeginnerASLError("Beginner model checkpoint is unavailable.",)
        import torch

        sys.path.insert(0, str(ROOT))
        from architecture.st_gcn import STGCN
        from architecture.fc import FC
        from architecture.network import Network

        blob = torch.load(path, map_location="cpu", weights_only=False)
        label_list = list(blob["labels"])
        model = Network(
            STGCN(4, dict(num_nodes=27, center=0, inward_edges=EDGES), True),
            FC(256, len(label_list), dropout_ratio=0.15),
        ).eval()
        model.load_state_dict(blob["state_dict"])
        model.eval()
        _runtime = (torch, model, label_list, int(blob.get("T", T)))
        return _runtime


def recognize(payload):
    import numpy as np

    frames = payload.get("frames") if isinstance(payload, dict) else None
    if not isinstance(frames, list) or not 5 <= len(frames) <= 90:
        raise BeginnerASLError("Capture must contain 5 to 90 landmark frames")
    torch, model, label_list, length = _load()
    coords_list, masks_list = [], []
    for frame in frames:
        pose = np.asarray(frame.get("pose", [[]]), dtype=np.float32)
        if pose.ndim != 2 or pose.shape[0] != 7:
            raise BeginnerASLError("pose must contain 7 landmarks")
        pose = pose[:, :2]
        left_raw = frame.get("left")
        right_raw = frame.get("right")
        lh = np.asarray(left_raw, dtype=np.float32)[HAND_POINTS] if left_raw else np.zeros((10, 2), np.float32)
        rh = np.asarray(right_raw, dtype=np.float32)[HAND_POINTS] if right_raw else np.zeros((10, 2), np.float32)
        coords_list.append(np.concatenate([pose, lh[:, :2], rh[:, :2]], 0))
        left_mask = np.zeros(27, np.float32)
        right_mask = np.zeros(27, np.float32)
        if left_raw:
            left_mask[7:17] = 1.0
        if right_raw:
            right_mask[17:27] = 1.0
        masks_list.append(np.stack([left_mask, right_mask], 1))
    coords = np.stack(coords_list).astype(np.float32)
    masks = np.stack(masks_list).astype(np.float32)
    center = ((coords[:, 3] + coords[:, 4]) / 2).mean(0)
    distance = np.sqrt(((coords[:, 3] - coords[:, 4]) ** 2).sum(-1)).mean()
    if distance > 1e-8:
        coords = (coords - center) / distance
    n = len(coords)
    if n != length:
        idx = np.linspace(0, n - 1, length)
        lo = np.floor(idx).astype(int)
        hi = np.minimum(lo + 1, n - 1)
        w = (idx - lo)[:, None, None].astype(np.float32)
        coords = coords[lo] * (1 - w) + coords[hi] * w
        masks = masks[np.round(idx).astype(int)]
    tensor = np.concatenate([coords.transpose(2, 0, 1), masks.transpose(2, 0, 1)], 0)
    batch = torch.tensor(tensor[None].astype(np.float32))
    with LOCK, torch.no_grad():
        probs = torch.softmax(model(batch), 1)[0].numpy()
    ranking = np.argsort(probs)[::-1][:5]
    predictions = [
        {"label": label_list[int(i)], "score": round(float(probs[i]), 6)} for i in ranking
    ]
    min_score = payload.get("minScore")
    if not (isinstance(min_score, (int, float)) and 0 < min_score < 1):
        min_score = 0.50
    low_confidence = False
    if predictions and predictions[0]["score"] < min_score:
        predictions = []
        low_confidence = True
    return {
        "predictions": predictions,
        "segment": "full-clip",
        "activeFrames": [0, len(frames) - 1],
        "frames": len(frames),
        "model": "HandSpeak ST-GCN beginner100-v1",
        "vocabulary": "beginner",
        "vocabularySize": len(label_list),
        "minScore": min_score,
        "lowConfidence": low_confidence,
        "experimental": True,
    }
