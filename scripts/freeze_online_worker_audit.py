"""Configurable successor: freeze fresh originals and repaired worker/API audit."""
import argparse, datetime, hashlib, json, secrets
from pathlib import Path
from scripts.prepare_online_motion_audit import ROOT, sha, write_new
from scripts.prepare_online_worker_audit import WORKER_FILES
from scripts.run_online_native_audit import verify

ASSETS = WORKER_FILES + ['motion-model.js','gesture-model.js','expanded-motion.js','hello-binary.js',
    'temporal-motion/temporal-features.js','training/experimental/dual_capture.mjs','training/experimental/dual_hand_worker.js',
    'training/experimental/body_manual_runtime.mjs','training/experimental/online_manual_runtime.mjs',
    'training/experimental/online_worker_audit_page.mjs','models/asl-words.json','models/asl-extra-words.json',
    'models/hello-binary.json','models/baby-binary.json','models/water-binary.json','models/research-words.json',
    'models/motion-categories/pack-dtw.json','reports/motion-repair-v5-20261107/candidates/body-manual-24.json']
MANUAL_MODES = dict(default=['HELLO','THANK YOU','PLEASE','YES','NO','FINISH','BABY'],
    expanded=['HELLO','THANK YOU','PLEASE','YES','NO','FINISH','BABY','DRINK','WATER','BOOK','FOOD','HUNGRY','LIKE','GO'],
    daily=['NAME','HOME','HAVE','WANT','LOVE'],pack=['FISH','PAIN','SEE','SICK','NIGHT'])


