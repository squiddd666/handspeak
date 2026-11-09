"""Compare active localhost inference with frozen validation probability math.

Uses cached validation landmarks, not cameras. Exports only scalar results;
never writes coordinates, user messages, or a selected expected-label override.
"""
from __future__ import annotations
import json,sys,urllib.request,urllib.error
from pathlib import Path
import numpy as np
from asl_model_tools import REPO,load_rows,digest
sys.path.insert(0,str(REPO))
from handshape_inference import combine
from motion_calibration import decide

REPORT=REPO/"reports/motion-repair-v3-20261107"
BASE="http://127.0.0.1:8003"


def request(family,payload=None):
    url=BASE+f"/api/{family}-asl"+("/status" if payload is None else "")
    req=urllib.request.Request(url,data=json.dumps(payload).encode() if payload is not None else None,
                               headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=60) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:return error.code,json.load(error)


def main():
    config=json.loads((REPO/"models/motion-calibration.json").read_text(encoding="utf-8"))
    tests=[]
    for family,archive,features in (
        ("beginner",REPO/"reports/motion-repair-v2-20261107/validation/beginner-aspect-v2-tta.npz",REPO.parent/"hs-eval/motion-repair-20261107/features-beginner-repaired.jsonl"),
        ("capstone",REPO/"reports/motion-repair-20261107/validation-full/full-deployed.npz",REPO.parent/"hs-eval/features-train-merged.jsonl")):
        profile=config["models"][family];status,data=request(family)
        assert status==200 and data["runtimeReady"] and data["calibrationId"]==config["calibrationId"]
        assert data["auxiliarySha256"]==profile["auxiliary"]["checkpointSha256"]
        tests.append({"family":family,"test":"loaded-identities","passed":True})
        base=np.load(archive,allow_pickle=False)
        auxiliary=np.load(REPORT/f"candidates/{family}-handshape.val.npz",allow_pickle=False)
        indices={str(f):i for i,f in enumerate(auxiliary["files"])}
        rows={r["file"]:r for r in load_rows(features,"val")}
        labels=list(base["labels"]);auxiliary_labels=list(auxiliary["labels"])
        usable=[i for i,p in enumerate(base["probabilities"]) if np.isfinite(p).all() and len(rows[str(base["files"][i])]["frames"])<=90][:2]
        for i in usable:
            file=str(base["files"][i]);frames=rows[file]["frames"]
            for mode in (["full"] if family=="beginner" else ["full","core","extended"]):
                weight=profile["auxiliary"]["weights"][mode]
                p=base["probabilities"][i];names=labels
                if weight:
                    p=combine(p,auxiliary["probabilities"][indices[file]],labels,auxiliary_labels,weight)
                    names=labels+["__UNKNOWN__"]
                if family=="capstone" and mode!="full":
                    from calibrate_motion_models import CORE,EXTRA
                    allowed=[labels.index(n) for n in (CORE if mode=="core" else CORE+EXTRA)]
                else:allowed=list(range(len(labels)))
                expected=decide(p,names,allowed=allowed,policy=profile["policies"][mode])
                code,actual=request(family,{"consent":True,"frames":frames,"vocabulary":mode})
                assert code==200,actual
                assert actual["rejectionReason"]==expected["rejectionReason"]
                assert [r["label"] for r in actual["suggestions"]]==[r["label"] for r in expected["suggestions"]]
                np.testing.assert_allclose([r["score"] for r in actual["suggestions"]],[r["score"] for r in expected["suggestions"]],atol=5e-6)
                code,attempt=request(family,{"consent":True,"frames":frames,"vocabulary":mode,"practiceLabel":"FORCED_TEST_WORD"})
                assert code==200 and attempt["predictions"]==actual["predictions"] and attempt["suggestions"]==actual["suggestions"]
                tests.append({"family":family,"vocabulary":mode,"file":file,"test":"offline-equality-and-no-practice-override","passed":True})
        blank=[{"pose":[[.5,.5,0]]*7,"left":None,"right":None}]*5
        code,error=request(family,{"consent":True,"frames":blank})
        assert code==422 and "hand-tracked" in error["error"]
        tests.append({"family":family,"test":"blank-hands-rejected","passed":True})
    result={"runtimeUrl":BASE,"configurationSha256":digest(REPO/"models/motion-calibration.json"),
            "tests":tests,"passed":len(tests),"failed":0,"rawLandmarksExported":False,"physicalCameraCalls":0}
    (REPORT/"runtime-contract-tests.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"passed":len(tests),"failed":0,"runtimeUrl":BASE}))


if __name__=="__main__":main()
