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
HS_EVAL = REPO.parent.parent / "hs-eval"
# Prefer latest denser Beginner checkpoints first.
# Prefer v2 over v3: same target-word readiness, slightly higher overall top-1.
CKPT_CANDIDATES = [
    REPO / "models" / "beginner-need79-v6.pt",
    HS_EVAL / "models" / "beginner-need79-v6.pt",
    REPO / "models" / "beginner-need79-v5.pt",
    HS_EVAL / "models" / "beginner-need79-v5.pt",
    REPO / "models" / "beginner-need79-v7.pt",
    HS_EVAL / "models" / "beginner-need79-v7.pt",
    REPO / "models" / "beginner-need79-v4.pt",
    HS_EVAL / "models" / "beginner-need79-v4.pt",
    REPO / "models" / "beginner-need79-v2.pt",
    HS_EVAL / "models" / "beginner-need79-v2.pt",
    REPO / "models" / "beginner-need79-v3.pt",
    HS_EVAL / "models" / "beginner-need79-v3.pt",
    REPO / "models" / "beginner-need79-v1.pt",
    HS_EVAL / "models" / "beginner-need79-v1.pt",
    REPO / "models" / "beginner-phase123-v2.pt",
    HS_EVAL / "models" / "beginner-phase123-v2.pt",
    REPO / "models" / "beginner-phase123-v3.pt",
    HS_EVAL / "models" / "beginner-phase123-v3.pt",
    REPO / "models" / "beginner-phase123-v1.pt",
    HS_EVAL / "models" / "beginner-phase123-v1.pt",
    REPO / "models" / "beginner-phase12-v2.pt",
    HS_EVAL / "models" / "beginner-phase12-v2.pt",
    REPO / "models" / "beginner-phase12-v1.pt",
    HS_EVAL / "models" / "beginner-phase12-v1.pt",
    REPO / "models" / "beginner-phase1-v1.pt",
    HS_EVAL / "models" / "beginner-phase1-v1.pt",
    REPO / "models" / "beginner100-v1.pt",
    HS_EVAL / "models" / "beginner100-v1.pt",
]
LABEL_MAP_CANDIDATES = [
    REPO / "models" / "beginner-100-label-map.json",
    HS_EVAL / "beginner-100" / "label-map.json",
]
READY_LABEL_CANDIDATES = [
    REPO / "models" / "beginner-ready-labels.json",
    HS_EVAL / "beginner-100" / "beginner-ready-labels.json",
]
HAND_POINTS = [0, 4, 5, 8, 9, 12, 13, 16, 17, 20]
EDGES = [
    [2, 0], [1, 0], [0, 3], [0, 4], [3, 5], [4, 6], [5, 7], [6, 17], [7, 8], [7, 9],
    [9, 10], [7, 11], [11, 12], [7, 13], [13, 14], [7, 15], [15, 16], [17, 18], [17, 19],
    [19, 20], [17, 21], [21, 22], [17, 23], [23, 24], [17, 25], [25, 26],
]
LOCK = threading.Lock()
_runtime = None
_extra = {}
T = 32
# v8 clears these three, but using it as the open model drops other ready words.
CLOSED_PRACTICE = ("SCHOOL", "SISTER", "WE")
V8_CANDIDATES = [
    REPO / "models" / "beginner-need79-v8.pt",
    HS_EVAL / "models" / "beginner-need79-v8.pt",
]


class BeginnerASLError(ValueError):
    pass


def _first_existing(paths):
    for path in paths:
        if path.exists():
            return path
    return None


def _checkpoint_path() -> Path | None:
    return _first_existing(CKPT_CANDIDATES)


def _ready_meta() -> dict:
    path = _first_existing(READY_LABEL_CANDIDATES)
    if not path:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def available() -> bool:
    return _checkpoint_path() is not None


def all_labels() -> list[str]:
    path = _checkpoint_path()
    if path and path.exists():
        try:
            import torch

            blob = torch.load(path, map_location="cpu", weights_only=False)
            return list(blob.get("labels") or [])
        except Exception:
            pass
    label_map = _first_existing(LABEL_MAP_CANDIDATES)
    if label_map:
        return json.loads(label_map.read_text(encoding="utf-8")).get("trainLabels", [])
    return []


def ready_labels() -> list[str]:
    meta = _ready_meta()
    ready = meta.get("labels") if isinstance(meta, dict) else None
    if isinstance(ready, list) and ready:
        known = set(all_labels())
        filtered = [label for label in ready if not known or label in known]
        return filtered or list(ready)
    return all_labels()


def labels() -> list[str]:
    """Public online vocabulary: ready (≥70%) Beginner words only."""
    return ready_labels()