def main(args):
    folder=args.out.resolve(); folder.relative_to((ROOT.parent/'hs-eval').resolve())
    folder.mkdir(exist_ok=args.development is False)
    if (folder/'protocol.json').exists(): raise FileExistsError('Already frozen; no reselection/replay')
    prior_path=args.pre_acquisition.resolve(); prior=json.loads(prior_path.read_text('utf-8')); verify(prior)
    frozen=dict(prior['frozenFilesSha256']); clips=[]; evidence={str(prior_path):sha(prior_path)}
    if not args.development:
        if not args.preflight: raise ValueError('Successful isolated development preflight required before the fresh audit')
        preflight=args.preflight.resolve()
        pp=json.loads((preflight/'protocol.json').read_text('utf-8'))
        resolution_path=preflight/'harness-resolution.json'
        resolutions=json.loads(resolution_path.read_text('utf-8')) if resolution_path.exists() else {}
        for name,digest in pp['frozenFilesSha256'].items():
            if sha(Path(name))==digest: continue
            snapshot=Path(resolutions.get(name,{}).get('snapshot',''))
            snapshot.resolve().relative_to(preflight)
            if not snapshot.is_file() or sha(snapshot)!=digest: raise ValueError('Changed development preflight input cannot be resolved: '+name)
        result=json.loads((preflight/'browser-ledger/checkpoint.json').read_text('utf-8'))
        if pp['purpose']!='development-only' or len(result['attempts'])!=1 or not result['attempts'][0]['contractPassed']:
            raise ValueError('Missing passed development capture contract')
        if len(list((preflight/'api-receipts').glob('*.json')))!=4:
            raise ValueError('All four real production modes must be checked on development input first')
        for p in preflight.rglob('*'):
            if p.is_file() and ('browser-ledger' in p.parts or 'api-receipts' in p.parts or p.name in ('protocol.json','post-run-integrity.json','infrastructure-checks.json','cleanup-receipt.json')):
                evidence[str(p)]=sha(p)
        if resolutions:
            evidence[str(resolution_path)]=sha(resolution_path)
            evidence.update({r['snapshot']:sha(Path(r['snapshot'])) for r in resolutions.values()})
        for name in ('worker-audit-python-preflight-20261108.log','worker-audit-js-preflight-20261108.log'):
            p=ROOT.parent/'hs-eval'/name; evidence[str(p)]=sha(p)
    transport=False; exclusions=[]
    if args.development:
        manifest=ROOT.parent/'hs-eval/capture-throughput-dev-20261108/capture-final-smoke/config.json'
        dev=json.loads(manifest.read_text('utf-8'))
        # One predefined used train recording, never chosen using fresh outcomes.
        i=dev['fixture']['items'][0]
        clips=[dict(file='dev-1',label='HELLO',path=i['path'],sha256=i['sha256'],participant='ASLCitizen:P11',
                    split='development-only',member='previously-used-train-fixture',fullDecodePassed=True)]
        evidence[str(manifest)]=sha(manifest)
    else:
        batch=args.batch.resolve(); rows=json.loads((batch/'downloads.json').read_text('utf-8'))
        acquisition=json.loads((batch/'protocol.json').read_text('utf-8'))
        health=json.loads((batch/'video-integrity.json').read_text('utf-8'))
        inventory_path=folder/'excluded-identity-inventory.json'; inventory=json.loads(inventory_path.read_text('utf-8'))
        known_keys={tuple(k) for k in inventory['recordingKeys']}; known_hashes=set(inventory['hashes'])
        seen=set(); checks={h['auditId']:h for h in health['files']}
        for row in rows:
            if not row['auditEligible']:
                exclusions.append(row); continue
            if tuple(row['recordingKey']) in known_keys or row['sha256'] in known_hashes or row['sha256'] in seen:
                raise ValueError('Claimed fresh recording overlaps the pre-acquisition inventory')
            seen.add(row['sha256'])
            clips.append(dict(file=row['auditId'],label=row['label'],path=row['path'],sha256=row['sha256'],
                participant='PopSignV1:'+row['participant'],split='audit-only',member=row['member'],
                source=row['source'],publisherLabel=row['publisherLabel'],publisherSplit=row['publisherSplit'],
                fullDecodePassed=checks[row['auditId']]['fullDecodePassed']))
        for name in ('protocol.json','downloads.json','summary.json','frozen-selection.json','video-integrity.json'):
            evidence[str(batch/name)]=sha(batch/name)
        evidence[str(inventory_path)]=sha(inventory_path)
        transport=acquisition['transportCertificateVerified']
    if not clips: raise ValueError('No recording-new originals available; do not pretend an audit ran')
    for clip in clips:
        if sha(Path(clip['path']))!=clip['sha256']: raise ValueError('Original clip changed')
        frozen[clip['path']]=clip['sha256']
    candidate=ROOT/ASSETS[-1]; validation=candidate.with_suffix('.validation.json')
    v=json.loads(validation.read_text('utf-8'))
    if v['modelSha256']!=sha(candidate) or v['testUsedForSelection']: raise ValueError('Candidate is not validation-frozen')
    write_new(folder/'cohort.json',dict(purpose='development-only' if args.development else 'audit-only',clips=clips,
        recordingNew=not args.development,newSignerAudit=False,crossDatasetSignerSeparationVerified=False,
        trainingAllowed=False,calibrationAllowed=False,excludedRecords=exclusions,sourceEvidenceSha256=evidence))
    frozen.update(evidence); frozen[str(folder/'cohort.json')]=sha(folder/'cohort.json')
    scripts=['scripts/freeze_online_worker_audit.py','scripts/prepare_online_worker_audit.py','scripts/prepare_online_motion_audit.py',
        'scripts/serve_online_worker_audit.py','scripts/serve_capture_throughput_dev.py','scripts/run_online_native_audit.py',
        'scripts/report_online_worker_audit.py','scripts/verify_online_audit_videos.py','training/ux/run_online_worker_audit.mjs',
        'training/test_online_worker_audit.py','training/test_online_worker_audit.mjs']
    frozen.update({str(ROOT/n):sha(ROOT/n) for n in ASSETS+scripts})
    frozen[str(validation)]=sha(validation)
    chrome=Path('C:/Program Files/Google/Chrome/Application/chrome.exe'); frozen[str(chrome)]=sha(chrome)
    status=prior['productionStatus']
    production_modes={'beginner':status['beginner']['labels'],'capstone-core':status['capstone']['coreLabels'],
        'capstone-extended':status['capstone']['extendedLabels'],'capstone-full':status['capstone']['labels']}
    protocol=dict(schema=4,frozenAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        purpose='development-only' if args.development else 'audit-only',cohort=str(folder/'cohort.json'),
        frozenFilesSha256=frozen,classifierArtifactsSha256=prior['classifierArtifactsSha256'],productionStatus=status,
        manualModes=MANUAL_MODES,productionModes=production_modes,candidateLabels=json.loads(candidate.read_text('utf-8'))['labels'],
        candidatePromotionAllowed=False,trainingAllowed=False,calibrationAllowed=False,chromeExecutable=str(chrome),
        order=[c['file'] for c in clips],attemptsPerClip=1,noBestOfRetries=True,
        capture=dict(canvas=[960,720],fps=30,fit='letterbox, no crop, no mirror',playbackRate=1,
            duration='4s for source <=3.8s, 6s <=5.8s, otherwise 8s; preserve and flag truncation',
            countdown='source paused at frame zero; normal 1.5s minimum pose warm-up; failures retained',
            sampling='Unchanged createLandmarkCapture snapshot/queue/drain policy; maximum side 640, 80-image bound',
            body='Actual default supported-browser Holistic worker + optional same-image recovery',
            manual='Independent Tasks VIDEO worker; paired immutable pixels/epoch/timestamps/dimensions, no hand fusion',
            resetBothGraphsPerClip=True,contractFailure='No classifier/API output accepted',
            infrastructure='Preinitialize without images; owned headless Chrome/SwiftShader, no hardware permissions'),
        api=dict(endpoints=['/api/beginner-asl','/api/capstone-asl'],consent=True,minBodyFrames=5,timeoutMs=20000,
            input='Unmodified captured body frames; no label/minScore/expected-word hints. All modes independently tested.',
            acceptance='Only predictions[0].label, never unaccepted suggestions',
            receipts='Append-only scalar response + landmark payload digest, no images or stored landmarks',
            isolation='Loopback allowlist, fresh SQLite folder, MySQL config cleared, no run()/warm interpreter/user database'),
        scoring='Literal exact label match within each frozen vocabulary; positives include failures/rejections. Every other label is a mode-specific negative. Never merge modes or normalize gloss variants.',
        newSignerAudit=False,full198Audit=False,fullProductionAppRoutingVerified=False,
        transportCertificateVerified=transport,transportLimitation='Publisher TLS chain untrusted on this host; public-original-host-only unverified TLS used without credentials. Local hashes are consistency checks, not publisher authentication.' if not args.development and not transport else None)
    write_new(folder/'protocol.json',protocol)
    refs=[dict(id=c['file'],label=c['label'],video='/__worker_clips__/'+c['file']+'.mp4',videoSha256=c['sha256']) for c in clips]
    allowed={'/'+n.replace('\\','/'):str(ROOT/n) for n in ASSETS}
    allowed.update({r['video']:c['path'] for r,c in zip(refs,clips)})
    allowed['/fixture.html']=str(folder/'fixture.html')
    cfg=dict(items=refs,candidate=ASSETS[-1],allowedFiles=allowed,token=secrets.token_urlsafe(32),protocolSha256=sha(folder/'protocol.json'))
    cfg['fixtureSha256']=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()
    write_new(folder/'fixture.json',cfg)
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><title>Frozen worker recognition audit</title>
<style>body{font:15px system-ui;background:#142024;color:#eee;padding:20px}video,canvas{width:240px;height:180px}button{padding:10px}pre{max-height:250px;overflow:auto}</style>
<h1>Frozen worker recognition audit</h1><p>COUNT originals. Separate mode denominators; no retraining, gate changes or candidate promotion. Not a full-198 or new-signer audit.</p>
<video id="source" muted playsinline controls></video><canvas id="virtualCanvas" width="960" height="720"></canvas><video id="virtualCamera" muted playsinline></video>
<select id="reference"></select><button id="arm">Arm</button><button id="record" disabled>Record</button><button id="cancel" disabled>Cancel</button><button id="blank">Blank</button>
<button id="batch">Run frozen one-pass batch</button><button id="stop">Stop</button>
<p id="status">Loading infrastructure without images…</p><p id="summary"></p><p id="saved"></p><p id="batchStatus"></p><pre id="ledger"></pre>
<script>window.DUAL_CAPTURE_FIXTURE = CONFIG;</script><script type="module" src="/training/experimental/online_worker_audit_page.mjs"></script></html>'''
    with (folder/'fixture.html').open('x',encoding='utf-8') as f: f.write(html.replace('COUNT',str(len(clips))).replace('CONFIG',json.dumps(cfg)))
    print('Frozen:',folder/'protocol.json',len(clips),'clips, no predictions run')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--out',type=Path,required=True)
    p.add_argument('--pre-acquisition',type=Path,required=True); p.add_argument('--batch',type=Path)
    p.add_argument('--development',action='store_true'); p.add_argument('--preflight',type=Path); main(p.parse_args())
