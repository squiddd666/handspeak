"""Freeze the actual app's full-198 reference regression, not a fresh audit."""
import argparse,json,secrets
from pathlib import Path
from scripts.run_online_native_audit import ROOT,sha,verify
from scripts.prepare_online_motion_audit import write_new


def main(args):
    out=args.out.resolve();out.relative_to((ROOT.parent/'hs-eval').resolve());out.mkdir(exist_ok=False)
    prior=json.loads((ROOT.parent/'hs-eval/online-worker-recognition-audit-20261108/protocol.json').read_text('utf-8'));verify(prior)
    import torch,beginner_asl,capstone_asl_v3
    torch.set_num_threads(1);status=dict(beginner=beginner_asl.status(),capstone=capstone_asl_v3.status())
    if status!=prior['productionStatus']:raise ValueError('Actual loaded production models changed')
    catalog=json.loads((ROOT/'models/motion-vocabulary.json').read_text('utf-8'));by_id={r['id']:r for r in catalog['items']}
    manifest=json.loads((ROOT/'models/recognition-videos.json').read_text('utf-8'));items=[]
    for ref in manifest['items']:
        r=by_id[ref['id']]
        digest=sha(ROOT/r['video'])
        if r['video']!=ref['video'] or (ref.get('videoSha256') and digest!=ref['videoSha256']):raise ValueError('Reference identity mismatch')
        items.append({k:r[k] for k in ('id','label','video','recognition')}|dict(videoSha256=digest,
            recognitionModes=r.get('recognitionModes',[]),cameraGroups=r.get('cameraGroups',[])))
    if len(items)!=198 or len({r['id'] for r in items})!=198:raise ValueError('Full catalog coverage required')
    names=['scripts/freeze_full198_browser.py','scripts/serve_full198_browser.py','training/ux/run_full198_browser.mjs',
        'training/test_full198_browser.py','training/ux/motion_virtual_source.js','training/ux/motion_virtual_runner.js']
    assets=list(ROOT.glob('*.js'))+list(ROOT.glob('*.css'))+[ROOT/'favicon.svg',ROOT/'index.html']
    assets+=list((ROOT/'models').rglob('*.json'))+list((ROOT/'temporal-motion').glob('*.js'))
    assets+=list((ROOT/'media/avatar').rglob('*.json'))+[ROOT/r['video'] for r in items]
    frozen=dict(prior['frozenFilesSha256']);frozen.update({str(p):sha(p) for p in assets+[ROOT/n for n in names]})
    cfg=dict(width=960,height=720,items=items,indexSha256=sha(ROOT/'index.html'),bootstrapSha256=sha(ROOT/'training/ux/motion_virtual_source.js'),
        runnerSha256=sha(ROOT/'training/ux/motion_virtual_runner.js'),restartVirtualStreamEachReference=True,
        runtimeSha256={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in assets if p.suffix=='.js'},
        activeModelSha256={k:s['checkpointSha256'] for k,s in status.items()},
        activeAuxiliaryModelSha256={k:s['auxiliarySha256'] for k,s in status.items() if s.get('auxiliarySha256')},
        calibrationSha256=sha(ROOT/'models/motion-calibration.json'),
        auditCheckpoint=dict(endpoint='/__motion_audit__/checkpoint',token=secrets.token_urlsafe(32)))
    # This is transport-only audit instrumentation. Neither identity nor target
    # labels are added to the recognition payload, and responses are not replaced.
    transport='''
(() => {const original=window.fetch.bind(window);window.fetch=(input,init)=>{
  const u=new URL(typeof input==='string'?input:input.url,location.href),method=(init?.method||input?.method||'GET').toUpperCase();
  if(u.origin===location.origin&&method==='POST'&&['/api/beginner-asl','/api/capstone-asl','/api/research-words'].includes(u.pathname)){
    const id=JSON.parse(document.getElementById('vcReport').textContent).attempts.at(-1)?.id;
    const headers=new Headers(init?.headers);headers.set('X-Motion-Audit',window.HANDSPEAK_VIRTUAL_FIXTURE.auditCheckpoint.token);headers.set('X-Reference-ID',id||'');
    return original(input,{...init,headers});
  }return original(input,init);
};})();
'''
    code='\n<script>\nwindow.HANDSPEAK_VIRTUAL_FIXTURE = '+json.dumps(cfg)+';\n'
    code+=(ROOT/'training/ux/motion_virtual_source.js').read_text('utf-8').replace('</script','<\\/script')
    code+='\n'+transport+'\n'+(ROOT/'training/ux/motion_virtual_runner.js').read_text('utf-8').replace('</script','<\\/script')+'\n</script>\n'
    html=(ROOT/'index.html').read_bytes().replace(b'<head>',b'<head>'+code.encode('utf-8'),1)
    (out/'fixture.html').write_bytes(html);write_new(out/'fixture.json',cfg)
    frozen[str(out/'fixture.html')]=sha(out/'fixture.html');frozen[str(out/'fixture.json')]=sha(out/'fixture.json')
    allowed={'/'+str(p.relative_to(ROOT)).replace('\\','/'):str(p) for p in assets};allowed['/fixture.html']=str(out/'fixture.html')
    plan=dict(purpose='full-198-production-app-reference-regression-only',order=[r['id'] for r in items],frozenFilesSha256=frozen,
        allowedFiles=allowed,productionStatus=status,classifierArtifactsSha256=prior['classifierArtifactsSha256'],
        chromeExecutable=prior['chromeExecutable'],attemptsPerReference=1,rate=1,noBestOfRetries=True,
        trainingAllowed=False,calibrationAllowed=False,independentAccuracy=False,newSignerAudit=False,
        route='Actual Watch selector -> public Practice -> appropriate public Record control. No selected result or Add reviewed word clicks.',
        scoring='Report literal exact-label counts separately from the legacy fixture normalized display. Rejections/tracking failures retained.',
        scope='All 198 previously used Watch references, including synthetic greetings. Not independent real-world or unseen-signer evidence.')
    write_new(out/'protocol.json',plan);print('Frozen actual full-198 app regression; loaded checkpoint identity used, no predictions run.',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);main(p.parse_args())
