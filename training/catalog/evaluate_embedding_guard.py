"""Evaluate the predeclared guarded subset; never changes its selection or cutoffs."""
import argparse
import json
from pathlib import Path
import numpy as np
import torch
import evaluate_calibrated_candidate as candidate
import calibrate_word_thresholds as calibration
from train_embedding_guard import apply_guard
from motion_window import align_window
from body_tip_features import features
from train_motion_residual import MotionNet,batch
ROOT=Path('/opt/handspeak-training/vocabulary-expansion-embedding-guard')
REPORT=Path('/opt/handspeak/repository/reports/vocabulary-expansion/embedding-guard')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--ordinary',action='store_true');args=parser.parse_args()
    plan=json.loads((ROOT/'release-subset-plan.json').read_text());p=candidate.verify()
    if candidate.sha(ROOT/'guard.json')!=plan['guardSha256'] or p['checkpointSha256']!=plan['checkpointSha256'] or candidate.sha(Path(__file__).with_name('train_embedding_guard.py'))!=plan['guardImplementationSha256']:raise ValueError('Frozen guard changed')
    if candidate.sha(candidate.ROOT/'protocol.json')!=plan['sharedFreshProtocolSha256']:raise ValueError('Frozen shared selection changed')
    p=dict(p,labels=plan['labels']);guard=json.loads((ROOT/'guard.json').read_text())
    if args.ordinary:
        media=Path('/opt/handspeak-training/ordinary-movement-fresh22');frames=Path('/opt/handspeak-training/framing-ordinary-fresh22/frames');manifest=media/'manifest.json';scope='Regression on ordinary clips already scored by the unguarded candidate. Not a fresh independent ordinary-action result.';name='ordinary-regression'
    else:
        state=json.loads((candidate.ROOT/'job-status.json').read_text())
        if state['state']!='complete':raise ValueError('Shared extraction not complete')
        manifest=candidate.ROOT/'test-manifest.json';frames=candidate.ROOT/'frames';scope='Shared fresh recordings; guard and ten-label subset frozen before shared-model outcomes. Existing held-out signer pool, not new people or camera timing.';name='shared-fresh-signs'
    rows=json.loads(manifest.read_text());samples=[]
    for row in rows:
        r=json.loads((frames/(row['sha256']+'.json')).read_text())
        if any(r[k]!=row[k] for k in ['sha256','label','file','participant']) or candidate.sha(row['file'])!=row['sha256']:raise ValueError('Evaluation recording changed')
        samples.append(r)
    specification=dict(checkpointSha256=p['checkpointSha256'],guardSha256=plan['guardSha256'],releasePlanSha256=candidate.sha(ROOT/'release-subset-plan.json'),manifestSha256=candidate.sha(manifest),implementationSha256=candidate.sha(__file__),scope=scope,deployed=False)
    destination=ROOT/(name+'-protocol.json')
    if destination.exists():raise ValueError('Evaluation already frozen')
    candidate.write(destination,specification)
    saved=torch.load(candidate.ROOT/'frozen.pt',weights_only=True);net=MotionNet(len(p['outputLabels']),torch.zeros(175),torch.ones(175)).eval();net.load_state_dict(saved['states'][0]);torch.set_num_threads(1);captured=[]
    handle=net.head.register_forward_pre_hook(lambda module,args:captured.append(args[0].detach().numpy().copy()))
    inputs=torch.tensor(np.stack([features(align_window(dict(r,body=[None]*len(r['rawFrames'])))) for r in samples]))
    with torch.no_grad():probs=net(inputs).softmax(1).numpy()
    pred=apply_guard(calibration.predictions(samples,probs,p),captured[-1],guard);handle.remove()
    if args.ordinary:
        coverage={a:sum(r['action']==a and r['sequence'] is not None for r in samples) for a in sorted({r['action'] for r in samples})}
        result=dict(total=len(samples),falseSuggestions=sum(x is not None for x in pred),usablePerAction=coverage,passesScreen=not any(pred) and all(coverage.values()))
    else:
        metrics=candidate.base.metrics(samples,pred,p['labels']);result=dict(metrics=metrics,passesScreen=batch.trainer.gate(metrics))
    result.update(**specification,predictions=[dict(expected=r['label'],sha256=r['sha256'],predicted=v) for r,v in zip(samples,pred)])
    candidate.write(ROOT/(name+'.json'),result);candidate.write(REPORT/(name+'.json'),result);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
