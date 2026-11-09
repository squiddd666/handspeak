"""Body-located hand motion in physical image-width units, no target label.

The aspect ratio is height/width. Hand depth stays wrist-relative; pose depth
is never mixed with it. Missing hands remain explicit in the final masks.
"""
from __future__ import annotations

import numpy as np
from handshape_features import raw_arrays, encode, mirror
from sign_features import validate_capture

VERSION = "body-manual-aspect-v1"
LENGTH = 20


def tensorize(row):
    try:
        frames = row.get("frames") or []
        validate_capture(frames, maximum=max(90, len(frames)))
        aspect = row["imageAspect"]
        if type(aspect) not in (int, float) or not np.isfinite(aspect) or not .2 <= aspect <= 5:
            raise ValueError("Invalid capture aspect")
        pose, hands, visible = raw_arrays(frames)
        pose[..., 1] *= aspect
        hands[..., 1] *= aspect
        return encode(pose, hands, visible, length=LENGTH).T
    except (KeyError, ValueError, TypeError, IndexError):
        return None


def mirrored(sequence):
    return mirror(np.asarray(sequence).T).T


def dtw_many(sequence, references, wrist_weight=1., shape_weight=.5, pose_weight=.15, missing_cost=.75):
    """Banded distance vectorized over independent reference sequences."""
    a = np.asarray(sequence, np.float64)
    refs = np.asarray(references, np.float64)
    n, length, channels = refs.shape
    if a.shape != (length, 146) or channels != 146:
        raise ValueError("Body motion dimensions differ")
    def rms(x, y):
        # Avoid allocating [references, time, time, 63] deltas for every clip.
        # The dot-product identity is the same Euclidean cost, with rounding
        # clamped only at zero (not a matching threshold change).
        squared = (np.sum(x*x, axis=1)[None, :, None] +
                   np.sum(y*y, axis=2)[:, None, :] - 2*np.einsum('ic,njc->nij', x, y))
        return np.sqrt(np.maximum(0, squared) / x.shape[1])
    cost = pose_weight * rms(a[:, :14], refs[:, :, :14])
    for side in range(2):
        both = a[None, :, None, 144+side] * refs[:, None, :, 144+side]
        mismatch = a[None, :, None, 144+side] != refs[:, None, :, 144+side]
        wrist = slice(14+side*2, 16+side*2)
        shape = slice(18+side*63, 81+side*63)
        wrist_d = rms(a[:, wrist], refs[:, :, wrist])
        weights = np.tile([1., 1., .5], 21)
        shape_d = rms(a[:, shape]*weights, refs[:, :, shape]*weights)
        cost += (wrist_weight * wrist_d + shape_weight * shape_d) * both + missing_cost * mismatch
    previous = np.full((n, length+1), np.inf)
    previous[:, 0] = 0
    for i in range(1, length+1):
        current = np.full((n, length+1), np.inf)
        for j in range(max(1, i-5), min(length, i+5)+1):
            current[:, j] = cost[:, i-1, j-1] + np.minimum(np.minimum(previous[:, j], current[:, j-1]), previous[:, j-1])
        previous = current
    return previous[:, -1] / length
