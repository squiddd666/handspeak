"""Versioned body-location + wrist-relative full-handshape features.

Hand z values are local to each detected wrist, unlike pose z. Never center
them together. Missing hands stay zero and are not interpolated across gaps.
The representation is independent of a practice label and source video.
"""
from __future__ import annotations
import numpy as np
from sign_features import _points, validate_capture

VERSION = "body-handshape-v1"
CHANNELS = 146
LENGTH = 32
POSE_MIRROR = [0, 2, 1, 4, 3, 6, 5]


def raw_arrays(frames):
    pose = np.stack([_points(f.get("pose"), 7, "pose") for f in frames])
    hands = np.zeros((len(frames), 2, 21, 3), np.float32)
    visible = np.zeros((len(frames), 2), np.float32)
    for t, frame in enumerate(frames):
        for side, name in enumerate(("left", "right")):
            points = frame.get(name)
            if points is None or (isinstance(points, list) and not points):
                continue
            xy = _points(points, 21, name)
            hands[t, side, :, :2] = xy
            if np.asarray(points).shape[1] == 3:
                hands[t, side, :, 2] = np.asarray(points, np.float32)[:, 2]
            visible[t, side] = 1
    return pose, hands, visible


def encode(pose, hands, visible, length=LENGTH):
    center = ((pose[:, 3] + pose[:, 4]) / 2).mean(0)
    span = np.linalg.norm(pose[:, 3] - pose[:, 4], axis=-1).mean()
    if span < 1e-5:
        raise ValueError("Degenerate shoulders")
    body = (pose - center) / span
    wrists = (hands[:, :, 0, :2] - center) / span
    wrists *= visible[..., None]
    shape = hands - hands[:, :, :1]
    palm = np.linalg.norm(shape[:, :, 9], axis=-1)
    # A clip-level palm scale avoids framewise scale jitter; each hand remains
    # independent. Absence is explicit, not a giant displaced phantom hand.
    for side in range(2):
        present = visible[:, side] > 0
        scale = np.median(palm[present, side]) if present.any() else 1
        shape[:, side] /= max(float(scale), .01)
    shape *= visible[..., None, None]
    values = np.concatenate([body.reshape(len(body), 14), wrists.reshape(len(body), 4),
                             shape.reshape(len(body), 126), visible], axis=1)
    index = np.linspace(0, len(values) - 1, length)
    lo = np.floor(index).astype(int); hi = np.minimum(lo + 1, len(values) - 1)
    nearest = np.round(index).astype(int); w = (index - lo)[:, None]
    out = values[lo] * (1 - w) + values[hi] * w
    for side in range(2):
        both = (visible[lo, side] * visible[hi, side]) > 0
        for block in (slice(14 + side * 2, 16 + side * 2), slice(18 + side * 63, 81 + side * 63)):
            out[:, block] = np.where(both[:, None], out[:, block], values[nearest, block])
            out[:, block] *= visible[nearest, side, None]
    out[:, -2:] = visible[nearest]
    return np.clip(out.T, -10, 10).astype(np.float32)


def frames_to_handshape(frames, length=LENGTH):
    return encode(*raw_arrays(frames), length=length)


def tensorize(row):
    try:
        frames = row.get("frames") or []
        if row.get("error"):
            return None
        validate_capture(frames, maximum=max(90, len(frames)))
        return frames_to_handshape(frames)
    except (ValueError, TypeError, IndexError):
        return None


def mirror(x):
    out = x.copy()
    pose = out[:14].reshape(7, 2, -1).copy()[POSE_MIRROR]
    pose[:, 0] *= -1
    out[:14] = pose.reshape(14, -1)
    wrist = out[14:18].reshape(2, 2, -1).copy()[::-1]
    wrist[:, 0] *= -1
    out[14:18] = wrist.reshape(4, -1)
    shape = out[18:144].reshape(2, 21, 3, -1).copy()[::-1]
    shape[:, :, 0] *= -1
    out[18:144] = shape.reshape(126, -1)
    out[-2:] = out[-2:][::-1].copy()
    return out
