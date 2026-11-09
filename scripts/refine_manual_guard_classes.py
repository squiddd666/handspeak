"""Tighten supported predicted-class gates on the same development VAL only."""
import argparse,copy,json,math
from pathlib import Path
from scripts.run_online_native_audit import ROOT,sha
from scripts.train_manual_open_set_guard import verify_dev,apply_gate
from scripts.train_native_manual_v4 import metrics


def main(args):
    base=args.base.resolve();p=json.loads((base/'protocol.json').read_text('utf-8'));verify_dev(p)
    v=json.loads((base/'validation.json').read_text('utf-8'));model=json.loads((base/'candidate.json').read_text('utf-8'))
    if sha(base/'candidate.json')!=v['modelSha256']:raise ValueError('Base candidate changed')
    parity=json.loads((base/'runtime-parity.json').read_text('utf-8'))
    if not parity['predictionsIdentical'] or not parity['baselineMatchesActualCurrentJavaScript']:raise ValueError('Actual baseline parity required')
    out=args.out.resolve();out.relative_to((ROOT.parent/'hs-eval').resolve());out.mkdir(exist_ok=False)
    archive=[json.loads(l) for l in (base/'validation-baseline.jsonl').read_text('utf-8').splitlines() if l.strip()]
    members={r['file']:r for r in json.loads((base/'source-manifest.json').read_text('utf-8'))}
    frozen={str(base/n):sha(base/n) for n in ('protocol.json','candidate.json','validation.json','validation-baseline.jsonl','runtime-parity.json','source-manifest.json')}
    files=['scripts/refine_manual_guard_classes.py','scripts/verify_refined_guard.py','training/experimental/manual_open_set_guard_v2.mjs','training/test_refined_manual_guard.mjs']
    frozen.update({str(ROOT/n):sha(ROOT/n) for n in files})
    plan=dict(purpose='native-validation-development-only',base=str(base),baseProtocolSha256=sha(base/'protocol.json'),frozenInputsSha256=frozen,
        minimumCorrectRecordingSupport=3,minimumCorrectSignerSupport=2,selectionSplit='val',trainingReferencesChanged=False,
        classPolicy='Only stricter gates than the global fallback; supported predicted classes only, sparse classes unchanged.',
        requirements='Retain every correctly accepted VAL recording and do not increase wrong/negative accepts; at least 25% fewer unsupported accepts to enable a mode.',
        testUsed=False,auditOutcomesRead=False,deploymentAllowed=False)
    with (out/'protocol.json').open('x',encoding='utf-8') as f:json.dump(plan,f,indent=2)
    expected=[dict(label=r['label']) for r in archive];result=copy.deepcopy(model);result['featureVersion']='manual-open-set-competition-v2'
    comparisons={};records=[];outputs={};class_audit={}
    for mode,labels in p['manualModes'].items():
        old=[r['baseline'][mode] for r in archive];current=[r['candidate'][mode] for r in v['records']]
        global_policy=result['modes'][mode];global_policy['classPolicies']={}
        # A previously disabled mode's unrestrictive fallback is examined on
        # validation, then enabled only if the complete mode clears the bar.
        global_policy['enabled']=True
        class_audit[mode]={}
        for label in labels:
            ids=[i for i,x in enumerate(current) if x==label];hits=[i for i in ids if archive[i]['label']==label]
            signers={members[archive[i]['file']]['participant'] for i in hits}
            if len(hits)<3 or len(signers)<2:
                class_audit[mode][label]=dict(adjusted=False,reason='sparse-correct-support',correct=len(hits),signers=len(signers));continue
            rows=[expected[i] for i in ids];before=[current[i] for i in ids]
            stats=[tuple(math.inf if x is None else x for x in archive[i]['guardStats'][mode]) for i in ids]
            original=metrics(rows,before,labels);best=None
            for distance in p['limits']:
                if distance>global_policy['maxDistance']:continue
                for ratio in p['ratios']:
                    if ratio<global_policy['minRatio']:continue
                    predicted=apply_gate(before,stats,distance,ratio);m=metrics(rows,predicted,labels)
                    if m['correct']!=original['correct'] or m['wrong']>original['wrong'] or m['negativeFalse']>original['negativeFalse']:continue
                    key=(-m['negativeFalse'],-m['wrong'],-ratio,distance)
                    if best is None or key>best[0]:best=(key,distance,ratio,m,predicted)
            if best:
                _,distance,ratio,m,predicted=best
                if m['negativeFalse']<original['negativeFalse'] or m['wrong']<original['wrong']:
                    global_policy['classPolicies'][label]=dict(maxDistance=distance,minRatio=ratio)
                    for i,new in zip(ids,predicted):current[i]=new
                    class_audit[mode][label]=dict(adjusted=True,before=original,after=m,correctSigners=len(signers))
                else:class_audit[mode][label]=dict(adjusted=False,reason='no-supported-improvement')
        before=metrics(expected,old,labels);after=metrics(expected,current,labels)
        if any(r['label']==b and b is not None and a!=b for r,b,a in zip(expected,old,current)):raise ValueError('Correct recording lost')
        eligible=before['negativeFalse']>0 and after['negativeFalse']<=math.floor(before['negativeFalse']*.75)
        if not eligible:
            result['modes'][mode]=copy.deepcopy(model['modes'][mode]);current=old;after=before
        outputs[mode]=current;comparisons[mode]=dict(before=before,after=after,eligible=eligible,classPolicyCount=len(result['modes'][mode].get('classPolicies',{})))
        print(mode,json.dumps(comparisons[mode]),flush=True)
    for i,r in enumerate(archive):records.append(dict(file=r['file'],label=r['label'],baseline=r['baseline'],candidate={m:outputs[m][i] for m in outputs}))
    result['purpose']='offline-class-supported-rejection-only-candidate-not-deployed'
    with (out/'candidate.json').open('x',encoding='utf-8') as f:json.dump(result,f,separators=(',',':'))
    report=dict(modelSha256=sha(out/'candidate.json'),protocolSha256=sha(out/'protocol.json'),comparison=comparisons,classSelectionAudit=class_audit,
        records=records,sourceManifestSha256=v['sourceManifestSha256'],selectionSplit='val',trainingSplit='train',testUsedForSelection=False,
        auditOutcomesReadForSelection=False,correctRecordingRetention=True,deployed=False,productionFilesUnchanged=True,
        scope='Native development validation only; not independent audit or production browser accuracy.')
    with (out/'validation.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    verify_dev(p)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--base',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);main(parser.parse_args())
