"""Checkpoint-bound rejection policies; calibrated scores are not certainty."""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

POLICIES = Path(__file__).resolve().parent / "models/motion-calibration.json"


@lru_cache(maxsize=16)
def _digest(path, modified, size):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checkpoint_digest(path):
    stat = Path(path).stat()
    return _digest(str(Path(path).resolve()), stat.st_mtime_ns, stat.st_size)


def policy_for(family, checkpoint, vocabulary="full"):
    try:
        data = json.loads(POLICIES.read_text(encoding="utf-8"))
        profile = data["models"][family]
        if data.get("version") != 1 or profile["checkpointSha256"] != checkpoint_digest(checkpoint):
            return None
        policy = dict(profile["policies"][vocabulary])
        policy["calibrationId"] = data["calibrationId"]
        return policy
    except (OSError, ValueError, KeyError, TypeError):
        return None


def decide(probabilities, labels, allowed=None, policy=None, min_score=None):
    """Choose from actual model outputs, never from an expected practice label."""
    p = np.asarray(probabilities, np.float64)
    if p.shape != (len(labels),) or not np.isfinite(p).all() or np.any(p < 0) or p.sum() <= 0:
        raise ValueError("Invalid model probabilities")
    p /= p.sum()
    selected = list(range(len(labels))) if allowed is None else list(allowed)
    if not selected:
        raise ValueError("Empty model vocabulary")
    mass = float(p[selected].sum())
    normalized = p[selected] / max(mass, 1e-15)
    ranking = np.argsort(normalized)[::-1][:5]
    suggestions = [{"label": labels[selected[int(i)]], "score": round(float(normalized[i]), 6)} for i in ranking]
    score = float(normalized[ranking[0]])
    margin = score - (float(normalized[ranking[1]]) if len(ranking) > 1 else 0)
    policy = policy or {}
    # Apply only the policy for the model's ACTUAL top class. Practice labels
    # are deliberately absent from this API and cannot affect recognition.
    policy = {**policy, **policy.get("classPolicies", {}).get(suggestions[0]["label"], {})}
    explicit = type(min_score) in (int, float) and np.isfinite(min_score) and 0 < min_score < 1
    gate = float(min_score if explicit else policy.get("minScore", 0))
    reason = "outside-vocabulary" if mass < policy.get("minVocabularyMass", 0) else "low-score" if score < gate else "ambiguous" if margin < policy.get("minMargin", 0) else None
    return {"predictions": [] if reason else suggestions, "suggestions": suggestions,
        "minScore": gate or None, "minMargin": float(policy.get("minMargin", 0)),
        "vocabularyMass": round(mass, 6), "lowConfidence": bool(reason), "rejectionReason": reason,
        "calibrationId": policy.get("calibrationId"), "scoresAreCalibratedConfidence": False}
