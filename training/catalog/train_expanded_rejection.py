"""Expand the frozen hands-only rejection model to 50 development target labels."""
import copy
import hashlib
import json
from pathlib import Path
import numpy as np
import torch
from torch import nn
import body_tip_features
import train_expansion_batch as batch
from train_motion_residual import MotionNet, augmented_batch, class_weights, select

BASE=Path('/opt/handspeak-training/vocabulary-expansion-ordinary-rejection-test')
SOURCE=Path('/opt/handspeak-training/vocabulary-expansion-ordinary-source')
ROOT=Path('/opt/handspeak-training/vocabulary-expansion-expanded-rejection')
REPORT=Path('/opt/handspeak/repository/reports/vocabulary-expansion/expanded-rejection')


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.partial');temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(path)


def main():
    if (ROOT/'fine-tune-protocol.json').exists():raise ValueError('Do not overwrite a frozen experiment')
    p=json.loads((BASE/'protocol.json').read_text())
    source=json.loads((SOURCE/'protocol.json').read_text())
    if digest(BASE/'frozen.pt')!=p['checkpointSha256'] or digest(source['source'])!=source['sourceSha256']:
        raise ValueError('Frozen source changed')
    target_protocol=json.loads(Path('/opt/handspeak-training/vocabulary-expansion-priority-data-v2/protocol.json').read_text())
    parent_labels=list(p['labels']);p['labels']=target_protocol['labels']
    if len(p['labels'])!=50 or not set(parent_labels)<=set(p['labels']):raise ValueError('Unexpected expanded target set')
    torch.set_num_threads(2);torch.manual_seed(83)
    train,val=batch.prepare(Path(source['source']),ROOT,labels=p['labels'],separate_negatives=True)
    protocol=json.loads((ROOT/'protocol.json').read_text())
    labels=protocol['outputLabels'];batch.trainer.LABELS=p['labels']
    old=torch.load(BASE/'frozen.pt',weights_only=True)
    if len(old['states'])!=1:raise ValueError('Expected single source model')
    state=old['states'][0]
    net=MotionNet(len(labels),state['mean'].flatten(),state['scale'].flatten())
    updated=net.state_dict()
    for key,value in state.items():
        if not key.startswith('head.'):updated[key]=value.clone()
    updated['head.1.weight'].zero_();updated['head.1.bias'].fill_(-4)
    for i,label in enumerate(old['outputLabels']):
        j=labels.index(label)
        updated['head.1.weight'][j]=state['head.1.weight'][i]
        updated['head.1.bias'][j]=state['head.1.bias'][i]
    net.load_state_dict(updated)
    specification=dict(parentCheckpointSha256=p['checkpointSha256'],sourceSha256=source['sourceSha256'],
        featureMode='hands-only',parentReleaseLabels=parent_labels,expandedTargetLabels=p['labels'],epochs=40,validationEpochs=[10,20,40],seed=83,
        learningRate=.0002,weightDecay=.02,targetLossMultiplier=2,labelSmoothing=.05,
        normalization='Preserve parent training normalization',
        selection='Development validation only. Do not use recorded test outcomes for checkpoint or threshold selection.',
        ordinaryGrouping='Recording groups, not verified unique persons',deployed=False)
    dependencies=[Path(__file__),Path(body_tip_features.__file__),Path(batch.__file__),
                  Path(__file__).with_name('train_motion_residual.py')]
    specification['implementations']={str(f):digest(f) for f in dependencies}
    write(ROOT/'fine-tune-protocol.json',specification)
    for f in dependencies:(ROOT/f.name).write_bytes(f.read_bytes())
    write(ROOT/'motion-protocol.json',dict(featureEncoding='body-tips-v1',featureMode='hands-only',featureImplementationSha256=digest(body_tip_features.__file__)))
    def status(stage,**extra):
        for directory in (ROOT,REPORT):write(directory/'job-status.json',dict(stage=stage,deployed=False,**extra))
    status('training',state='running')
    augmented=train+[batch.trainer.encoding.mirrored(r) for r in train]
    x=torch.tensor(np.stack([body_tip_features.features(r) for r in augmented]))
    vx=torch.tensor(np.stack([body_tip_features.features(r) for r in val]))
    y=torch.tensor([labels.index(r['label']) for r in augmented])
    weights=class_weights(y,len(labels),len(p['labels']),2)
    optimizer=torch.optim.AdamW(net.parameters(),lr=.0002,weight_decay=.02)
    best=None;trials=[]
    for epoch in range(1,41):
        net.train()
        for ids in torch.randperm(len(x)).split(64):
            optimizer.zero_grad()
            loss=nn.functional.cross_entropy(net(augmented_batch(x[ids],masked=True)),y[ids],weight=weights,label_smoothing=.05)
            loss.backward();nn.utils.clip_grad_norm_(net.parameters(),5);optimizer.step()
        if epoch not in (10,20,40):continue
        net.eval()
        with torch.no_grad():probs=net(vx).softmax(1).numpy()
        result=dict(epoch=epoch,seed=83,members=1,**select(val,probs));trials.append(result)
        if best is None or batch.trainer.score(result['validation'])<batch.trainer.score(best['validation']):
            best=copy.deepcopy(result)
            torch.save(dict(states=[copy.deepcopy(net.state_dict())],selected=best,outputLabels=labels),ROOT/'motion-private.pt')
        status('training',state='running',epoch=epoch,validation=result['validation'])
        print(json.dumps(result),flush=True)
    saved=torch.load(ROOT/'motion-private.pt',weights_only=True);net.load_state_dict(saved['states'][0]);net.eval()
    with torch.no_grad():probs=net(vx).softmax(1).numpy()
    predictions=batch.trainer.outputs(val,probs,best['threshold'],best['margin'])
    if batch.trainer.metrics(val,predictions)!=best['validation']:raise ValueError('Reload mismatch')
    if any(digest(path)!=sha for path,sha in specification['implementations'].items()):raise ValueError('Implementation changed')
    result=dict(selected=best,trials=trials,passesValidation=batch.trainer.gate(best['validation']),
        checkpointReloadVerified=True,checkpointSha256=digest(ROOT/'motion-private.pt'),
        sourceSha256=source['sourceSha256'],deployed=False,
        errors=[dict(expected=r['label'],predicted=v,sha256=r['sha256']) for r,v in zip(val,predictions)
                if (r['label'] in p['labels'] and v!=r['label']) or (r['label'] not in p['labels'] and v is not None)])
    for directory in (ROOT,REPORT):write(directory/'validation.json',result)
    status('complete',state='complete',passesValidation=result['passesValidation'],validation=best['validation'])


if __name__=='__main__':main()
