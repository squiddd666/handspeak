"""Improve framing robustness using development-only scale augmentation."""
import copy
import itertools
import camera_framing
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
ROOT=Path('/opt/handspeak-training/vocabulary-expansion-framing-rejection')
REPORT=Path('/opt/handspeak/repository/reports/vocabulary-expansion/framing-rejection')


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
    torch.set_num_threads(2);torch.manual_seed(97)
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
        featureMode='hands-only',epochs=20,validationEpochs=[5,10,20],seed=97,
        learningRate=.0002,weightDecay=.02,targetLossMultiplier=2,labelSmoothing=.05,
        normalization='Preserve parent training normalization',
        framingScales=[1,.5625,1.3],framingScope='Scaled development landmarks, not fresh detector or independent camera accuracy',
        selection='Development validation only. Do not use recorded test outcomes for checkpoint or threshold selection.',
        ordinaryGrouping='Recording groups, not verified unique persons',deployed=False)
    dependencies=[Path(__file__),Path(camera_framing.__file__),Path(body_tip_features.__file__),Path(batch.__file__),
                  Path(__file__).with_name('train_motion_residual.py')]
    specification['implementations']={str(f):digest(f) for f in dependencies}
    write(ROOT/'fine-tune-protocol.json',specification)
    for f in dependencies:(ROOT/f.name).write_bytes(f.read_bytes())
    write(ROOT/'motion-protocol.json',dict(featureEncoding='body-tips-v1',featureMode='hands-only',featureImplementationSha256=digest(body_tip_features.__file__)))
    def status(stage,**extra):
        for directory in (ROOT,REPORT):write(directory/'job-status.json',dict(stage=stage,deployed=False,**extra))
    status('training',state='running')
    scales=[1,.5625,1.3]
    vectors=[];targets=[]
    for factor in scales:
        for row in train:
            framed=camera_framing.scaled(row,factor)
            for example in (framed,batch.trainer.encoding.mirrored(framed)):
                vectors.append(body_tip_features.features(example));targets.append(labels.index(row['label']))
    x=torch.tensor(np.stack(vectors));del vectors
    y=torch.tensor(targets)
    vx=torch.tensor(np.stack([body_tip_features.features(camera_framing.scaled(row,factor)) for factor in scales for row in val]))
    def framing_select(probabilities):
        chosen=None
        for threshold,margin in itertools.product([.35,.5,.65,.8,.9,.95,.98],[0,.15,.3,.45]):
            by_scale=[]
            for i,factor in enumerate(scales):
                predictions=batch.trainer.outputs(val,probabilities[i*len(val):(i+1)*len(val)],threshold,margin)
                by_scale.append(dict(scale=factor,metrics=batch.trainer.metrics(val,predictions)))
            combined=batch.trainer.metrics(val*len(scales),batch.trainer.outputs(val*len(scales),probabilities,threshold,margin))
            key=(not all(batch.trainer.gate(item['metrics']) for item in by_scale),*batch.trainer.score(combined)[1:])
            entry=dict(threshold=threshold,margin=margin,validation=by_scale[0]['metrics'],framingValidation=by_scale,selectionScore=key)
            if chosen is None or key<chosen['selectionScore']:chosen=entry
        return chosen
    weights=class_weights(y,len(labels),len(p['labels']),2)
    optimizer=torch.optim.AdamW(net.parameters(),lr=.0002,weight_decay=.02)
    best=None;trials=[]
    for epoch in range(1,21):
        net.train()
        for ids in torch.randperm(len(x)).split(64):
            optimizer.zero_grad()
            loss=nn.functional.cross_entropy(net(augmented_batch(x[ids],masked=True)),y[ids],weight=weights,label_smoothing=.05)
            loss.backward();nn.utils.clip_grad_norm_(net.parameters(),5);optimizer.step()
        if epoch not in (5,10,20):continue
        net.eval()
        with torch.no_grad():probs=net(vx).softmax(1).numpy()
        result=dict(epoch=epoch,seed=97,members=1,**framing_select(probs));trials.append(result)
        if best is None or tuple(result['selectionScore'])<tuple(best['selectionScore']):
            best=copy.deepcopy(result)
            torch.save(dict(states=[copy.deepcopy(net.state_dict())],selected=best,outputLabels=labels),ROOT/'motion-private.pt')
        status('training',state='running',epoch=epoch,validation=result['validation'],framingValidation=result['framingValidation'])
        print(json.dumps(result),flush=True)
    saved=torch.load(ROOT/'motion-private.pt',weights_only=True);net.load_state_dict(saved['states'][0]);net.eval()
    with torch.no_grad():probs=net(vx).softmax(1).numpy()
    predictions=batch.trainer.outputs(val,probs[:len(val)],best['threshold'],best['margin'])
    if batch.trainer.metrics(val,predictions)!=best['validation'] or framing_select(probs)['framingValidation']!=best['framingValidation']:raise ValueError('Reload mismatch')
    if any(digest(path)!=sha for path,sha in specification['implementations'].items()):raise ValueError('Implementation changed')
    result=dict(selected=best,trials=trials,passesValidation=all(batch.trainer.gate(item['metrics']) for item in best['framingValidation']),
        checkpointReloadVerified=True,checkpointSha256=digest(ROOT/'motion-private.pt'),
        sourceSha256=source['sourceSha256'],deployed=False,
        errors=[dict(expected=r['label'],predicted=v,sha256=r['sha256']) for r,v in zip(val,predictions)
                if (r['label'] in p['labels'] and v!=r['label']) or (r['label'] not in p['labels'] and v is not None)])
    for directory in (ROOT,REPORT):write(directory/'validation.json',result)
    status('complete',state='complete',passesValidation=result['passesValidation'],validation=best['validation'])


if __name__=='__main__':main()
