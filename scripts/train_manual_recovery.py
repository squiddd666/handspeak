"""Fit missing-sign fallback using the frozen TRAIN bank and native VAL only."""
import argparse,collections,datetime,itertools,json,math,subprocess,time
from pathlib import Path
import numpy as np
from scripts.run_online_native_audit import ROOT,sha,verify
from scripts.train_manual_open_set_guard import verify_dev
from scripts.train_native_manual_v4 import dtw_many,mirrored,metrics
from scripts.audit_body_manual_v5 import BASELINE_FILES


def select_class_gate(stats,expected,signers,label,limits,ratios,votes):
    best=None
    for limit,ratio,vote in itertools.product(limits,ratios,votes):
        accepted=[i for i,s in enumerate(stats) if s and s['label']==label and s['distance']<=limit and s['ratio']>=ratio and s['votes']>=vote]
        hits=[i for i in accepted if expected[i]==label]
        # Correct support is per fallback class, never inherited from a global
        # score. Zero VAL false accepts includes other supported/unsupported words.
        if len(hits)!=len(accepted) or len(hits)<3 or len({signers[i] for i in hits})<2:continue
        key=(len(hits),-limit,ratio,vote)
        if best is None or key>best[0]:best=(key,dict(maxDistance=limit,minRatio=ratio,minVotes=vote),hits)
    return best


