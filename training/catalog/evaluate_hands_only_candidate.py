"""Freeze and evaluate a hands-only candidate on preselected recorded clips.

The shared clip selection is frozen separately; no predictions from the body
candidate are read. Neither checkpoint selection nor thresholds use test results.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time

import numpy as np
import torch
import body_tip_features
from motion_window import align_window
from train_motion_residual import MotionNet
import train_expansion_batch as batch


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_suffix('.partial')
    tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)


def predict(rows, checkpoint, protocol):
    saved=torch.load(checkpoint,weights_only=True)
    if saved['outputLabels']!=protocol['outputLabels']:
        raise ValueError('Output order changed')
    hands=[]
    for row in rows:
        clean=dict(row,body=[None]*len(row['rawFrames']))
        hands.append(align_window(clean))
    x=torch.tensor(np.stack([body_tip_features.features(r) for r in hands]))
    torch.set_num_threads(1)
    probabilities=[]
    for state in saved['states']:
        net=MotionNet(len(protocol['outputLabels']),torch.zeros(175),torch.ones(175)).eval()
        net.load_state_dict(state)
        with torch.no_grad():probabilities.append(net(x).softmax(1).numpy())
    output=[]
    for row,scores in zip(rows,np.mean(probabilities,axis=0)):
        order=np.argsort(scores)[::-1];winner,second=order[:2]
        label=protocol['outputLabels'][winner]
        output.append(label if row.get('sequence') is not None and label in protocol['labels']
                      and scores[winner]>=protocol['threshold']
                      and scores[winner]-scores[second]>=protocol['margin'] else None)
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--clips',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();out=args.output
    out.mkdir(parents=True,exist_ok=True)
    if (out/'protocol.json').exists():raise ValueError('Use a new frozen evaluation directory')
    base=json.loads((args.source/'protocol.json').read_text())
    if sha(base['source'])!=base['sourceSha256']:raise ValueError('Development source changed')
    clip_protocol=json.loads((args.clips/'protocol.json').read_text())
    if base['labels']!=clip_protocol['labels']:raise ValueError('Shared test targets differ')
    # Snapshot before opening any test manifest, cached features or predictions.
    shutil.copyfile(args.source/'motion-private.pt',out/'frozen.pt')
    saved=torch.load(out/'frozen.pt',weights_only=True)
    fine_tune_path=args.source/'fine-tune-protocol.json'
    if fine_tune_path.exists():
        fine_tune=json.loads(fine_tune_path.read_text())
        result=json.loads((args.source/'validation.json').read_text())
        if (fine_tune.get('featureMode')!='hands-only' or saved['selected'].get('seed')!=fine_tune['seed']
                or saved['selected'].get('epoch') not in fine_tune['validationEpochs']
                or result['checkpointSha256']!=sha(out/'frozen.pt')):
            raise ValueError('Fine-tuned checkpoint provenance mismatch')
        selection='Completed ordinary-rejection fine-tune; checkpoint and thresholds selected on development validation only'
    else:
        if saved['selected'].get('seed')!=17 or saved['selected'].get('epoch') not in (20,40,80):
            raise ValueError('Expected a checkpoint selected from the first completed seed')
        selection='First completed training seed; checkpoint and thresholds selected on development validation only'
    protocol=dict(labels=base['labels'],outputLabels=saved['outputLabels'],
                  threshold=saved['selected']['threshold'],margin=saved['selected']['margin'],
                  featureMode='hands-only',checkpointSha256=sha(out/'frozen.pt'),
                  developmentSha256=base['sourceSha256'],
                  sharedSelectionProtocolSha256=sha(args.clips/'protocol.json'),
                  selection=selection,
                  sourceFineTuneProtocolSha256=sha(fine_tune_path) if fine_tune_path.exists() else None,
                  scope='Reserved recordings used in parallel frozen-candidate comparisons; not new people or live camera accuracy',
                  deployed=False)
    files=[Path(__file__),Path(body_tip_features.__file__),
           Path(__file__).with_name('motion_window.py'),
           Path(__file__).with_name('train_motion_residual.py')]
    protocol['implementations']={str(p):sha(p) for p in files}
    data=json.loads(Path(base['source']).read_text())
    if any(any(p is not None for p in r['body']) for r in data):
        raise ValueError('Expected a body-free training source')
    val=[r for r in data if r['split']=='val'];del data
    batch.trainer.LABELS=protocol['labels']
    metrics=batch.trainer.metrics(val,predict(val,out/'frozen.pt',protocol))
    if metrics!=saved['selected']['validation'] or not batch.trainer.gate(metrics):
        raise ValueError('Hands-only development screen did not reproduce a pass')
    del val
    write(out/'protocol.json',protocol);write(args.report/'protocol.json',protocol)
    write(args.report/'development-screen.json',metrics)
    for p in files:shutil.copyfile(p,out/p.name)
    write(args.report/'job-status.json',dict(stage='waiting-for-shared-extraction',state='running',deployed=False))
    while True:
        state=json.loads((args.clips/'job-status.json').read_text())
        if state['state']=='failed':raise ValueError('Shared extraction failed')
        if state['state']=='complete':break
        time.sleep(5)
    if sha(args.clips/'protocol.json')!=protocol['sharedSelectionProtocolSha256']:
        raise ValueError('Shared selection changed')
    if any(sha(p)!=digest for p,digest in protocol['implementations'].items()):
        raise ValueError('Evaluation implementation changed')
    if sha(out/'frozen.pt')!=protocol['checkpointSha256']:
        raise ValueError('Frozen checkpoint changed')
    manifest=json.loads((args.clips/'test-manifest.json').read_text())
    samples=[];frame_hashes={}
    for row in manifest:
        if row['sha256'] in clip_protocol['knownHashes'] or str(row['participant']) in clip_protocol['excludedSigners']:
            raise ValueError('Known content or development signer entered fresh test')
        if sha(row['file'])!=row['sha256']:raise ValueError('Video content changed')
        path=args.clips/'frames'/(row['sha256']+'.json')
        sample=json.loads(path.read_text())
        if any(sample[k]!=row[k] for k in ('sha256','label','participant','file')):
            raise ValueError('Cached feature identity mismatch')
        samples.append(sample);frame_hashes[row['sha256']]=sha(path)
    predictions=predict(samples,out/'frozen.pt',protocol)
    metrics=batch.trainer.metrics(samples,predictions)
    result=dict(metrics=metrics,passesRecordedClipGate=batch.trainer.gate(metrics),
                checkpointSha256=protocol['checkpointSha256'],scope=protocol['scope'],
                manifestSha256=sha(args.clips/'test-manifest.json'),frameHashes=frame_hashes,
                predictions=[dict(expected=r['label'],sha256=r['sha256'],predicted=p)
                             for r,p in zip(samples,predictions)],deployed=False,readyForDeployment=False)
    write(out/'test-results.json',result);write(args.report/'test-results.json',result)
    write(args.report/'job-status.json',dict(stage='complete',state='complete',metrics=metrics,
          passesRecordedClipGate=result['passesRecordedClipGate'],deployed=False))
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
