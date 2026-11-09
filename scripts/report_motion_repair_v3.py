"""Full frozen-release regression accounting, including all remaining failures."""
from __future__ import annotations
import csv,json,hashlib
from pathlib import Path
from report_motion_repair import baseline_attempts,counts
from summarize_motion_virtual_camera import summarize

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/"reports/motion-repair-v3-20261107"


def read(path):return json.loads(path.read_text(encoding="utf-8"))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8")


def report():
    raw=REPORT/"virtual-final/final-all-198.json"
    summarize(raw)
    current=read(raw);summary=read(raw.parent/"summary.json")
    previous=read(ROOT/"reports/motion-repair-v2-20261107/virtual-final/final-all-198.json")
    old,new=baseline_attempts(previous),baseline_attempts(current)
    before,after=counts(old),counts(new)
    config=read(ROOT/"models/motion-calibration.json")
    if current["calibrationSha256"]!=sha(ROOT/"models/motion-calibration.json"):
        raise ValueError("Calibration changed during verification")
    for name,identity in current["runtimeSha256"].items():
        if sha(ROOT/name)!=identity:raise ValueError(f"Runtime changed during verification: {name}")
    for t in new.values():
        response=t.get("response") or {}
        if response.get("checkpointSha256"):
            profile=config["models"][t["family"]]
            if response["checkpointSha256"]!=profile["checkpointSha256"] or response.get("calibrationId")!=config["calibrationId"]:
                raise ValueError("Stale base model/calibration was tested")
            auxiliary=profile.get("auxiliary")
            mode=t.get("vocabulary") or "full"
            if auxiliary and auxiliary["weights"].get(mode,0):
                if response.get("auxiliarySha256")!=auxiliary["checkpointSha256"] or response.get("auxiliaryWeight")!=auxiliary["weights"][mode]:
                    raise ValueError("Stale auxiliary model was tested")
    transitions=[]
    def outcome(t):return "matched" if t["correct"] else "wrong" if t.get("predicted") else "no match"
    for key,t in new.items():
        transitions.append({"label":t["label"],"before":outcome(old[key]),"after":outcome(t),"prediction":t.get("predicted")})
    remaining=[w for w in summary["words"] if w["outcome"]!="matched"]
    independent=[]
    for family in ("beginner","capstone"):
        prior=read(ROOT/f"reports/motion-repair-v2-20261107/heldout-{family}.json")
        selected=read(REPORT/f"heldout-{family}.json")
        for mode,result in selected["selected"]["modes"].items():
            b=prior["selected"]["modes"][mode]["accepted"];a=result["accepted"]
            if a["attempts"]!=b["attempts"] or a["negativeAttempts"]!=b["negativeAttempts"]:
                raise ValueError("Independent audit denominators changed")
            keys=("attempts","correct","wrong","noMatch","negativeAttempts","negativeFalse")
            independent.append({"family":family,"mode":mode,"before":{k:b[k] for k in keys},"after":{k:a[k] for k in keys}})
    result={"before":before,"after":after,"calibrationId":config["calibrationId"],"scope":summary["scope"],
            "independentAudits":independent,"transitions":transitions,"remainingFailures":remaining,
            "allWordsReliablyFixed":False,"appUrl":"http://127.0.0.1:8003/#learn"}
    write(REPORT/"repair-summary.json",result);write(REPORT/"remaining-reference-failures.json",remaining)
    with (REPORT/"remaining-reference-failures.csv").open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=["label","modelRoute","prediction","outcome","rejectionReason","trackedFrames","status"],extrasaction="ignore")
        writer.writeheader();writer.writerows(remaining)
    lines=["# Full-handshape retraining and third frozen recognition release","","## Implemented","",
           "* Trained separate lightweight temporal auxiliary classifiers for Beginner-79 and full-100, each for 55 epochs. Saved the best train/validation-only objective checkpoint.",
           "* Preserved the existing ST-GCN checkpoints and added 21-point wrist-relative XYZ handshape, body-relative wrists, seven body landmarks, and explicit missing-hand masks. Pose depth is never mixed with hand depth.",
           "* Included training-only aspect/crop/sparse-sampling/noise/hand-loss augmentation, anatomical mirror averaging, and an explicit unsupported-sign class. Unknown probability mass is retained for rejection and never emitted as a word.",
           "* Selected fusion weights and gates only on validation. Both known-word errors and unsupported accepts must stay within v2 validation budgets; class relaxations require at least three correct validation examples.",
           "* Source/signers are disjoint across train/validation/test. Primary Watch videos are excluded from fitting and independent audits. Synthetic joined GOOD greetings remain explicitly synthetic.",
           "* Auxiliary digests, label maps, preprocessing, and gates are tied together; mismatches fail closed. Preserved v2 weights/configuration/benchmarks. Published honest current recorded counts.",
           "* Small default/pack/daily template recognizers were not retrained: their available data are separate and insufficient to validate a common body-handshape model. Their failures remain visible.","","## All 198 reference regressions","",
           f"* v2: **{before['matched']} matched / {before['wrong']} wrong / {before['noMatch']} no match**.",
           f"* v3: **{after['matched']} matched / {after['wrong']} wrong / {after['noMatch']} no match**.",
           f"* Completed reference playback: {summary['completeClipPlayback']}/198; insufficient tracking: {summary['insufficientTrackingMisses']}.",
           "* Exactly one normal-speed primary-reference attempt per word, using visible Watch → Practice → Record controls in the isolated in-page virtual camera. No practice-label override, user-history writes, or physical camera/microphone calls.",
           "* These are reference regressions, not independent live-camera accuracy. All remaining failures and regressions are retained below.","","## Frozen independent recording audit","",
           "| Route | Attempts | v2 correct / wrong / no match | v3 correct / wrong / no match | Unsupported accepts: v2 → v3 |","|---|---:|---|---|---|"]
    for r in independent:
        b,a=r["before"],r["after"]
        lines.append(f"| {r['family']} / {r['mode']} | {a['attempts']} | {b['correct']} / {b['wrong']} / {b['noMatch']} | {a['correct']} / {a['wrong']} / {a['noMatch']} | {b['negativeFalse']} → {a['negativeFalse']} / {a['negativeAttempts']} |")
    lines += ["","**Not every metric improves:** Beginner independent coverage improves substantially, but accepted wrong named signs increase from 23 to 28. Full-100 wrong signs decrease from 30 to 29. Unsupported accepts decrease in both. Settings were not retuned on these test results.","","## Remaining reference failures","","| Word | Route | Actual output | Outcome | Reason |","|---|---|---|---|---|"]
    for w in remaining:lines.append(f"| {w['label']} | {w['modelRoute']} | {w['prediction'] or '—'} | {w['outcome']} | {w['rejectionReason'] or w['status']} |")
    lines += ["","## Evidence and next requirements","",
              "* `candidates/*.history.json`, `selection-*.json`, `frozen-selection.json`, and `calibration/` document fitting and selection before independent audits.",
              "* `heldout-*.json` contains every independent attempted recording, including insufficient-tracking misses and unsupported signs.",
              "* `virtual-final/final-all-198.json`, `virtual-final/summary.json`, and `repair-summary.json` retain all reference outcomes and before/after transitions.",
              "* `pre-v3/` preserves configuration and published benchmarks for rollback; old weights remain unchanged.",
              "* Test runs and scope are in `test-scope.json`. Broader legacy Python failures documented in v2 were not silently claimed fixed.",
              "* Remaining manual-model confusions need new independent signer recordings and validation negatives. Body-model failures still need more variants/tracking robustness. Lowering a threshold or returning the selected practice word is not a fix.",
              "* Updated runtime: http://127.0.0.1:8003/#learn. Earlier servers retain older in-memory models; use the new port for this release.",
              "* Local research use only; no public deployment, dataset redistribution, external biometric upload, or user-message modification."]
    (REPORT/"README.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return {"before":before,"after":after,"remaining":len(remaining)}


if __name__=="__main__":print(json.dumps(report(),indent=2))
