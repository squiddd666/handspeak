"""Train-reference competition and validation-only rejection gates; never deploy."""
import argparse,collections,json,math,time,subprocess
from pathlib import Path
import numpy as np
from scripts.run_online_native_audit import ROOT,sha,verify
from scripts.audit_body_manual_v5 import Baseline,BASELINE_FILES
from scripts.train_native_manual_v4 import prototypes,dtw_many,mirrored,metrics

VERSION='manual-open-set-competition-v1'


def verify_dev(p):
    verify({'frozenFilesSha256':{**p['productionFrozenFilesSha256'],**p['frozenInputsSha256'],**p['sourceOriginalsSha256']}})


def statistics(distances,refs,label):
    names=np.asarray([r['label'] for r in refs]);same=float(np.min(distances[names==label])) if np.any(names==label) else math.inf
    other=float(np.min(distances[names!=label])) if np.any(names!=label) else math.inf
    ratio=other/(same+1e-6) if math.isfinite(same) and math.isfinite(other) else 0.
    return same,other,ratio


def apply_gate(before,stats,limit,ratio):
    return [label if label is not None and math.isfinite(s[0]) and math.isfinite(s[1]) and s[0]<=limit and s[2]>=ratio else None for label,s in zip(before,stats)]


def select_gate(rows,before,stats,labels,limits,ratios):
    old=metrics(rows,before,labels);best=None
    for limit in limits:
        for ratio in ratios:
            out=apply_gate(before,stats,limit,ratio);current=metrics(rows,out,labels)
            if current['correct']!=old['correct'] or current['wrong']>old['wrong'] or current['negativeFalse']>old['negativeFalse']:
                continue
            # Total correct retention for a rejection-only gate also means no
            # correctly accepted individual recording can have been lost.
            if any(r['label']==b and b is not None and a!=b for r,b,a in zip(rows,before,out)):raise AssertionError('Correct accept changed')
            key=(-current['negativeFalse'],-current['wrong'],-ratio,limit)
            if best is None or key>best[0]:best=(key,limit,ratio,current,out)
    improved=best is not None and old['negativeFalse']>0 and best[3]['negativeFalse']<=math.floor(old['negativeFalse']*.75)
    if not improved:return dict(enabled=False,labels=labels,maxDistance=10.,minRatio=0.),dict(before=old,after=old,eligible=False,reason='No >=25% unsupported reduction without losing correct validation accepts'),list(before)
    _,limit,ratio,current,out=best
    return dict(enabled=True,labels=labels,maxDistance=limit,minRatio=ratio),dict(before=old,after=current,eligible=True,correctRecordingRetention=True),out