def main(args):
    started=time.perf_counter();base=args.guard.resolve();gp=json.loads((base/'protocol.json').read_text('utf-8'))
    verify({'frozenFilesSha256':gp['frozenInputsSha256']});dev=Path(gp['base']);dp=json.loads((dev/'protocol.json').read_text('utf-8'));verify_dev(dp)
    guard=json.loads((base/'candidate.json').read_text('utf-8'));gv=json.loads((base/'validation.json').read_text('utf-8'))
    if sha(base/'candidate.json')!=gv['modelSha256']:raise ValueError('Unfrozen guard')
    out=args.out.resolve();out.relative_to((ROOT.parent/'hs-eval').resolve());out.mkdir(exist_ok=False)
    names=['scripts/train_manual_recovery.py','training/experimental/manual_recovery_runtime.mjs','training/test_manual_recovery.py','training/test_manual_recovery.mjs']
    frozen={str(ROOT/n):sha(ROOT/n) for n in names}
    frozen.update({str(base/n):sha(base/n) for n in ('protocol.json','candidate.json','validation.json','runtime-parity.json')})
    plan=dict(frozenAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),purpose='native-train-val-recovery-development-only',
        guard=str(base),development=str(dev),frozenInputsSha256=frozen,sourceManifestSha256=sha(dev/'source-manifest.json'),
        selectionSplit='val',referenceSplit='train',trainingBankChanged=False,
        selection='Nearest overall TRAIN prototype competes with all 57 labels, not just the requested vocabulary. Per-class VAL gate; only after the frozen guard rejects.',
        limits=[.2,.3,.4,.5,.65,.8,1.,1.5,2.,3.],ratios=[1.,1.05,1.1,1.2,1.3,1.5,2.,3.],votes=[1,2,3],
        minimumCorrectRecordings=3,minimumCorrectSigners=2,
        requirements='Zero newly wrong/unsupported VAL accepts, retain every correct baseline recording, at least two recovered correct recordings per enabled mode.',
        gateTieBreak='Most correct fallback accepts, then smallest distance, highest ratio, most votes.',
        noAuditOutcomesRead=True,testRead=False,watchReadForFitting=False,deploymentAllowed=False,
        license='Local noncommercial ASL Citizen research only; no redistribution of originals or derived templates.',
        scope='Selection-set validation, not independent recognition accuracy or full-198 verification.')
    (out/'protocol.json').write_text(json.dumps(plan,indent=2)+'\n','utf-8')
    raw=[json.loads(l) for l in Path(dp['nativeArchive']).read_text('utf-8').splitlines() if l.strip()]
    if any(r['split'] not in ('train','val') for r in raw):raise ValueError('Test/audit input prohibited')
    native={r['file']:r for r in raw if r['split']=='val'}
    manifest={r['file']:r for r in json.loads((dev/'source-manifest.json').read_text('utf-8'))}
    records=gv['records'];rows=[manifest[r['file']] for r in records]
    data=dict(models={k:json.loads((ROOT/n).read_text('utf-8')) for k,n in BASELINE_FILES.items()},
        cases=[dict(rawFrames=native[r['file']]['rawFrames'],imageAspect=native[r['file']]['imageAspect']) for r in records])
    run=subprocess.run(['C:/Program Files/nodejs/node.exe',str(ROOT/'training/ux/run_manual_guard_baseline.mjs')],input=json.dumps(data),capture_output=True,text=True,check=True)
    cases=json.loads(run.stdout)
    if len(cases)!=len(records) or any(c['baseline']!=r['baseline'] for c,r in zip(cases,records)):raise ValueError('Actual baseline changed')
    refs=np.asarray([r['sequence'] for r in guard['samples']]);labels=np.asarray([r['label'] for r in guard['samples']]);statistics=[]
    for i,c in enumerate(cases):
        if c['sequence'] is None:statistics.append(None);continue
        seq=np.asarray(c['sequence']);d=np.minimum(dtw_many(seq,refs),dtw_many(mirrored(seq),refs));rank=np.argsort(d,kind='stable')
        label=str(labels[rank[0]]);same=float(d[rank[0]]);other=float(d[rank[labels[rank]!=label][0]])
        statistics.append(dict(label=label,distance=same,ratio=other/(same+1e-6),votes=int((labels[rank[:3]]==label).sum())))
    result=dict(version=1,featureVersion='manual-recovery-v1',guard=guard,modes={},purpose='local-experimental-not-deployed')
    outputs={};comparisons={};selection={}
    for mode,mode_labels in dp['manualModes'].items():
        guarded=[r['candidate'][mode] for r in records];before=[r['baseline'][mode] for r in records]
        stats=[s if old is None else None for s,old in zip(statistics,guarded)]
        expected=[r['label'] for r in rows];signers=[r['participant'] for r in rows];policies={};current=list(guarded);selection[mode]={}
        for label in mode_labels:
            selected=select_class_gate(stats,expected,signers,label,plan['limits'],plan['ratios'],plan['votes'])
            if selected:
                _,gate,hits=selected;policies[label]=gate
                for i in hits:current[i]=label
                selection[mode][label]=dict(correctSources=[rows[i]['file'] for i in hits],correctSigners=sorted({signers[i] for i in hits}),gate=gate)
        b=metrics(rows,before,mode_labels);g=metrics(rows,guarded,mode_labels);a=metrics(rows,current,mode_labels)
        eligible=a['correct']>=g['correct']+2 and a['wrong']<=g['wrong'] and a['negativeFalse']<=g['negativeFalse']
        if not eligible:current=guarded;policies={};a=g
        if any(r['label']==old and old is not None and new!=old for r,old,new in zip(rows,before,current)):raise ValueError('Correct baseline source lost')
        result['modes'][mode]=dict(enabled=eligible,classPolicies=policies);outputs[mode]=current
        comparisons[mode]=dict(baseline=b,guard=g,recovery=a,eligible=eligible,classes=len(policies),
            recoveredNoMatches=sum(old is None and new==r['label'] for r,old,new in zip(rows,before,current)),
            correctedVetoedWords=sum(old is not None and old!=r['label'] and new==r['label'] for r,old,new in zip(rows,before,current)))
        print(mode,json.dumps(comparisons[mode]),flush=True)
    (out/'candidate.json').write_text(json.dumps(result,separators=(',',':')),'utf-8')
    report=dict(modelSha256=sha(out/'candidate.json'),protocolSha256=sha(out/'protocol.json'),comparison=comparisons,classSelection=selection,
        records=[dict(file=r['file'],label=r['label'],baseline=r['baseline'],guard=r['candidate'],candidate={m:outputs[m][i] for m in outputs}) for i,r in enumerate(records)],
        testUsedForSelection=False,auditOutcomesRead=False,productionFilesUnchanged=True,deployed=False,seconds=round(time.perf_counter()-started,3))
    (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    module=(ROOT/'training/experimental/manual_recovery_runtime.mjs').as_uri()
    code='import {predictManualRecovery} from '+json.dumps(module)+";let t='';for await(const c of process.stdin)t+=c;const i=JSON.parse(t);process.stdout.write(JSON.stringify(i.cases.map(c=>predictManualRecovery(i.model,c.sequence,c.baseline))));"
    run=subprocess.run(['C:/Program Files/nodejs/node.exe','--input-type=module','-e',code],input=json.dumps(dict(model=result,cases=cases)),capture_output=True,text=True,check=True)
    actual=json.loads(run.stdout);max_error=0.
    for i,(r,a,s) in enumerate(zip(report['records'],actual,statistics)):
        if a['guarded']!=r['guard'] or a['predictions']!=r['candidate']:raise ValueError('Python/JS guard or fallback parity mismatch')
        if s:
            js=a['statistics']
            if js['label']!=s['label'] or js['votes']!=s['votes']:raise ValueError('Rank parity mismatch')
            max_error=max(max_error,abs(js['distance']-s['distance']),abs(js['ratio']-s['ratio']))
    verify_dev(dp);verify({'frozenFilesSha256':frozen})
    parity=dict(cases=len(cases),modeOutcomes=len(cases)*4,baselineIdentical=True,guardIdentical=True,recoveryIdentical=True,
        maxDistanceOrRatioError=max_error,modelSha256=sha(out/'candidate.json'),productionFilesUnchanged=True,testRead=False,auditOutcomesRead=False,gateChanges=False)
    (out/'runtime-parity.json').write_text(json.dumps(parity,indent=2)+'\n','utf-8');print(json.dumps(parity),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--guard',type=Path,required=True);p.add_argument('--out',type=Path,required=True);main(p.parse_args())
