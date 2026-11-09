"""Select separate TRAIN/VAL originals for detector-domain development only."""
import argparse,collections,datetime,json
from pathlib import Path
from scripts.run_online_native_audit import ROOT,sha
from scripts.train_manual_open_set_guard import verify_dev


def select_sources(rows,excluded,labels):
    # Metadata only: no prediction, distance, tracking-health or best-of fields
    # participate in selection. Previously frozen browser checks are excluded.
    selected=[]
    names=sorted({r['label'] for r in rows})
    for split in ('train','val'):
        for label in names:
            count=(4 if split=='train' else 3) if label in labels else 2
            pool=sorted((r for r in rows if r['split']==split and r['label']==label and r['file'] not in excluded),key=lambda r:r['file'])
            selected.extend(pool[:count])
    if len({r['file'] for r in selected})!=len(selected):raise ValueError('Source identity overlap')
    train={r['participant'] for r in selected if r['split']=='train'};val={r['participant'] for r in selected if r['split']=='val'}
    if train&val:raise ValueError('Train/validation signer overlap')
    return selected


def main(args):
    base=args.base.resolve();p=json.loads((base/'protocol.json').read_text('utf-8'));verify_dev(p)
    check=args.browser_check.resolve();exclusion=json.loads((check/'cohort.json').read_text('utf-8'))
    rows=json.loads((base/'source-manifest.json').read_text('utf-8'));excluded={r['sourceFile'] for r in exclusion['clips']}
    labels=set().union(*map(set,p['manualModes'].values()));selected=select_sources(rows,excluded,labels)
    out=args.out.resolve();out.relative_to((ROOT.parent/'hs-eval').resolve());out.mkdir(exist_ok=False)
    sources=[{k:r[k] for k in ('file','path','sha256','split','participant','gloss','label')} for r in selected]
    with (out/'sources.json').open('x',encoding='utf-8') as f:json.dump(sources,f,indent=2)
    support={}
    for label in sorted(labels):
        tr=[r for r in sources if r['split']=='train' and r['label']==label];va=[r for r in sources if r['split']=='val' and r['label']==label]
        support[label]=dict(train=len(tr),val=len(va),valSigners=len({r['participant'] for r in va}),
            minimumMetadataSupport=len(tr)>=3 and len(va)>=3 and len({r['participant'] for r in va})>=2)
    names=['landmark-capture.js','holistic-worker-tracker.js','holistic-body-worker.js','legacy-holistic-worker-context.js',
        'body-hand-recovery.js','hand-recovery-worker.js','landmark-frame-geometry.js','camera-performance.js','gesture-model.js','motion-model.js',
        'training/experimental/dual_capture.mjs','training/experimental/dual_hand_worker.js','training/experimental/prepared_tracker_factory.mjs',
        'scripts/prepare_browser_domain_development.py','training/test_browser_domain_development.py']
    frozen={str(ROOT/n):sha(ROOT/n) for n in names};frozen[str(base/'protocol.json')]=sha(base/'protocol.json')
    frozen[str(base/'source-manifest.json')]=sha(base/'source-manifest.json');frozen[str(check/'cohort.json')]=sha(check/'cohort.json')
    frozen[str(out/'sources.json')]=sha(out/'sources.json');frozen.update({r['path']:r['sha256'] for r in sources})
    protocol=dict(frozenAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),purpose='separate-browser-detector-domain-train-val-development',
        frozenFilesSha256=frozen,sourceManifest=str(out/'sources.json'),manualModes=p['manualModes'],predeclaredAliases=p['predeclaredManualAliases'],
        counts=dict(collections.Counter(r['split'] for r in sources)),support=support,excludedBrowserSources=sorted(excluded),
        selection='First four remaining TRAIN and three remaining VAL filenames per manual label; first two per other label per split. Metadata only; all sparse support is reported.',
        fitting='TRAIN measured production-equivalent detector features only; gate selection on separate VAL only. Require correct-retention and unsupported-sign checks before independent audit.',
        source='Previously acquired official ASL Citizen TRAIN/VAL originals, not new recordings or new signers.',
        capture='Use the frozen production sampler with separately measured immutable Holistic/Tasks VIDEO streams; original rate, letterbox 960x720, maximum tracked side 640, no hand-output fusion.',
        storage='Temporary camera images stay in tab memory. Only derived TRAIN/VAL landmark features may be stored in this local external research directory; no served/public template redistribution.',
        license=p['sourceLicense'],watchExcluded=True,officialTestExcluded=True,priorOnlineAuditsExcluded=True,
        priorBrowserCheckExcluded=True,priorBrowserOutcomesReadForSelection=False,predictionsRun=False,featuresCaptured=False,
        trainingAllowed=True,calibrationAllowed=True,productionDeploymentAllowed=False,independentAccuracy=False,
        followup='Freeze a purpose-built feature capture harness before recording. Never reuse excluded browser-check or independent audit outcomes for further gate selection.')
    with (out/'protocol.json').open('x',encoding='utf-8') as f:json.dump(protocol,f,indent=2)
    print(json.dumps(dict(counts=protocol['counts'],manualLabels=len(labels),metadataSupportPassed=sum(s['minimumMetadataSupport'] for s in support.values()),
        excludedPriorBrowserRecordings=len(excluded),predictionsRun=False,featuresCaptured=False)),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--browser-check',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);main(parser.parse_args())
