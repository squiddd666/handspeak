"""Predeclare then fit only measured separate browser TRAIN/VAL features."""
import argparse,collections,datetime,itertools,json,math,subprocess,time
from pathlib import Path
import numpy as np
from scripts.run_online_native_audit import ROOT,sha,verify
from scripts.train_native_manual_v4 import dtw_many,mirrored,metrics
from scripts.audit_body_manual_v5 import BASELINE_FILES,RUNTIME_FILES

def prepare(capture,out):
    p=json.loads((capture/'protocol.json').read_text('utf-8'));verify(p)
    if p['purpose']!='browser-detector-domain-train-val-feature-capture':raise ValueError('Wrong separate development intake')
    out.relative_to((ROOT.parent/'hs-eval').resolve());out.mkdir(exist_ok=False)
    names=['scripts/train_browser_domain_recovery.py','training/experimental/browser_domain_recovery.mjs',
        'training/test_browser_domain_recovery.mjs','training/test_browser_domain_recovery.py',
        'training/experimental/online_manual_runtime.mjs','training/ux/run_manual_guard_baseline.mjs',
        'scripts/train_native_manual_v4.py','scripts/audit_body_manual_v5.py','scripts/run_online_native_audit.py',
        'scripts/prepare_native_repair_v4.py','scripts/train_body_manual_v5.py','scripts/prepare_targeted_data_v4.py']+list(BASELINE_FILES.values())+RUNTIME_FILES
    frozen=dict(p['frozenFilesSha256']);frozen.update({str(ROOT/n):sha(ROOT/n) for n in names});frozen[str(capture/'protocol.json')]=sha(capture/'protocol.json')
    plan=dict(purpose='measured-browser-train-val-recovery-development-only',frozenAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        capture=str(capture),frozenFilesSha256=frozen,manualModes=p['manualModes'],
        prototypeSelection='All up to four measured usable TRAIN samples per label, rounded to six decimals; sparse classes remain in competition.',
        distanceLimits=[.2,.3,.4,.5,.65,.8,1.,1.5,2.,3.,5.,10.],ratios=[0.,.5,.75,1.,1.05,1.1,1.2,1.3,1.5,2.,3.,5.],votes=[1,2,3],
        guardSelection='Per predicted label only. At least three retained correct VAL recordings and two VAL signers; retain EVERY correct baseline source. No sparse-class global fallback; require at least one fewer wrong/unsupported accept.',
        recoverySelection='Only after baseline/guard rejection. Nearest overall TRAIN label competes with all 57 labels. At least three correct VAL recoveries / two signers and zero new wrong/unsupported VAL accepts per enabled class.',
        tieBreak='Most recovered correct or fewest false accepts, then smallest distance, greatest ratio and greatest votes.',
        requirements='Entire mode must retain every baseline correct recording and never increase wrong/unsupported accepts; otherwise fail training, do not install.',
        failedCapturePolicy='Failed captures are retained as no-match outcomes but never references or gate support; no imputed landmarks.',
        sourceLicense='ASL Citizen local noncommercial research; measured templates remain outside served repo.',
        trainSplit='train',selectionSplit='val',testRead=False,auditOutcomesRead=False,watchReadForFitting=False,
        independentAccuracy=False,productionDeploymentAllowed=False)
    (out/'protocol.json').write_text(json.dumps(plan,indent=2)+'\n','utf-8');print('Frozen detector-domain training protocol before feature outcomes were read.',flush=True)

def select_guard(rows,before,statistics,label,limits,ratios):
    hits=[i for i,(r,b) in enumerate(zip(rows,before)) if b==label and r['label']==label]
    if len(hits)<3 or len({rows[i]['participant'] for i in hits})<2:return None
    ids=[i for i,b in enumerate(before) if b==label];false=[i for i in ids if rows[i]['label']!=label];best=None
    for limit,ratio in itertools.product(limits,ratios):
        accepted=[i for i in ids if statistics[i] and label in statistics[i]['byLabel']
            and statistics[i]['byLabel'][label]<=limit
            and min(d for l,d in statistics[i]['byLabel'].items() if l!=label)/(statistics[i]['byLabel'][label]+1e-6)>=ratio]
        if not set(hits)<=set(accepted):continue
        errors=sum(i in false for i in accepted)
        if errors>=len(false):continue
        key=(-errors,-limit,ratio)
        if best is None or key>best[0]:best=(key,dict(maxDistance=limit,minRatio=ratio),accepted)
    return best

def select_recovery(rows,guarded,statistics,label,limits,ratios,votes):
    best=None
    for limit,ratio,vote in itertools.product(limits,[x for x in ratios if x>=1],votes):
        ids=[i for i,s in enumerate(statistics) if guarded[i] is None and s and s['label']==label and s['distance']<=limit and s['ratio']>=ratio and s['votes']>=vote]
        if len(ids)<3 or any(rows[i]['label']!=label for i in ids) or len({rows[i]['participant'] for i in ids})<2:continue
        key=(len(ids),-limit,ratio,vote)
        if best is None or key>best[0]:best=(key,dict(maxDistance=limit,minRatio=ratio,minVotes=vote),ids)
    return best

