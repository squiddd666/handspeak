"""Freeze validation selections before test audits; explicitly install later.

The prepare operation writes report artifacts only. Installation preserves v2
configuration/benchmarks and requires the frozen independent audits to exist.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, shutil
from pathlib import Path
from datetime import datetime, timezone
from asl_model_tools import REPO, digest


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8")


def prepare(root):
    output=root/"release-draft.json"
    if output.exists():
        raise FileExistsError(output)
    old=read(REPO/"models/motion-calibration.json");config=copy.deepcopy(old)
    for family,filename in (("beginner","beginner-aspect-classes.json"),("capstone","capstone-classes.json")):
        selection=read(root/f"selection-{family}.json")
        calibration=read(REPO/"reports/motion-repair-v2-20261107/calibration"/filename)
        profile=config["models"][family]
        if selection["checkpointSha256"]!=profile["checkpointSha256"] or selection["testUsedForSelection"] or selection["watchClipsUsedForSelection"]:
            raise ValueError("Invalid candidate selection provenance")
        if selection["deployable"]:
            auxiliary_path=Path(selection["auxiliaryCheckpoint"])
            if digest(auxiliary_path)!=selection["auxiliarySha256"]:
                raise ValueError("Candidate changed after selection")
            weights={mode:value["weight"] for mode,value in selection["selected"].items()}
            auxiliary={"checkpoint":f"models/{family}-handshape-v3.pt","checkpointSha256":selection["auxiliarySha256"],
                       "featureVersion":selection["auxiliaryFeatureVersion"],"weights":weights}
            profile.update(auxiliary=auxiliary,policies=selection["policies"],calibrationReport=f"{family}-handshape.json")
            calibration.update(policies=selection["policies"],auxiliarySha256=selection["auxiliarySha256"],
                               auxiliaryFeatureVersion=selection["auxiliaryFeatureVersion"],fusionWeights=weights,
                               selectionReportSha256=digest(root/f"selection-{family}.json"))
        else:
            profile["calibrationReport"]=f"{family}-handshape.json"
        write(root/"calibration"/f"{family}-handshape.json",calibration)
    config["calibrationId"]="motion-repair-v3-20261107-val-"+hashlib.sha256(json.dumps(config["models"],sort_keys=True).encode()).hexdigest()[:12]
    config["selectedAt"]=datetime.now(timezone.utc).isoformat()
    config["selectionScope"]="Train/validation-only full-handshape temporal fusion with explicit unknown examples; test and Watch never set weights or gates."
    write(output,config)
    write(root/"frozen-selection.json",{"selectedAt":config["selectedAt"],"calibrationId":config["calibrationId"],
                                       "releaseDraftSha256":digest(output),"testUsedForSelection":False,"watchClipsUsedForSelection":False,
                                       "selections":{family:digest(root/f"selection-{family}.json") for family in ("beginner","capstone")}})
    print("Prepared only:",output)


def install(root):
    config=read(root/"release-draft.json");frozen=read(root/"frozen-selection.json")
    if digest(root/"release-draft.json")!=frozen["releaseDraftSha256"]:
        raise ValueError("Release draft changed after selection")
    for family in ("beginner","capstone"):
        report=read(root/f"heldout-{family}.json");calibration=root/"calibration"/f"{family}-handshape.json"
        if report["split"]!="test" or report["testUsedForSelection"] or not report["watchClipsExcluded"] or not report["sourcesAndParticipantsDisjoint"]:
            raise ValueError("Invalid independent audit")
        if report["calibrationSha256"]!=digest(calibration):
            raise ValueError("Calibration differs from audited selection")
        profile=config["models"][family]
        if profile.get("auxiliary"):
            if report["selected"].get("auxiliarySha256")!=profile["auxiliary"]["checkpointSha256"]:
                raise ValueError("Auxiliary differs from independently audited weights")
            selection=read(root/f"selection-{family}.json")
            target=REPO/profile["auxiliary"]["checkpoint"]
            if target.exists():
                raise FileExistsError(target)
            shutil.copyfile(selection["auxiliaryCheckpoint"],target)
    backup=root/"pre-v3"
    backup.mkdir(exist_ok=True)
    for name in ("motion-calibration.json","motion-word-accuracy.json"):
        target=backup/name
        if target.exists():
            raise FileExistsError(target)
        shutil.copyfile(REPO/"models"/name,target)
    write(REPO/"models/motion-calibration.json",config)
    write(root/"installation.json",{"installedAt":datetime.now(timezone.utc).isoformat(),"calibrationId":config["calibrationId"],
                                    "configurationSha256":digest(REPO/"models/motion-calibration.json"),"v2Backups":str(backup)})
    print("Installed frozen release:",config["calibrationId"])


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir",type=Path,default=REPO/"reports/motion-repair-v3-20261107")
    parser.add_argument("--install",action="store_true")
    args=parser.parse_args()
    (install if args.install else prepare)(args.report_dir.resolve())
