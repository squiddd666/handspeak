"""Screen ensemble agreement and a separately trained rejection guard on development data.

No retraining, test access, threshold relaxation, or deployment. Validation is
already used for selection and cannot establish independent accuracy.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import numpy as np
import torch
from train_motion_residual import MotionNet, batch
import body_tip_features


def read_development(protocol):
    source=Path(protocol['source'])
    if hashlib.sha256(source.read_bytes()).hexdigest()!=protocol['sourceSha256']:
        raise ValueError('Frozen source changed')
    rows=json.loads(source.read_text())
    if any(r['split'] not in ('train','val') for r in rows):
        raise ValueError('Only development data may be opened')
    return [r for r in rows if r['split']=='val']


def guarded_outputs(rows, members, guard, threshold, margin, minimum_votes, use_guard):
    average=members.mean(0)
    out=batch.trainer.outputs(rows,average,threshold,margin)
    winners=np.argsort(average,axis=1)[:,-1]
    votes=(np.argsort(members,axis=2)[:,:,-1]==winners[None,:]).sum(0)
    rejected=np.argsort(guard,axis=1)[:,-1]>=len(batch.trainer.LABELS)
    return [p if votes[i]>=minimum_votes and not (use_guard and rejected[i]) else None
            for i,p in enumerate(out)]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment',type=Path,required=True)
    parser.add_argument('--guard',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    protocol=json.loads((args.experiment/'protocol.json').read_text())
    guard_protocol=json.loads((args.guard/'protocol.json').read_text())
    selected=json.loads((args.experiment/'validation.json').read_text())
    guard_selected=json.loads((args.guard/'temporal-validation.json').read_text())['selected']
    if protocol['labels']!=guard_protocol['labels']:
        raise ValueError('Supported class order differs')
    checkpoint=args.experiment/'motion-private.pt';guard_checkpoint=args.guard/'temporal-private.pt'
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=selected['checkpointSha256'] or hashlib.sha256(guard_checkpoint.read_bytes()).hexdigest()!=guard_selected['sha256']:
        raise ValueError('Frozen checkpoint changed')
    frozen=dict(candidateSha256=selected['checkpointSha256'],guardSha256=guard_selected['sha256'],
                candidateSourceSha256=protocol['sourceSha256'],guardSourceSha256=guard_protocol['sourceSha256'],
                thresholds=[.35,.5,.65,.8,.9,.97],margins=[0,.1,.25,.4],
                rule='Require selected count of member argmax votes for the averaged winner. Optional guard vetoes any global winning rejection class, without fallback.',
                implementationSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                deployed=False,independentTest=False,gate=protocol['validationGate'])
    args.output.mkdir(parents=True,exist_ok=True)
    path=args.output/'consensus-protocol.json'
    if path.exists() and json.loads(path.read_text())!=frozen:raise ValueError('Protocol changed')
    path.write_text(json.dumps(frozen,indent=2)+'\n')
    rows=read_development(protocol);guard_rows=read_development(guard_protocol)
    lookup={r['sha256']:r for r in guard_rows}
    if len(lookup)!=len(rows) or {r['sha256'] for r in rows}!=set(lookup):raise ValueError('Development recordings differ')
    guard_rows=[lookup[r['sha256']] for r in rows]
    if any((r['label'],r['participant'],r.get('sequence') is None)!=(g['label'],g['participant'],g.get('sequence') is None) for r,g in zip(rows,guard_rows)):
        raise ValueError('Development labels, signers or quality decisions differ')
    saved=torch.load(checkpoint,weights_only=True)
    if saved['outputLabels']!=protocol['outputLabels']:raise ValueError('Candidate output order changed')
    motion_protocol=json.loads((args.experiment/'motion-protocol.json').read_text())
    encoding=motion_protocol.get('featureEncoding','legacy')
    if encoding not in ('legacy','body-tips-v1'):raise ValueError('Unknown feature encoding')
    if encoding=='body-tips-v1' and hashlib.sha256(Path(body_tip_features.__file__).read_bytes()).hexdigest()!=motion_protocol['featureImplementationSha256']:
        raise ValueError('Frozen feature encoder changed')
    feature_fn=body_tip_features.features if encoding=='body-tips-v1' else batch.trainer.encoding.features
    x=torch.tensor(np.stack([feature_fn(r) for r in rows]));members=[]
    torch.set_num_threads(2);batch.trainer.LABELS=protocol['labels']
    for state in saved['states']:
        net=MotionNet(len(saved['outputLabels']),torch.zeros(x.shape[1]),torch.ones(x.shape[1])).eval()
        net.load_state_dict(state)
        with torch.no_grad():members.append(net(x).softmax(1).numpy())
    members=np.array(members)
    reference=selected['selected']
    if batch.trainer.metrics(rows,batch.trainer.outputs(rows,members.mean(0),reference['threshold'],reference['margin']))!=reference['validation']:
        raise ValueError('Candidate baseline could not be reproduced')
    net=batch.trainer.Net(guard_selected['width'],len(batch.model_outputs(guard_protocol,guard_selected)),guard_protocol.get('temporalBins',1)).eval()
    net.load_state_dict(torch.load(guard_checkpoint,weights_only=True)['state'])
    with torch.no_grad():guard=net(torch.tensor(np.stack([batch.trainer.encoding.features(r) for r in guard_rows]))).softmax(1).numpy()
    if batch.trainer.metrics(guard_rows,batch.trainer.outputs(guard_rows,guard,guard_selected['threshold'],guard_selected['margin']))!=guard_selected['validation']:
        raise ValueError('Guard baseline could not be reproduced')
    best=None;trials=[]
    for threshold,margin,votes,use_guard in itertools.product(frozen['thresholds'],frozen['margins'],range(1,len(members)+1),(False,True)):
        predictions=guarded_outputs(rows,members,guard,threshold,margin,votes,use_guard)
        metrics=batch.trainer.metrics(rows,predictions)
        entry=dict(threshold=threshold,margin=margin,minimumVotes=votes,useGuard=use_guard,validation=metrics)
        trials.append(entry)
        if best is None or batch.trainer.score(metrics)<batch.trainer.score(best['validation']):best=entry
    result=dict(selected=best,passesValidation=batch.trainer.gate(best['validation']),trials=trials,
                candidateReloadVerified=True,guardReloadVerified=True,protocol=frozen,
                independentAccuracyPassed=False,deployed=False)
    (args.output/'consensus-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(parameters={k:v for k,v in best.items() if k!='validation'},
                         metrics={k:v for k,v in best['validation'].items() if k!='perWord'},
                         zeroCorrect=[k for k,v in best['validation']['perWord'].items() if not v['correct']],
                         passesValidation=result['passesValidation'])),flush=True)


if __name__=='__main__':main()
