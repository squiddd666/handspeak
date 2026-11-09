"""Freeze cohort, classifiers, and both sampling plans BEFORE any predictions."""
import argparse,datetime,hashlib,json,secrets
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main(args):
    folder=args.out.resolve();folder.relative_to((ROOT.parent/'hs-eval').resolve());folder.mkdir(exist_ok=False)
    cohort_path=ROOT/'reports/online-motion-audit-20261107/frozen-online-intake.json'
    cohort=json.loads(cohort_path.read_text(encoding='utf-8'));clips=cohort['clips']
    if len(clips)!=76 or len({c['sha256'] for c in clips})!=76 or cohort['trainingAllowed'] or cohort['calibrationAllowed']:
        raise ValueError('Expected the untouched 76-clip audit-only cohort')
    for c in clips:
        if sha(c['path'])!=c['sha256']:raise ValueError('Clip changed')
    for name,digest in cohort['modelAndRuntimeSha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Production model/runtime changed after intake: '+name)
    candidate=ROOT/'reports/motion-repair-v5-20261107/candidates/body-manual-24.json'
    validation=candidate.with_suffix('.validation.json');v=json.loads(validation.read_text(encoding='utf-8'))
    if sha(candidate)!=v['modelSha256'] or v['testUsedForSelection']:raise ValueError('Candidate is not validation-frozen')
    files=['landmark-capture.js','body-hand-recovery.js','hand-recovery-worker.js','camera-performance.js','motion-model.js',
           'gesture-model.js','expanded-motion.js','hello-binary.js','temporal-motion/temporal-features.js',
           'training/experimental/dual_capture.mjs','training/experimental/dual_hand_worker.js',
           'training/experimental/body_manual_runtime.mjs','training/experimental/online_manual_runtime.mjs',
           'training/experimental/online_dual_audit_page.mjs',
           'models/asl-words.json','models/asl-extra-words.json','models/hello-binary.json','models/baby-binary.json',
           'models/water-binary.json','models/research-words.json','models/motion-categories/pack-dtw.json',str(candidate.relative_to(ROOT))]
    script_files=['scripts/freeze_online_recognition_audit.py','scripts/run_online_native_audit.py','scripts/extract_native_motion_v4.py',
                  'scripts/audit_body_manual_v5.py','scripts/train_native_manual_v4.py','scripts/train_body_manual_v5.py',
                  'body_manual_features.py','scripts/serve_online_dual_audit.py','training/ux/run_online_dual_audit.mjs',
                  'scripts/report_online_recognition_audit.py']
    frozen={str(ROOT/name):sha(ROOT/name) for name in files+script_files}
    frozen.update({str(ROOT/name):digest for name,digest in cohort['modelAndRuntimeSha256'].items()})
    frozen[str(cohort_path)]=sha(cohort_path);frozen[str(validation)]=sha(validation)
    frozen.update({c['path']:c['sha256'] for c in clips})
    hand=ROOT.parent/'hs-eval/motion-repair-v5-20261107/hand_landmarker.task';frozen[str(hand)]=sha(hand)
    chrome=Path('C:/Program Files/Google/Chrome/Application/chrome.exe');frozen[str(chrome)]=sha(chrome)
    protocol=dict(frozenAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),purpose='audit-only',cohort=str(cohort_path),
                  cohortSha256=sha(cohort_path),candidate=str(candidate),candidateSha256=sha(candidate),nativeHandModel=str(hand),
                  chromeExecutable=str(chrome),
                  frozenFilesSha256=frozen,productionSha256=cohort['modelAndRuntimeSha256'],
                  manualModes=dict(default=['HELLO','THANK YOU','PLEASE','YES','NO','FINISH','BABY'],
                    expanded=['HELLO','THANK YOU','PLEASE','YES','NO','FINISH','BABY','DRINK','WATER','BOOK','FOOD','HUNGRY','LIKE','GO'],
                    daily=['NAME','HOME','HAVE','WANT','LOVE'],pack=['FISH','PAIN','SEE','SICK','NIGHT']),
                  candidateLabels=json.loads(candidate.read_text())['labels'],
                  nativeSampling=dict(samples=32,window='entire original clip, uniformly spaced unique source frame indices',
                    maximumImageSide=640,holistic='MediaPipe 0.10.21, complexity 1, smooth, detection/tracking .5',
                    manual='separate Tasks VIDEO, two hands, detection/presence/tracking .5',resetBothGraphsPerClip=True),
                  browserSampling=dict(canvas=[960,720],fps=30,fit='letterbox, no crop or mirror',playbackRate=1,
                    duration='4s if source <=3.8s, 6s if <=5.8s, otherwise 8s; longer clips are flagged truncated, not sped up',
                    capture='unchanged createLandmarkCapture sampler, countdown excluded, queued snapshots max side 640',
                    infrastructure='initialize detectors without images before the first take; each begin resets both graphs',
                    dualStream='copies of one immutable image, matching pixel digest/dimensions/timestamp/epoch; no cross-stream hand substitution',
                    contractFailure='reject all classifier outputs if capture contract fails',
                    browser='fresh headless Chrome profile, no user browser attached, no hardware permissions'),
                  order=[c['file'] for c in clips],attemptsPerClipPerPipeline=1,noBestOfRetries=True,
                  preflightTests=dict(targetedPythonPassed=22,captureContractJavaScriptPassed=23,fullApplicationSuiteClaimed=False),
                  recognitionPolicy='score independent frozen body candidate and all four manual modes; no cross-mode or expected-label winner selection',
                  scoring='every clip counts per mode; unsupported acceptance is false; rejected positive and tracking/capture failure are no match',
                  trainingAllowed=False,calibrationAllowed=False,candidatePromotionAllowed=False,
                  newSignerAudit=False,signerSeparationAcrossDatasetsVerified=False,full198Audit=False,fullProductionAppRoutingVerified=False,
                  transportCertificateVerified=False,
                  cohortTransportLimitation='Original publisher TLS certificate was untrusted on this host; source hashes are local consistency checks, not publisher authentication.')
    (folder/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n',encoding='utf-8')
    refs=[dict(id=c['file'],label=c['label'],video='/__online_clips__/'+c['file']+'.mp4',videoSha256=c['sha256']) for c in clips]
    cfg=dict(items=refs,candidate=str(candidate.relative_to(ROOT)).replace('\\','/'),filesSha256={n.replace('\\','/'):sha(ROOT/n) for n in files},
             token=secrets.token_urlsafe(32),protocolSha256=sha(folder/'protocol.json'))
    cfg['fixtureSha256']=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><title>Frozen online recognition audit</title>
<style>body{font:15px system-ui;background:#142024;color:#eee;padding:20px}video,canvas{width:240px;height:180px}button{padding:10px}pre{max-height:250px;overflow:auto}</style>
<h1>One-pass online recognition audit</h1><p>76 new recordings, known signers. Audit-only; no model or gate changes. Physical camera/microphone prohibited. All four manual modes are independently tested, not selected by expected label.</p>
<video id="source" muted playsinline controls></video><canvas id="virtualCanvas" width="960" height="720"></canvas><video id="virtualCamera" muted playsinline></video>
<select id="reference"></select><button id="arm">Arm</button><button id="record" disabled>Record</button><button id="cancel" disabled>Cancel</button><button id="blank">Blank</button>
<button id="batch">Run frozen 76-clip audit</button><button id="stop">Stop</button>
<p id="status">Loading infrastructure without images…</p><p id="summary"></p><p id="saved"></p><p id="batchStatus"></p><pre id="ledger"></pre>
<script>window.DUAL_CAPTURE_FIXTURE = CONFIG;</script><script type="module" src="/training/experimental/online_dual_audit_page.mjs"></script></html>'''
    (folder/'fixture.html').write_text(html.replace('CONFIG',json.dumps(cfg)),encoding='utf-8')
    (folder/'fixture.json').write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8')
    print('Frozen protocol:',folder/'protocol.json','76 clips, no inference run')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);main(p.parse_args())
