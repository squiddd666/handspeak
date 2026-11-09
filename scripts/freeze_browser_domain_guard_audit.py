"""Freeze browser-domain guard against 54 untouched, audit-only PopSign originals."""
import argparse,hashlib,json,secrets
from pathlib import Path
from scripts.run_online_native_audit import ROOT,sha,verify
from scripts.freeze_online_worker_audit import ASSETS,MANUAL_MODES

def render(cfg):
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><title>Frozen independent recording guard audit</title>
<style>body{font:15px system-ui;background:#142024;color:#eee;padding:20px}video,canvas{width:240px;height:180px}button{padding:12px}pre{max-height:250px;overflow:auto}</style>
<h1>Frozen unused-recording guard audit</h1><p>54 audit-only public originals. Same capture for baseline/candidate. No fitting, retries, new-signer claims, or user cameras.</p>
<video id="source" muted playsinline controls></video><canvas id="virtualCanvas" width="960" height="720"></canvas><video id="virtualCamera" muted playsinline></video>
<select id="reference"></select><button id="arm">Arm</button><button id="record" disabled>Record</button><button id="cancel" disabled>Cancel</button><button id="blank">Blank</button>
<button id="batch">Run frozen one-pass audit</button><button id="stop">Stop</button>
<p id="status">Initializing without images…</p><p id="summary"></p><p id="saved"></p><p id="batchStatus"></p><pre id="ledger"></pre>
<script>window.DUAL_CAPTURE_FIXTURE = '''+json.dumps(cfg).replace('</','<\\/')+''';</script><script type="module" src="/training/experimental/browser_domain_guard_audit_page.mjs"></script></html>'''

def main(args):
    candidate=args.candidate.resolve();selection=json.loads((candidate/'validation.json').read_text('utf-8'))
    plan=json.loads((candidate/'protocol.json').read_text('utf-8'));digest=sha(candidate/'candidate.json')
    # Candidate bytes and validation freeze are authoritative. Historical tooling
    # digests inside older capture protocols may drift as work continues.
    if selection['candidateSha256']!=digest or not selection['parity']['predictionsIdentical'] or selection['deployed']:raise ValueError('Candidate not frozen/parity verified')
    if plan.get('auditOutcomesRead') or plan.get('testRead') or plan.get('productionDeploymentAllowed'):raise ValueError('Candidate protocol allows prohibited fitting/deployment')
    model=json.loads((candidate/'candidate.json').read_text('utf-8'))
    if model.get('featureVersion') not in ('browser-domain-recovery-v1','body-context-recovery-v1'):raise ValueError('Unsupported guard candidate feature version')
    if any(p['recoveryPolicies'] for p in model['modes'].values()):raise ValueError('This audit receiver requires rejection-only candidate')
    batch=args.batch.resolve();rows=json.loads((batch/'downloads.json').read_text('utf-8'));integrity=json.loads((batch/'video-integrity.json').read_text('utf-8'))
    if len(rows)<18 or any(not r['auditEligible'] or r['status']!='downloaded' for r in rows):raise ValueError('Verified unused originals required')
    if integrity['summary']['fullDecodePassed']!=len(rows) or integrity['summary'].get('predictionsRun'):raise ValueError('Unused originals must fully decode without predictions')
    if integrity['summary']['files']!=len(rows):raise ValueError('Video integrity does not cover the frozen downloads')
    # Their selection/download protocol was audit-only and predates fitting;
    # no recognizer has run on these originals. Never mix them into TRAIN/VAL.
    bp=json.loads((batch/'protocol.json').read_text('utf-8'))
    if bp['trainingAllowed'] or bp['calibrationAllowed'] or bp['predictionsRun']:raise ValueError('Contaminated online cohort')
    prior=json.loads((ROOT.parent/'hs-eval/online-worker-recognition-audit-20261108/protocol.json').read_text('utf-8'))

    out=args.out.resolve();out.relative_to((ROOT.parent/'hs-eval').resolve());out.mkdir(exist_ok=False)
    clips=[dict(r,file=f'guard-audit-{i:03}',sourceFile=r['member']) for i,r in enumerate(rows,1)]
    (out/'cohort.json').write_text(json.dumps(dict(clips=clips,purpose='independent-recording-audit-only'),indent=2)+'\n','utf-8')
    names=list(ASSETS)+['training/experimental/browser_domain_recovery.mjs','training/experimental/browser_domain_guard_audit_page.mjs',
        'training/experimental/prepared_tracker_factory.mjs','scripts/serve_manual_guard_browser.py',
        'training/ux/run_manual_guard_browser.mjs','scripts/freeze_browser_domain_guard_audit.py','training/test_browser_domain_guard_audit.py']
    frozen=dict(prior['frozenFilesSha256']);frozen.update({str(ROOT/n):sha(ROOT/n) for n in names})
    for n in ('protocol.json','candidate.json','validation.json'):frozen[str(candidate/n)]=sha(candidate/n)
    for n in ('protocol.json','downloads.json','frozen-selection.json','video-integrity.json'):frozen[str(batch/n)]=sha(batch/n)
    frozen.update({r['path']:r['sha256'] for r in rows});frozen[str(out/'cohort.json')]=sha(out/'cohort.json')
    refs=[dict(id=c['file'],label=c['label'],video='/__worker_clips__/'+c['file']+'.mp4',videoSha256=c['sha256']) for c in clips]
    allowed={'/'+n.replace('\\','/'):str(ROOT/n) for n in names};allowed.update({ref['video']:c['path'] for ref,c in zip(refs,clips)})
    allowed['/fixture.html']=str(out/'fixture.html');allowed['/__guard_model__.json']=str(candidate/'candidate.json')
    p=dict(schema=5,purpose='frozen-browser-independent-recording-guard-audit',cohort=str(out/'cohort.json'),frozenFilesSha256=frozen,
        productionStatus=prior['productionStatus'],classifierArtifactsSha256=prior['classifierArtifactsSha256'],
        candidate=str(candidate/'candidate.json'),candidateSha256=digest,manualModes=MANUAL_MODES,productionModes=prior['productionModes'],
        capture=prior['capture'],api=prior['api'],chromeExecutable=prior['chromeExecutable'],order=[c['file'] for c in clips],
        attemptsPerClip=1,noBestOfRetries=True,trainingAllowed=False,calibrationAllowed=False,deploymentAllowed=False,
        acceptance='Every correct baseline source must be retained. All wrong and unsupported accepts remain visible. No gate selection from this audit, regardless of result.',
        scope=f'{len(rows)} unused-recording PopSign v1 originals, known signer IDs. Cross-dataset people identity separation unverified. Not full198, new-signer or live-camera accuracy.',
        priorGuardAudit54FittingExcluded=True)
    (out/'protocol.json').write_text(json.dumps(p,indent=2)+'\n','utf-8')
    cfg=dict(items=refs,candidate=ASSETS[-1],guardModel='/__guard_model__.json',allowedFiles=allowed,token=secrets.token_urlsafe(32),protocolSha256=sha(out/'protocol.json'))
    cfg['fixtureSha256']=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()
    (out/'fixture.json').write_text(json.dumps(cfg,indent=2)+'\n','utf-8');(out/'fixture.html').write_text(render(cfg),'utf-8')
    print(f'Frozen {len(rows)}-original recording-new browser audit; candidate gates immutable; no recognition run yet.',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--batch',type=Path,required=True);p.add_argument('--out',type=Path,required=True);main(p.parse_args())
