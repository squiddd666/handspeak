"""Freeze a purpose-built, landmark-only TRAIN/VAL domain capture harness."""
import argparse,datetime,hashlib,json,secrets
from pathlib import Path
from scripts.run_online_native_audit import ROOT,sha,verify

ASSETS=['landmark-capture.js','holistic-worker-tracker.js','holistic-body-worker.js',
    'legacy-holistic-worker-context.js','body-hand-recovery.js','hand-recovery-worker.js',
    'landmark-frame-geometry.js','camera-performance.js','gesture-model.js','motion-model.js',
    'training/experimental/dual_capture.mjs','training/experimental/dual_hand_worker.js',
    'training/experimental/prepared_tracker_factory.mjs','training/experimental/domain_capture_contract.mjs',
    'training/experimental/browser_domain_page.mjs']

CAPTURE_PURPOSES={
    'separate-browser-detector-domain-train-val-development':'browser-detector-domain-train-val-feature-capture',
    'phone-domain-train-val-feature-intake':'phone-domain-train-val-feature-capture',
    'full-family-body-domain-train-val-development':'full-family-body-domain-train-val-feature-capture',
}
ALLOWED_CAPTURE_PURPOSES=set(CAPTURE_PURPOSES.values())

def render(cfg):
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><title>TRAIN/VAL detector-domain capture</title>
<style>body{font:15px system-ui;background:#142024;color:#eee;padding:20px}video,canvas{width:240px;height:180px}button{padding:12px}</style>
<h1>Local TRAIN/VAL landmark capture</h1><p>Production body sampler and independent Tasks VIDEO stream. No image persistence, predictions, audit fitting or public templates.</p>
<video id="source" muted playsinline></video><canvas id="virtualCanvas" width="960" height="720"></canvas><video id="virtualCamera" muted playsinline></video>
<button id="batch">Run frozen one-pass capture</button><button id="stop">Stop</button>
<p id="status">Initializing without images…</p><p id="summary"></p><p id="saved"></p><p id="batchStatus"></p>
<script>window.DOMAIN_CAPTURE_FIXTURE = '''+json.dumps(cfg).replace('</','<\\/')+''';</script>
<script type="module" src="/training/experimental/browser_domain_page.mjs"></script></html>'''

def source_id(prefix,index):
    return f'{prefix}-{index:04d}' if prefix!='domain' else f'domain-{index:03d}'

def main(args):
    base=args.base.resolve();p=json.loads((base/'protocol.json').read_text('utf-8'));verify(p)
    if not p['trainingAllowed'] or not p['calibrationAllowed'] or not p['priorBrowserCheckExcluded']:
        raise ValueError('Separate permitted TRAIN/VAL intake required')
    if p['purpose'] not in CAPTURE_PURPOSES:raise ValueError('Unsupported development intake purpose')
    capture_purpose=CAPTURE_PURPOSES[p['purpose']]
    sources=json.loads(Path(p['sourceManifest']).read_text('utf-8'))
    if any(r['split'] not in ('train','val') or r['file'] in p['excludedBrowserSources'] for r in sources):raise ValueError('Excluded source')
    if {r['participant'] for r in sources if r['split']=='train'}&{r['participant'] for r in sources if r['split']=='val'}:raise ValueError('Signer overlap')
    out=args.out.resolve();out.relative_to((ROOT.parent/'hs-eval').resolve());out.mkdir(exist_ok=False)
    inherited=[];failed=[];skip=0;resume_frozen={};prefix=args.id_prefix
    if args.resume and args.continue_incomplete:
        raise ValueError('Use either --resume or --continue-incomplete, not both')
    if args.resume:
        old=args.resume.resolve();op=json.loads((old/'protocol.json').read_text('utf-8'))
        resolution=json.loads((old/'harness-resolution.json').read_text('utf-8'))
        for path,digest in op['frozenFilesSha256'].items():
            snapshot=Path(resolution[path]['snapshot']) if path in resolution else Path(path)
            if sha(snapshot)!=digest:raise ValueError('Failed-run original input no longer resolvable: '+path)
            resume_frozen[str(snapshot)]=digest
        inherited=json.loads((old/'features/checkpoint.json').read_text('utf-8'))
        disposition=json.loads((old/'failure-disposition.json').read_text('utf-8'))
        skip=len(disposition['attemptedSourceIds'])
        expected_ids=[source_id(prefix,i) for i in range(1,skip+1)]
        if skip!=len(inherited)+1 or disposition['attemptedSourceIds']!=expected_ids:raise ValueError('Unresolved prior attempt order; refuse a rerun')
        if disposition['missingFeatureSource']!=sources[skip-1]:raise ValueError('Wrong missing-feature source')
        failed=[dict(source=sources[skip-1],reason=disposition['reason'])]
        for row,source in zip(inherited,sources):
            if row['file']!=source['file'] or sha(Path(row['path']))!=row['sha256']:raise ValueError('Prior measured feature changed')
            resume_frozen[row['path']]=row['sha256']
        for n in ('protocol.json','harness-resolution.json','failure-disposition.json','features/checkpoint.json'):
            resume_frozen[str(old/n)]=sha(old/n)
    elif args.continue_incomplete:
        # Deadline/interrupt continuation: keep every durable feature, do not invent a
        # failed disposition for unreached sources, and never reshuffle order.
        old=args.continue_incomplete.resolve();op=json.loads((old/'protocol.json').read_text('utf-8'))
        if op.get('idPrefix',prefix)!=prefix:raise ValueError('Continue-incomplete id prefix mismatch')
        if (old/'capture-summary.json').exists():raise ValueError('Prior capture already completed; refuse continuation')
        inherited=json.loads((old/'features/checkpoint.json').read_text('utf-8'))
        expected_ids=[source_id(prefix,i) for i in range(1,len(inherited)+1)]
        if [row['id'] for row in inherited]!=expected_ids:raise ValueError('Incomplete capture ledger order is not contiguous')
        if [row['id'] for row in inherited]!=op['order'][:len(inherited)]:raise ValueError('Checkpoint diverged from prior frozen order')
        skip=len(inherited)
        if skip>=len(sources):raise ValueError('No remaining sources to continue')
        for row,source in zip(inherited,sources):
            if row['file']!=source['file'] or sha(Path(row['path']))!=row['sha256']:raise ValueError('Prior measured feature changed')
            resume_frozen[row['path']]=row['sha256']
        for n in ('protocol.json','features/checkpoint.json','final-page-state.json','cleanup-receipt.json'):
            path=old/n
            if path.exists():resume_frozen[str(path)]=sha(path)
        interruption=dict(reason='Capture runner deadline exceeded after durable partial ledger; unreached sources were not marked failed and are continued exactly once.',
            completedIds=[row['id'] for row in inherited],remainingIds=[source_id(prefix,i) for i in range(skip+1,len(sources)+1)],
            predictionsRun=False,trainingRun=False)
        (out/'continuation-disposition.json').write_text(json.dumps(interruption,indent=2)+'\n','utf-8')
        resume_frozen[str(out/'continuation-disposition.json')]=sha(out/'continuation-disposition.json')
    original_sources=p['sourceManifest'];sources=sources[skip:]
    (out/'sources.json').write_text(json.dumps(sources,indent=2)+'\n','utf-8')
    names=ASSETS+['scripts/freeze_browser_domain_capture.py','scripts/serve_browser_domain_capture.py',
        'training/ux/run_browser_domain_capture.mjs','training/test_browser_domain_capture.py','training/test_domain_capture_contract.mjs']
    frozen=dict(p['frozenFilesSha256']);frozen.update(resume_frozen);frozen.update({str(ROOT/n):sha(ROOT/n) for n in names})
    frozen[str(base/'protocol.json')]=sha(base/'protocol.json')
    frozen[str(out/'sources.json')]=sha(out/'sources.json')
    refs=[dict(id=source_id(prefix,i),video=f'/__development_clips__/{source_id(prefix,i)}.mp4',videoSha256=r['sha256']) for i,r in enumerate(sources,skip+1)]
    # Labels/signers/splits are stored server-side only, not passed to detectors.
    allowed={'/'+n:str(ROOT/n) for n in ASSETS};allowed.update({ref['video']:r['path'] for ref,r in zip(refs,sources)})
    allowed['/fixture.html']=str(out/'fixture.html')
    cfg=dict(items=refs,allowedFiles=allowed,token=secrets.token_urlsafe(32))
    cfg['fixtureSha256']=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()
    (out/'fixture.json').write_text(json.dumps(cfg,indent=2)+'\n','utf-8');(out/'fixture.html').write_text(render(cfg),'utf-8')
    frozen[str(out/'fixture.json')]=sha(out/'fixture.json');frozen[str(out/'fixture.html')]=sha(out/'fixture.html')
    prior=json.loads((ROOT.parent/'hs-eval/online-worker-recognition-audit-20261108/protocol.json').read_text('utf-8'))
    scopes={
        'browser-detector-domain-train-val-feature-capture':'Previously acquired official TRAIN/VAL, not independent accuracy. This manual-targeted 57-label cohort is not full-198 support.',
        'phone-domain-train-val-feature-capture':'Official PopSign phone-camera TRAIN/VAL only, not independent accuracy. Guard-audit54 stays fitting-excluded.',
        'full-family-body-domain-train-val-feature-capture':'Full-family Citizen TRAIN/VAL remainder after prior domain dispositions, not independent accuracy or new-signer proof.',
    }
    plan=dict(frozenAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),purpose=capture_purpose,
        base=str(base),sourceManifest=str(out/'sources.json'),originalSourceManifest=original_sources,
        inheritedFeatures=inherited,inheritedFailedSources=failed,previousAttemptsNotRepeated=skip,
        order=[r['id'] for r in refs],frozenFilesSha256=frozen,
        manualModes=p['manualModes'],support=p['support'],chromeExecutable=prior['chromeExecutable'],
        port=args.port,debugPort=args.debug_port,idPrefix=prefix,
        sampler='Unmodified production createLandmarkCapture; 4/6/8 second window; at most 80 real unique snapshots; warmup excluded.',
        geometry='Original-rate video contained on 960x720 virtual camera; production snapshots 640x480; no stretch, no hand-output fusion.',
        features='Measured seven-pose-joint body payload and all observed 21-point hands; independent VIDEO-mode manual slots; one timestamped immutable source per pair.',
        failedCapturePolicy='Keep partial measured evidence, mark contractPassed=false, never train/select from failed captures; no best-of capture retries.',
        scope=scopes[capture_purpose],
        storage='Originals/landmarks stay in external local noncommercial research folder; temporary images released in browser memory; no public redistribution.',
        trainingAllowed=True,calibrationAllowed=True,predictionsRun=False,auditInputsAllowed=False,deploymentAllowed=False,
        noPhysicalCamera=True,noMicrophone=True,noProductionDatabase=True,noExpectedWordHints=True)
    (out/'protocol.json').write_text(json.dumps(plan,indent=2)+'\n','utf-8')
    print(json.dumps(dict(sources=len(refs),priorAttemptsRetained=skip,originalCounts=p['counts'],purpose=capture_purpose,protocol=str(out/'protocol.json'),predictionsRun=False)),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--resume',type=Path)
    parser.add_argument('--continue-incomplete',type=Path,
        help='Continue a deadline-interrupted capture from its durable checkpoint without inventing failed sources')
    parser.add_argument('--port',type=int,default=8013);parser.add_argument('--debug-port',type=int,default=9233)
    parser.add_argument('--id-prefix',default='domain',choices=('domain','phone','body'))
    main(parser.parse_args())