def train(args):
    folder=args.protocol.resolve().parent;p=json.loads(args.protocol.read_text('utf-8'));verify_dev(p)
    if (folder/'candidate.json').exists() or (folder/'training-started.json').exists():raise FileExistsError('Development run already started; no silent overwrite/reselection')
    (folder/'training-started.json').write_text(json.dumps({'protocolSha256':sha(args.protocol),'stage':'development-only'})+'\n','utf-8')
    started=time.perf_counter();raw=[json.loads(l) for l in Path(p['nativeArchive']).read_text('utf-8').splitlines() if l.strip()]
    manifest=json.loads((folder/'source-manifest.json').read_text('utf-8'));meta={r['file']:r for r in manifest}
    if len(raw)!=len(meta) or any(r['file'] not in meta or r['split'] not in ('train','val') for r in raw):raise ValueError('Development manifest mismatch')
    baseline=Baseline();encoded=[]
    for r in raw:
        value=json.loads(baseline.js.eval('JSON.stringify(prepareAudit('+json.dumps(r['rawFrames'])+','+str(r['imageAspect'])+'))'))
        sequence=value['sequence']
        if sequence is not None and not baseline.js.eval('validMotion('+json.dumps(sequence)+')'):sequence=None
        encoded.append({**meta[r['file']],'sequence':sequence})
    train=[r for r in encoded if r['split']=='train' and r['sequence'] is not None];groups=collections.defaultdict(list)
    for r in train:groups[r['label']].append(r)
    expected_labels=set().union(*map(set,p['manualModes'].values()))
    if any(len(groups[l])<3 for l in expected_labels):raise ValueError('Insufficient usable training references for all manual labels')
    refs=[]
    for label in sorted(groups):
        for r in prototypes(groups[label],4):refs.append(dict(label=label,file=r['file'],participant=r['participant'],sequence=np.round(np.asarray(r['sequence']),6).tolist()))
    if len(refs)>p['maxPrototypeCount']:raise ValueError('Prototype bank exceeds the predeclared bound')
    ref_sequences=np.asarray([r['sequence'] for r in refs]);validation=[];all_stats={m:[] for m in p['manualModes']}
    val_raw=[r for r in raw if r['split']=='val'];enc={r['file']:r for r in encoded}
    print('TRAIN usable',len(train),'labels',len(groups),'references',len(refs),'VAL',len(val_raw),flush=True)
    # Use the exact current JavaScript baseline rather than the old offline
    # adapter, whose missing-sequence specialist behavior differs from the app.
    print('Computing actual current JavaScript baseline, without expected labels…',flush=True)
    node_input=dict(models={k:json.loads((ROOT/n).read_text('utf-8')) for k,n in BASELINE_FILES.items()},
        cases=[dict(rawFrames=r['rawFrames'],imageAspect=r['imageAspect']) for r in val_raw])
    run=subprocess.run(['C:/Program Files/nodejs/node.exe',str(ROOT/'training/ux/run_manual_guard_baseline.mjs')],
        input=json.dumps(node_input),capture_output=True,text=True,check=True)
    actual_baseline=json.loads(run.stdout)
    if len(actual_baseline)!=len(val_raw):raise ValueError('Incomplete exact-baseline validation')
    archive=[]
    with (folder/'validation-baseline.jsonl').open('x',encoding='utf-8') as sink:
        for i,r in enumerate(val_raw,1):
            item=dict(enc[r['file']]);actual=actual_baseline[i-1]
            item['sequence']=actual['sequence'];predictions=actual['baseline'];validation.append(item)
            seq=item['sequence'];d=np.full(len(refs),np.inf) if seq is None else np.minimum(dtw_many(seq,ref_sequences),dtw_many(mirrored(np.asarray(seq)),ref_sequences))
            row_stats={}
            for mode,labels in p['manualModes'].items():
                label=predictions[mode];s=statistics(d,refs,label) if label is not None and seq is not None else (math.inf,math.inf,0.)
                all_stats[mode].append(s);row_stats[mode]=[v if math.isfinite(v) else None for v in s]
            record=dict(file=r['file'],split='val',label=item['label'],sequenceUsable=seq is not None,baseline=predictions,guardStats=row_stats)
            sink.write(json.dumps(record)+'\n');sink.flush();archive.append(record)
            if i%20==0 or i==len(val_raw):print('Validation',i,'/',len(val_raw),'seconds',round(time.perf_counter()-started,1),flush=True)
    policies={};comparison={};after={}
    for mode,labels in p['manualModes'].items():
        before=[r['baseline'][mode] for r in archive]
        policies[mode],comparison[mode],after[mode]=select_gate(validation,before,all_stats[mode],labels,p['limits'],p['ratios'])
        comparison[mode]['perLabel']={label:{'before':metrics([r for r in validation if r['label']==label],[o for r,o in zip(validation,before) if r['label']==label],labels),
            'after':metrics([r for r in validation if r['label']==label],[o for r,o in zip(validation,after[mode]) if r['label']==label],labels)} for label in labels}
        print(mode,json.dumps({k:v for k,v in comparison[mode].items() if k!='perLabel'}),flush=True)
    model=dict(version=1,featureVersion=VERSION,encoding='two-hand-motion-v3',modes=policies,
        samples=[dict(label=r['label'],sequence=r['sequence']) for r in refs],purpose='offline-rejection-only-candidate-not-deployed')
    with (folder/'candidate.json').open('x',encoding='utf-8') as f:json.dump(model,f,separators=(',',':'))
    verify_dev(p)
    report=dict(modelSha256=sha(folder/'candidate.json'),protocolSha256=sha(args.protocol),nativeSha256=p['nativeSha256'],
        sourceManifestSha256=sha(folder/'source-manifest.json'),baselineArchiveSha256=sha(folder/'validation-baseline.jsonl'),
        fittingSplit='train',gateSelectionSplit='val',testUsedForSelection=False,watchUsedForSelection=False,auditOutcomesReadForSelection=False,
        trainSources=len([r for r in encoded if r['split']=='train']),usableTrainSources=len(train),trainCounts=dict(collections.Counter(r['label'] for r in train)),
        validationSources=len(validation),referenceCount=len(refs),referenceSources=[{k:r[k] for k in ('file','participant','label')} for r in refs],
        comparison=comparison,records=[dict(file=r['file'],label=r['label'],baseline=r['baseline'],candidate={m:after[m][i] for m in after}) for i,r in enumerate(archive)],
        productionFilesUnchanged=True,deployed=False,eligibleForBrowserDevelopment=any(v['enabled'] for v in policies.values()),
        scope='Selection-set native validation only, not independent test or browser accuracy. Guard only vetoes baseline accepts; no new correct accepts or repaired capture claims.',seconds=round(time.perf_counter()-started,3))
    with (folder/'validation.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print('Candidate frozen, not installed:',folder/'candidate.json',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--protocol',type=Path,required=True);train(parser.parse_args())