def status() -> dict:
    labs = labels()
    trained = all_labels()
    path = _checkpoint_path()
    name = path.name if path else "unavailable"
    meta = _ready_meta()
    if "need79-v6" in name:
        model_name = "HandSpeak ST-GCN beginner-need79-v6 (hard8 push)"
        phase = "need79-v6"
    elif "need79-v5" in name:
        model_name = "HandSpeak ST-GCN beginner-need79-v5 (hard8 boost)"
        phase = "need79-v5"
    elif "need79-v7" in name:
        model_name = "HandSpeak ST-GCN beginner-need79-v7 (hard4 push)"
        phase = "need79-v7"
    elif "need79-v4" in name:
        model_name = "HandSpeak ST-GCN beginner-need79-v4 (hard28 remainder)"
        phase = "need79-v4"
    elif "need79-v3" in name:
        model_name = "HandSpeak ST-GCN beginner-need79-v3 (recover-hard)"
        phase = "need79-v3"
    elif "need79-v2" in name:
        model_name = "HandSpeak ST-GCN beginner-need79-v2 (expanded ready)"
        phase = "need79-v2"
    elif "need79" in name:
        model_name = "HandSpeak ST-GCN beginner-need79-v1 (expanded)"
        phase = "need79-v1"
    elif "phase123-v3" in name:
        model_name = "HandSpeak ST-GCN beginner-phase123-v3 (hard-word fine-tune)"
        phase = "1-3-v3"
    elif "phase123-v2" in name:
        model_name = "HandSpeak ST-GCN beginner-phase123-v2 (ready-boost)"
        phase = "1-3-v2"
    elif "phase123" in name:
        model_name = "HandSpeak ST-GCN beginner-phase123-v1 (phases 1–3 denser)"
        phase = "1-3"
    elif "phase12-v2" in name or "phase12_v2" in name:
        model_name = "HandSpeak ST-GCN beginner-phase12-v2 (weak-word boost)"
        phase = "1-2-v2"
    elif "phase12" in name:
        model_name = "HandSpeak ST-GCN beginner-phase12-v1 (phases 1–2 denser)"
        phase = "1-2"
    elif "phase1" in name:
        model_name = "HandSpeak ST-GCN beginner-phase1-v1 (greetings/questions/pronouns)"
        phase = 1
    else:
        model_name = "HandSpeak ST-GCN beginner100-v1 (missing Beginner words)"
        phase = "full-missing"
    return {
        "available": available() and bool(labs),
        "labels": labs,
        "vocabularySize": len(labs),
        "trainedLabels": trained,
        "trainedVocabularySize": len(trained),
        "readyThreshold": meta.get("threshold", 0.70),
        "accuracy": meta.get("accuracy") or {},
        "model": model_name,
        "checkpoint": name,
        "phase": phase,
        "experimental": True,
        "liveCameraAccuracyVerified": False,
    }


def _build_runtime(path: Path):
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
    return torch, model, label_list, int(blob.get("T", T))


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
        _runtime = _build_runtime(path)
        return _runtime


def _load_v8():
    if "v8" in _extra:
        return _extra["v8"]
    with LOCK:
        if "v8" in _extra:
            return _extra["v8"]
        path = _first_existing(V8_CANDIDATES)
        if not path:
            raise BeginnerASLError("The SCHOOL / SISTER / WE practice model is unavailable.")
        _extra["v8"] = _build_runtime(path)
        return _extra["v8"]


def _active_span(coords, masks):
    """Keep the moving part of a capture so a short sign is not diluted by a hold."""
    import numpy as np

    count = len(coords)
    if count < 5:
        return coords, masks
    hands = coords[:, 7:27]
    step = np.linalg.norm(hands[1:] - hands[:-1], axis=(1, 2))
    motion = np.zeros(count, np.float32)
    motion[1:] = step
    motion[:-1] = np.maximum(motion[:-1], step)
    peak = float(motion.max())
    if peak < 1e-4:
        return coords, masks
    chosen = np.flatnonzero(motion >= peak * 0.2)
    if len(chosen) < 3:
        return coords, masks
    start = max(0, int(chosen[0]) - 1)
    end = min(count, int(chosen[-1]) + 2)
    if end - start < 3:
        return coords, masks
    return coords[start:end], masks[start:end]


def recognize(payload):
    import numpy as np

    frames = payload.get("frames") if isinstance(payload, dict) else None
    if not isinstance(frames, list) or not 3 <= len(frames) <= 90:
        raise BeginnerASLError("Capture must contain 3 to 90 landmark frames")
    closed = payload.get("closedLabels") if isinstance(payload, dict) else None
    use_closed = (
        isinstance(closed, list)
        and closed
        and set(closed) <= set(CLOSED_PRACTICE)
    )
    torch, model, label_list, length = _load_v8() if use_closed else _load()
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
    coords, masks = _active_span(coords, masks)
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
    ready = set(closed) if use_closed else set(ready_labels())
    if ready:
        scored = [
            (i, float(probs[i]))
            for i, label in enumerate(label_list)
            if label in ready
        ]
        # The network softmax is over the full training vocabulary. Renormalize
        # over the labels this request can return, matching the other HandSpeak
        # models. Held-out: open 0.50 keeps 323 correct and 15 wrong (raw 0.50
        # hid 152 correct). Closed three-word 0.50 keeps 33 correct and 0 wrong.
        mass = sum(score for _, score in scored)
        if mass > 0:
            scored = [(i, score / mass) for i, score in scored]
        scored.sort(key=lambda item: item[1], reverse=True)
        predictions = [
            {"label": label_list[i], "score": round(score, 6)} for i, score in scored[:5]
        ]
    else:
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
        "model": status().get("model", "HandSpeak ST-GCN beginner"),
        "vocabulary": "beginner-ready",
        "vocabularySize": len(ready) if ready else len(label_list),
        "minScore": min_score,
        "lowConfidence": low_confidence,
        "experimental": True,
    }
