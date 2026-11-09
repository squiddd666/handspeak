"""Select auxiliary fusion on validation, within the active error budgets.

This never deploys a candidate. It refuses source/weight mismatches and needs
more correct named validation accepts without more wrong/unsupported accepts.
"""
from __future__ import annotations
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from asl_model_tools import REPO, digest
from calibrate_motion_models import CORE, EXTRA, summarize
from calibrate_motion_classes import fit_classes
sys.path.insert(0,str(REPO))
from motion_calibration import decide


def metrics(p, expected, labels, names, policy):
    allowed = [labels.index(n) for n in names]
    predicted = np.full(len(p), "", dtype=object)
    for i, row in enumerate(p):
        if np.isfinite(row).all():
            d = decide(row, labels, allowed=allowed, policy=policy)
            if d["predictions"]:
                predicted[i] = d["predictions"][0]["label"]
    return summarize(predicted == expected, predicted != "", np.isin(expected,names))


def fit_budget(p, expected, labels, names, budgets):
    allowed = [labels.index(n) for n in names]
    valid = np.isfinite(p).all(1)
    q = np.nan_to_num(p, nan=0)[:,allowed]
    mass = q.sum(1); q /= np.maximum(mass[:,None],1e-15)
    ranking = np.argsort(q,1)[:,::-1]
    score = q[np.arange(len(q)),ranking[:,0]]
    gap = score - q[np.arange(len(q)),ranking[:,1]]
    correct = np.asarray(names)[ranking[:,0]] == expected
    known = np.isin(expected,names)
    best = None
    for gate in (0,.15,.25,.35,.45,.5,.55,.6,.65,.7,.75,.8,.85,.9,.95,.99):
        for margin in (0,.02,.05,.1,.15,.2,.3,.4):
            for minimum_mass in (0,.2,.4,.6,.8,.9,.95):
                accepted = valid & (score >= gate) & (gap >= margin) & (mass >= minimum_mass)
                m = summarize(correct, accepted, known)
                if m["wrong"] > budgets["wrong"] or m["negativeFalse"] > budgets["negativeFalse"]:
                    continue
                key = (m["correct"],-m["wrong"],-m["negativeFalse"],-margin,-minimum_mass,-gate)
                if best is None or key > best[0]:
                    best = (key,{"minScore":gate,"minMargin":margin,"minVocabularyMass":minimum_mass,
                                 "selectionSplit":"val","validation":m,"validationErrorBudgets":budgets})
    if best is None:
        return None
    policy, _ = fit_classes(p,expected,labels,names,best[1])
    return policy


def select(args):
    auxiliary = np.load(args.auxiliary.with_suffix(".val.npz"), allow_pickle=False)
    from handshape_model import load
    _, labels, blob = load(args.auxiliary)
    if list(auxiliary["labels"]) != labels or blob["trainingAudit"]["selectionSplit"] != "val" or blob["trainingAudit"]["testUsedForSelection"]:
        raise ValueError("Invalid auxiliary validation provenance")
    known = np.load(args.known, allow_pickle=False); negative = np.load(args.negatives, allow_pickle=False)
    calibration = json.loads(args.baseline.read_text(encoding="utf-8"))
    evidence = json.loads(args.known.with_suffix(".json").read_text(encoding="utf-8"))
    if evidence["split"] != "val" or evidence["checkpointSha256"] != calibration["checkpointSha256"] or evidence["probabilitiesSha256"] != digest(args.known):
        raise ValueError("Invalid baseline validation identity")
    if calibration["checkpointSha256"] != blob["trainingAudit"]["baseCheckpointSha256"]:
        raise ValueError("Auxiliary used a different baseline")
    if calibration["testUsedForCalibration"] or calibration["watchClipsUsedForCalibration"]:
        raise ValueError("Contaminated calibration")
    base_labels = list(known["labels"])
    if base_labels != labels[:-1] or list(negative["labels"]) != base_labels:
        raise ValueError("Label order mismatch")
    base = {}; expected_base = {}
    for archive in (known,negative):
        for f,p,y in zip(archive["files"],archive["probabilities"],archive["expected"]):
            if str(f) in base:
                raise ValueError("Duplicate validation source")
            base[str(f)] = np.append(p,0).astype(np.float32)
            expected_base[str(f)] = str(y)
    files = list(map(str,auxiliary["files"]))
    if set(files) != set(base):
        raise ValueError("Validation denominators differ")
    expected = np.asarray([expected_base[f] if expected_base[f] in base_labels else "__UNKNOWN__" for f in files])
    if not np.array_equal(expected,auxiliary["expected"]):
        raise ValueError("Validation expected labels differ")
    baseline_p = np.stack([base[f] for f in files])
    aux_p = auxiliary["probabilities"]
    watch = {s["originalFile"] for item in json.loads((REPO/"models/recognition-videos.json").read_text(encoding="utf-8"))["items"] for s in item.get("sources",[])}
    if any(Path(f).name in watch for f in files):
        raise ValueError("Watch source in validation")
    modes = {"full":base_labels} if args.family == "beginner" else {"full":base_labels,"core":CORE,"extended":CORE+EXTRA}
    policies, candidates, selected = {}, {}, {}
    for mode,names in modes.items():
        old = calibration["policies"][mode]
        before = metrics(baseline_p,expected,labels,names,old)
        winner = (before["correct"],-before["wrong"],-before["negativeFalse"])
        selected[mode] = {"weight":0,"before":before,"after":before,"improved":False}
        policies[mode] = old; candidates[mode] = []
        for weight in (.25,.5,.75,1):
            p = (1-weight)*baseline_p + weight*aux_p
            policy = fit_budget(p,expected,labels,names,before)
            if not policy:
                continue
            after = metrics(p,expected,labels,names,policy)
            row = {"weight":weight,"metrics":after,"policy":policy}
            candidates[mode].append(row)
            key = (after["correct"],-after["wrong"],-after["negativeFalse"])
            if after["correct"] > before["correct"] and key > winner:
                winner = key
                selected[mode] = {"weight":weight,"before":before,"after":after,"improved":True}
                policies[mode] = policy
        print(mode,json.dumps(selected[mode]),flush=True)
    result = {"family":args.family,"checkpoint":calibration["checkpoint"],"checkpointSha256":calibration["checkpointSha256"],
              "auxiliaryCheckpoint":str(args.auxiliary.resolve()),"auxiliarySha256":digest(args.auxiliary),
              "auxiliaryFeatureVersion":blob["featureVersion"],"auxiliaryValidationSha256":digest(args.auxiliary.with_suffix(".val.npz")),
              "selectedAt":datetime.now(timezone.utc).isoformat(),"selectionSplit":"val","testUsedForSelection":False,
              "watchClipsUsedForSelection":False,"baselineCalibrationSha256":digest(args.baseline),
              "sourceValidationSha256":digest(args.known),"negativeValidationSha256":digest(args.negatives),
              "selected":selected,"policies":policies,"candidates":candidates,
              "deployable":selected["full"]["improved"],"scope":"Validation-only auxiliary exploration, not deployed or independently verified."}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    return result


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family",choices=["beginner","capstone"],required=True)
    for field in ("auxiliary","known","negatives","baseline","out"):
        parser.add_argument("--"+field,type=Path,required=True)
    select(parser.parse_args())