def fit(folder):
    p=json.loads((folder/'protocol.json').read_text('utf-8'));verify(p);capture=Path(p['capture'])
    if (folder/'training-started.json').exists():raise FileExistsError('Training already started; no outcome-driven reruns')
    if not (capture/'capture-summary.json').exists():raise ValueError('All frozen source outcomes must finish first')
    integrity=json.loads((capture/'post-run-integrity.json').read_text('utf-8'))
    if not integrity['allFrozenFilesUnchanged'] or not integrity['allFeaturesUnchanged']:raise ValueError('Capture integrity failed')
    ledger=json.loads((capture/'features/checkpoint.json').read_text('utf-8'));cp=json.loads((capture/'protocol.json').read_text('utf-8'))
    expected=json.loads(Path(cp['sourceManifest']).read_text('utf-8'))
    if len(ledger)!=len(expected) or [r['id'] for r in ledger]!=cp['order']:raise ValueError('Incomplete capture ledger')
    started=time.perf_counter();(folder/'training-started.json').write_text(json.dumps(dict(protocolSha256=sha(folder/'protocol.json'),featureLedgerSha256=sha(capture/'features/checkpoint.json')))+'\n','utf-8')
    records=[];features={}
    for row,source in zip(ledger,expected):
        path=Path(row['path'])
        if sha(path)!=row['sha256']:raise ValueError('Feature changed')
        feature=json.loads(path.read_text('utf-8'));features[str(path)]=row['sha256']
        if feature['source']!=source or source['split'] not in ('train','val'):raise ValueError('Feature source mismatch or prohibited split')
        c=feature['capture'];records.append(dict(source,contractPassed=c['contractPassed'],
            rawFrames=[s['manual'] for s in c['samples']] if c['contractPassed'] else [],imageAspect=.75))
    originals={r['file']:r for r in json.loads(Path(cp.get('originalSourceManifest',cp['sourceManifest'])).read_text('utf-8'))}
    for row in cp.get('inheritedFeatures',[]):
        path=Path(row['path'])
        if sha(path)!=row['sha256']:raise ValueError('Inherited measured feature changed')
        feature=json.loads(path.read_text('utf-8'));source=feature['source'];c=feature['capture']
        if source!=originals[source['file']]:raise ValueError('Inherited source mapping changed')
        features[str(path)]=row['sha256'];records.append(dict(source,contractPassed=c['contractPassed'],
            rawFrames=[s['manual'] for s in c['samples']] if c['contractPassed'] else [],imageAspect=.75))
    for missing in cp.get('inheritedFailedSources',[]):
        source=missing['source']
        if source!=originals[source['file']]:raise ValueError('Missing-source disposition changed')
        records.append(dict(source,contractPassed=False,rawFrames=[],imageAspect=.75,missingFeatureReason=missing['reason']))
    if len({r['file'] for r in records})!=len(records) or len(records)!=len(originals):raise ValueError('Cross-run source duplication or hidden outcome')
    data=dict(models={k:json.loads((ROOT/n).read_text('utf-8')) for k,n in BASELINE_FILES.items()},
        cases=[dict(rawFrames=r['rawFrames'],imageAspect=r['imageAspect']) for r in records])
    run=subprocess.run(['C:/Program Files/nodejs/node.exe',str(ROOT/'training/ux/run_manual_guard_baseline.mjs')],input=json.dumps(data),capture_output=True,text=True,check=True)
    cases=json.loads(run.stdout)
    if len(cases)!=len(records):raise ValueError('Actual baseline case count changed')
    for r,c in zip(records,cases):r['sequence']=c['sequence'];r['baseline']=c['baseline']
    train=[r for r in records if r['split']=='train' and r['sequence'] is not None and r['contractPassed']];val=[r for r in records if r['split']=='val']
    if {r['participant'] for r in train}&{r['participant'] for r in val}:raise ValueError('Signer leakage')
    groups=collections.defaultdict(list)
    for r in train:groups[r['label']].append(r)
    refs=[dict(label=label,sequence=np.round(r['sequence'],6).tolist(),file=r['file'],participant=r['participant']) for label in sorted(groups) for r in groups[label][:4]]
    if len(refs)>256 or len(groups)<2:raise ValueError('Wrong training bank size')
    sequences=np.asarray([r['sequence'] for r in refs]);labels=np.asarray([r['label'] for r in refs]);statistics=[]
    for i,r in enumerate(val):
        if r['sequence'] is None:statistics.append(None);continue
        a=np.asarray(r['sequence']);d=np.minimum(dtw_many(a,sequences),dtw_many(mirrored(a),sequences));ranking=np.argsort(d,kind='stable')
        label=str(labels[ranking[0]]);distance=float(d[ranking[0]]);other=float(d[next(j for j in ranking if labels[j]!=label)])
        statistics.append(dict(byLabel={str(l):float(d[labels==l].min()) for l in sorted(set(labels))},label=label,distance=distance,ratio=other/(distance+1e-6),votes=int((labels[ranking[:3]]==label).sum())))
        if i%20==0:print('Measured VAL statistics',i+1,'/',len(val),flush=True)
    candidate=dict(version=1,featureVersion='browser-domain-recovery-v1',samples=[dict(label=r['label'],sequence=r['sequence']) for r in refs],modes={})
    outputs={};guard_outputs={};comparison={};selection={}
    for mode,mode_labels in p['manualModes'].items():
        before=[r['baseline'][mode] for r in val];guarded=list(before);guardPolicies={};recoveryPolicies={};selection[mode]={}
        for label in mode_labels:
            chosen=select_guard(val,before,statistics,label,p['distanceLimits'],p['ratios'])
            if chosen:
                _,gate,accepted=chosen;guardPolicies[label]=gate
                for i,b in enumerate(before):
                    if b==label and i not in accepted:guarded[i]=None
        current=list(guarded)
        for label in mode_labels:
            chosen=select_recovery(val,guarded,statistics,label,p['distanceLimits'],p['ratios'],p['votes'])
            if chosen:
                _,gate,ids=chosen;recoveryPolicies[label]=gate
                for i in ids:current[i]=label
                selection[mode][label]=dict(correctSources=[val[i]['file'] for i in ids],signers=sorted({val[i]['participant'] for i in ids}))
        if any(r['label']==b and b is not None and b!=a for r,b,a in zip(val,before,current)):raise ValueError('Correct baseline recording lost')
        old=metrics(val,before,mode_labels);new=metrics(val,current,mode_labels)
        if new['wrong']>old['wrong'] or new['negativeFalse']>old['negativeFalse']:raise ValueError('New validation false accept')
        candidate['modes'][mode]=dict(labels=mode_labels,guardPolicies=guardPolicies,recoveryPolicies=recoveryPolicies)
        comparison[mode]=dict(baseline=old,candidate=new,guarded=metrics(val,guarded,mode_labels),guardClasses=list(guardPolicies),recoveryClasses=list(recoveryPolicies))
        outputs[mode]=current;guard_outputs[mode]=guarded;print(mode,json.dumps(comparison[mode]),flush=True)
    (folder/'candidate.json').write_text(json.dumps(candidate,separators=(',',':')),'utf-8')
    module=(ROOT/'training/experimental/browser_domain_recovery.mjs').as_uri()
    code='import {predictBrowserDomainRecovery} from '+json.dumps(module)+";let t='';for await(const c of process.stdin)t+=c;const i=JSON.parse(t);process.stdout.write(JSON.stringify(i.cases.map(c=>predictBrowserDomainRecovery(i.model,c.sequence,c.baseline))));"
    run=subprocess.run(['C:/Program Files/nodejs/node.exe','--input-type=module','-e',code],input=json.dumps(dict(model=candidate,cases=[dict(sequence=r['sequence'],baseline=r['baseline']) for r in val])),capture_output=True,text=True,check=True)
    actual=json.loads(run.stdout);max_error=0.
    for i,(r,a,s) in enumerate(zip(val,actual,statistics)):
        if a['predictions']!={m:outputs[m][i] for m in outputs} or a['guarded']!={m:guard_outputs[m][i] for m in outputs}:raise ValueError('Python/JS prediction parity failed')
        if s:
            if a['statistics']['label']!=s['label'] or a['statistics']['votes']!=s['votes']:raise ValueError('Python/JS rank parity failed')
            max_error=max(max_error,abs(s['distance']-a['statistics']['distance']),abs(s['ratio']-a['statistics']['ratio']))
    verify(p);verify({'frozenFilesSha256':features})
    report=dict(candidateSha256=sha(folder/'candidate.json'),comparison=comparison,selection=selection,trainSources=len(train),
        references=len(refs),trainCounts=dict(collections.Counter(r['label'] for r in train)),validationSources=len(val),
        failedValidationCaptures=sum(not r['contractPassed'] for r in val),featureFilesSha256=features,
        parity=dict(cases=len(val),modeOutcomes=len(val)*4,predictionsIdentical=True,maxDistanceOrRatioError=max_error),
        records=[dict(file=r['file'],label=r['label'],baseline=r['baseline'],candidate={m:outputs[m][i] for m in outputs}) for i,r in enumerate(val)],
        selectionSetOnly=True,independentAccuracy=False,deployed=False,productionFilesUnchanged=True,
        next='Freeze candidate, then same-capture independent online audit; do not select further gates from that audit.',seconds=round(time.perf_counter()-started,3))
    (folder/'validation.json').write_text(json.dumps(report,indent=2)+'\n','utf-8');print('Measured-browser candidate frozen, NOT deployed.',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--capture',type=Path);parser.add_argument('--out',type=Path)
    parser.add_argument('--fit',type=Path);a=parser.parse_args()
    if a.fit:fit(a.fit.resolve())
    elif a.capture and a.out:prepare(a.capture.resolve(),a.out.resolve())
    else:parser.error('Use --capture/--out to freeze before outcomes, then --fit after capture completion')
