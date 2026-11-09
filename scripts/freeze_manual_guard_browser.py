"""Freeze a metadata-only 34-clip train/val browser development check."""
import argparse,hashlib,json,secrets
from pathlib import Path
from scripts.run_online_native_audit import ROOT,sha,verify
from scripts.freeze_online_worker_audit import ASSETS,MANUAL_MODES
from scripts.train_manual_open_set_guard import verify_dev


def main(args):
    out=args.out.resolve();out.relative_to((ROOT.parent/'hs-eval').resolve());out.mkdir(exist_ok=False)
    candidate_folder=args.candidate.resolve();selection=json.loads((candidate_folder/'validation.json').read_text('utf-8'))
    parity=json.loads((candidate_folder/'runtime-parity.json').read_text('utf-8'))
    if not parity['refinedPredictionsIdentical'] or sha(candidate_folder/'candidate.json')!=selection['modelSha256']:raise ValueError('Unfrozen/unverified guard candidate')
    class_plan=json.loads((candidate_folder/'protocol.json').read_text('utf-8'));base=Path(class_plan['base'])
    development=json.loads((base/'protocol.json').read_text('utf-8'));verify_dev(development)
    sources=json.loads((base/'source-manifest.json').read_text('utf-8'))
    labels=set().union(*map(set,MANUAL_MODES.values()));chosen=[]
    # No native prediction/feature-health values influence source selection.
    for label in sorted(labels):
        pool=[r for r in sources if r['split']=='val' and r['label']==label]
        if not pool:raise ValueError('Missing validation word')
        chosen.append(min(pool,key=lambda r:r['file']))
    other_labels=sorted({r['label'] for r in sources if r['split']=='val' and r['label'] not in labels})[:6]
    for label in other_labels:chosen.append(min([r for r in sources if r['split']=='val' and r['label']==label],key=lambda r:r['file']))
    for label in ['HELLO','WATER','HAVE','FISH']:
        chosen.append(min([r for r in sources if r['split']=='train' and r['label']==label],key=lambda r:r['file']))
    clips=[dict(r,sourceFile=r['file'],file=f'dev-{i:03}',split=r['split']) for i,r in enumerate(chosen,1)]
    with (out/'cohort.json').open('x',encoding='utf-8') as f:json.dump(dict(clips=clips,purpose='browser-development-only'),f,indent=2)
    old=json.loads((ROOT.parent/'hs-eval/online-worker-recognition-audit-20261108/protocol.json').read_text('utf-8'));verify(old)
    frozen=dict(old['frozenFilesSha256'])
    names=list(ASSETS)+['training/experimental/manual_open_set_guard_v2.mjs','training/experimental/manual_guard_browser_page.mjs',
        'training/ux/run_manual_guard_browser.mjs','scripts/serve_manual_guard_browser.py','scripts/freeze_manual_guard_browser.py',
        'training/test_manual_guard_browser.py','training/experimental/prepared_tracker_factory.mjs',
        'training/test_prepared_tracker_factory.mjs']
    frozen.update({str(ROOT/n):sha(ROOT/n) for n in names});frozen.update({c['path']:c['sha256'] for c in clips})
    frozen[str(out/'cohort.json')]=sha(out/'cohort.json')
    for n in ('candidate.json','protocol.json','validation.json','runtime-parity.json'):frozen[str(candidate_folder/n)]=sha(candidate_folder/n)
    p=dict(schema=5,purpose='frozen-browser-development-only',cohort=str(out/'cohort.json'),frozenFilesSha256=frozen,
        productionStatus=old['productionStatus'],classifierArtifactsSha256=old['classifierArtifactsSha256'],
        candidate=str(candidate_folder/'candidate.json'),candidateSha256=selection['modelSha256'],manualModes=MANUAL_MODES,
        productionModes=old['productionModes'],capture=old['capture'],api=old['api'],chromeExecutable=old['chromeExecutable'],
        order=[c['file'] for c in clips],attemptsPerClip=1,noBestOfRetries=True,trainingAllowed=False,calibrationAllowed=False,deploymentAllowed=False,
        selection='One first-filename validation source per 24 canonical manual words, first six nonmanual validation labels, plus four fixed training-word infrastructure fixtures. Metadata only.',
        sourceMapping='ASL Citizen original glossary preserved as gloss; predeclared manual aliases preserved as label. No related PopSign label substitutions.',
        scope='Same-source browser baseline/candidate development check, not fresh test/new signers or full-198. No gate adjustment from these captures.')
    with (out/'protocol.json').open('x',encoding='utf-8') as f:json.dump(p,f,indent=2)
    refs=[dict(id=c['file'],label=c['label'],video='/__worker_clips__/'+c['file']+'.mp4',videoSha256=c['sha256']) for c in clips]
    allowed={'/'+n.replace('\\','/'):str(ROOT/n) for n in names};allowed.update({r['video']:c['path'] for r,c in zip(refs,clips)})
    allowed['/fixture.html']=str(out/'fixture.html');allowed['/__guard_model__.json']=str(candidate_folder/'candidate.json')
    cfg=dict(items=refs,candidate=ASSETS[-1],guardModel='/__guard_model__.json',allowedFiles=allowed,token=secrets.token_urlsafe(32),protocolSha256=sha(out/'protocol.json'))
    cfg['fixtureSha256']=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()
    with (out/'fixture.json').open('x',encoding='utf-8') as f:json.dump(cfg,f,indent=2)
    html=render_fixture(cfg)
    with (out/'fixture.html').open('x',encoding='utf-8') as f:f.write(html)
    print('Frozen 34-clip browser development plan; no images predicted and no model changes.')


def render_fixture(cfg):
    # Never transform an embedded JSON object with global text replacements:
    # allowedFiles is an exact allowlist and must survive HTML rendering intact.
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><title>Frozen rejection-candidate browser development</title>
<style>body{font:15px system-ui;background:#142024;color:#eee;padding:20px}video,canvas{width:240px;height:180px}button{padding:10px}pre{max-height:250px;overflow:auto}</style>
<h1>Frozen rejection-candidate browser development</h1><p>34 train/validation originals. Identical captures for baseline and guard. Not an independent, new-signer or full-198 audit.</p>
<video id="source" muted playsinline controls></video><canvas id="virtualCanvas" width="960" height="720"></canvas><video id="virtualCamera" muted playsinline></video>
<select id="reference"></select><button id="arm">Arm</button><button id="record" disabled>Record</button><button id="cancel" disabled>Cancel</button><button id="blank">Blank</button>
<button id="batch">Run frozen one-pass batch</button><button id="stop">Stop</button>
<p id="status">Loading infrastructure without images…</p><p id="summary"></p><p id="saved"></p><p id="batchStatus"></p><pre id="ledger"></pre>
<script>window.DUAL_CAPTURE_FIXTURE = '''+json.dumps(cfg).replace('</','<\\/')+''';</script><script type="module" src="/training/experimental/manual_guard_browser_page.mjs"></script></html>'''


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--candidate',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);main(parser.parse_args())
