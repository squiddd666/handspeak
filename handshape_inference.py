"""Optional checkpoint-bound handshape fusion; no practice-label input.

Absent configuration preserves legacy inference exactly. Configured auxiliary
weights must match their published digest and vocabulary, or inference fails
closed rather than quietly applying gates to different model outputs.
"""
from __future__ import annotations
import json, threading
from pathlib import Path
import numpy as np
from motion_calibration import checkpoint_digest

REPO = Path(__file__).resolve().parent
CONFIG = REPO / "models/motion-calibration.json"
LOCK = threading.Lock()
_loaded = {}


def configuration(family, base_digest):
    data = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
    profile = data.get("models",{}).get(family,{})
    auxiliary = profile.get("auxiliary")
    if not auxiliary or profile.get("checkpointSha256") != base_digest:
        return None
    path = (REPO / auxiliary["checkpoint"]).resolve()
    if path.parent != (REPO / "models").resolve():
        raise ValueError("Auxiliary checkpoint must be in the model directory")
    if checkpoint_digest(path) != auxiliary["checkpointSha256"]:
        raise ValueError("Auxiliary checkpoint differs from frozen calibration")
    if auxiliary.get("featureVersion") != "body-handshape-v1":
        raise ValueError("Unknown auxiliary feature version")
    for weight in auxiliary["weights"].values():
        if type(weight) not in (int,float) or not np.isfinite(weight) or not 0 <= weight <= 1:
            raise ValueError("Invalid auxiliary fusion weight")
    return {**auxiliary,"path":path}


def _load(config, labels):
    key = str(config["path"])
    with LOCK:
        if key in _loaded:
            model, names, blob, identity = _loaded[key]
            if identity != config["checkpointSha256"]:
                raise ValueError("Auxiliary checkpoint changed. Restart the server.")
        else:
            from handshape_model import load
            model,names,blob = load(config["path"])
            identity = config["checkpointSha256"]
            _loaded[key] = model,names,blob,identity
        if len(names) != len(labels)+1 or set(names) != set(labels)|{"__UNKNOWN__"}:
            raise ValueError("Auxiliary vocabulary differs from base model")
        return model,names


def status(family, base_digest, labels):
    config = configuration(family,base_digest)
    if not config:
        return {}
    _load(config,labels)
    return {"auxiliaryCheckpoint":config["path"].name,"auxiliarySha256":config["checkpointSha256"],
            "auxiliaryFeatureVersion":config["featureVersion"],"auxiliaryWeights":config["weights"]}


def combine(base, auxiliary, base_labels, auxiliary_labels, weight):
    order = [auxiliary_labels.index(n) for n in base_labels + ["__UNKNOWN__"]]
    a = np.asarray(auxiliary)[...,order]
    p = np.asarray(base)
    zero = np.zeros((*p.shape[:-1],1),p.dtype)
    return (1-weight)*np.concatenate([p,zero],axis=-1) + weight*a


def fuse(family, base_digest, probabilities, labels, frames, vocabulary="full"):
    config = configuration(family,base_digest)
    if not config:
        return probabilities,labels,{}
    # Custom vocabulary requests use the full model's frozen fusion setting;
    # they still have their ordinary separate rejection/default policy.
    weight = config["weights"].get(vocabulary,config["weights"]["full"])
    if weight == 0:
        return probabilities,labels,{"auxiliaryWeight":0}
    model,names = _load(config,labels)
    from handshape_features import frames_to_handshape
    from handshape_model import predict
    with LOCK:
        auxiliary = predict(model,[frames_to_handshape(frames)])[0]
    p = combine(probabilities,auxiliary,labels,names,weight)
    return p,labels+["__UNKNOWN__"],{"auxiliarySha256":config["checkpointSha256"],
                                    "auxiliaryFeatureVersion":config["featureVersion"],"auxiliaryWeight":weight}
