"""Versioned, shared landmark preparation for training and server inference.

Old weights retain legacy-v1 features. Repaired weights opt into masked-v2:
missing hands remain zero after centering and cannot create phantom motion
when interpolation crosses a tracking gap. Mirroring swaps pose anatomy too.
"""
from __future__ import annotations

import numpy as np

HAND_POINTS = [0, 4, 5, 8, 9, 12, 13, 16, 17, 20]
POSE_MIRROR = [0, 2, 1, 4, 3, 6, 5]


def _points(value, count, name):
    try:
        points = np.asarray(value, dtype=np.float32)
    except (ValueError, TypeError) as error:
        raise ValueError(f"Invalid {name} landmarks") from error
    if points.ndim != 2 or points.shape[0] != count or points.shape[1] not in {2, 3}:
        raise ValueError(f"{name} must contain {count} two- or three-coordinate landmarks")
    if not np.isfinite(points).all() or np.abs(points).max() > 20:
        raise ValueError(f"Invalid {name} landmarks")
    return points[:, :2]


def arrays(frames, version="legacy-v1"):
    if version not in {"legacy-v1", "masked-v2"}:
        raise ValueError("Unknown landmark preprocessor version")
    coords, masks = [], []
    for frame in frames:
        if not isinstance(frame, dict):
            raise ValueError("Each landmark frame must be an object")
        pose = _points(frame.get("pose"), 7, "pose")
        hands = []
        mask = np.zeros((27, 2), np.float32)
        for side, start, column in (("left", 7, 0), ("right", 17, 1)):
            raw = frame.get(side)
            if raw is None or (isinstance(raw, list) and not raw):
                hands.append(np.zeros((10, 2), np.float32))
            else:
                hands.append(_points(raw, 21, side + " hand")[HAND_POINTS])
                mask[start:start + 10, column] = 1
        coords.append(np.concatenate([pose, *hands])); masks.append(mask)
    if not coords:
        raise ValueError("No landmark frames")
    c, m = np.stack(coords), np.stack(masks)
    center = ((c[:, 3] + c[:, 4]) / 2).mean(0)
    span = np.sqrt(((c[:, 3] - c[:, 4]) ** 2).sum(-1)).mean()
    if span > 1e-8:
        c = (c - center) / span
    if version == "masked-v2":
        c[:, 7:] *= m[:, 7:].sum(-1, keepdims=True)
    return c.astype(np.float32), m


def resample(c, m, length=32, version="legacy-v1"):
    if len(c) == length:
        return c, m
    idx = np.linspace(0, len(c) - 1, length)
    lo = np.floor(idx).astype(int); hi = np.minimum(lo + 1, len(c) - 1)
    w = (idx - lo)[:, None, None].astype(np.float32)
    nearest = np.round(idx).astype(int)
    result = c[lo] * (1 - w) + c[hi] * w
    mask = m[nearest]
    if version == "masked-v2":
        both = m[lo, 7:].sum(-1) * m[hi, 7:].sum(-1)
        result[:, 7:] = np.where(both[..., None] > 0, result[:, 7:], c[nearest, 7:])
        result[:, 7:] *= mask[:, 7:].sum(-1, keepdims=True)
    return result, mask


def frames_to_tensor(frames, version="legacy-v1", length=32):
    c, m = resample(*arrays(frames, version), length=length, version=version)
    return np.concatenate([c.transpose(2, 0, 1), m.transpose(2, 0, 1)], 0).astype(np.float32)


def validate_capture(frames, minimum=5, maximum=90):
    """Empty-hand frames are not evidence of a performed sign."""
    if not isinstance(frames, list) or not minimum <= len(frames) <= maximum:
        raise ValueError(f"Capture must contain {minimum} to {maximum} landmark frames")
    if any(not isinstance(frame, dict) for frame in frames):
        raise ValueError("Each landmark frame must be an object")
    observed = sum(any(isinstance(frame.get(side), list) and len(frame[side]) == 21
                       for side in ("left", "right")) for frame in frames)
    if observed < minimum:
        raise ValueError(f"Not enough hand-tracked frames ({observed}/{minimum}). Keep at least one hand visible.")


def tensorize(record, version="legacy-v1", length=32, minimum=5):
    frames = record.get("frames") or []
    if record.get("error") or len(frames) < minimum:
        return None
    try:
        validate_capture(frames, minimum=minimum, maximum=max(90, len(frames)))
        return frames_to_tensor(frames, version, length)
    except (ValueError, TypeError, IndexError):
        return None


def mirror_tensor(x, anatomical=False):
    out = x.copy(); out[0] *= -1
    if anatomical:
        out[:, :, :7] = out[:, :, POSE_MIRROR]
    out[:, :, 7:17], out[:, :, 17:27] = out[:, :, 17:27].copy(), out[:, :, 7:17].copy()
    out[2:4] = out[2:4][::-1].copy()
    return out
