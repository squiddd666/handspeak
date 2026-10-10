"""Train a fixed embedding-distance rejection guard, using development data only."""
import copy
import json
from pathlib import Path
import numpy as np
import torch
from camera_framing import scaled
from body_tip_features import features
from train_motion_residual import MotionNet
import train_expansion_batch as batch
import calibrate_word_thresholds as calibration
ROOT=Path('/opt/handspeak-training/vocabulary-expansion-embedding-guard')
SOURCE=Path('/opt/handspeak-training/vocabulary-expansion-framing-calibrated')
REPORT=Path('/opt/handspeak/repository/reports/vocabulary-expansion/embedding-guard')
sha=calibration.sha;write=calibration.write

def distances(embedding,centers):
    return ((embedding[:,None,:]-centers[None,:,:])**2).mean(2)

def cluster(values,count=8):
    selected=[int(np.argmin(((values-values.mean(0))**2).sum(1)))];centers=[values[selected[0]]]
    while len(centers)<min(count,len(values)):
        best=int(np.argmax(distances(values,np.stack(centers)).min(1)))
        if best in selected:break
        selected.append(best);centers.append(values[best])
    centers=np.stack(centers)
    for _ in range(20):
        assignment=distances(values,centers).argmin(1)
        updated=np.stack([values[assignment==i].mean(0) if np.any(assignment==i) else c for i,c in enumerate(centers)])
        if np.allclose(updated,centers,atol=1e-6):break
        centers=updated
    return centers

def apply_guard(base_predictions,embeddings,guard):
    normalized=(embeddings-np.array(guard['mean']))/np.array(guard['scale'])
    centers=np.array(guard['centers']);labels=guard['centerLabels'];d=distances(normalized,centers);out=[]
    for label,values in zip(base_predictions,d):
        if label is None:out.append(None);continue
        winner=int(values.argmin())
        own=float(min(v for v,l in zip(values,labels) if l==label))
        out.append(label if labels[winner]==label and own<=guard['radiusByLabel'][label] else None)
    return out

def main():
    if (ROOT/'plan.json').exists():raise ValueError('Use a new guard experiment directory')
    p=json.loads((SOURCE/'protocol.json').read_text())
    if sha(SOURCE/'frozen.pt')!=p['checkpointSha256'] or sha(p['source'])!=p['sourceSha256']:raise ValueError('Frozen inputs changed')
    plan=dict(checkpointSha256=p['checkpointSha256'],developmentSha256=p['sourceSha256'],scales=[1,.5625,1.3],clustersPerOutput=8,radiusTrainingQuantile=.99,rule='Keep a calibrated suggestion only if its closest standardized training embedding centroid has the same label and its own-class distance is within that class training 99th percentile. No fallback or cutoff relaxation.',implementationSha256=sha(__file__),selection='Fixed before this experiment; development screen only; no test predictions opened',deployed=False)
    write(ROOT/'plan.json',plan)
    data=json.loads(Path(p['source']).read_text());train=[r for r in data if r['split']=='train' and r['sequence'] is not None];val=[r for r in data if r['split']=='val'];del data
    torch.set_num_threads(1);saved=torch.load(SOURCE/'frozen.pt',weights_only=True);net=MotionNet(len(p['outputLabels']),torch.zeros(175),torch.ones(175)).eval();net.load_state_dict(saved['states'][0]);captured=[]
    handle=net.head.register_forward_pre_hook(lambda module,args:captured.append(args[0].detach().numpy().copy()))
    def infer(rows):
        inputs=torch.tensor(np.stack([features(r) for r in rows]));captured.clear()
        with torch.no_grad():prob=net(inputs).softmax(1).numpy()
        return prob,captured[-1]
    train_embeddings=[];train_labels=[];buffer=[]
    for factor in plan['scales']:
        for row in train:
            framed=scaled(row,factor)
            for example in (framed,batch.trainer.encoding.mirrored(framed)):
                buffer.append(example);train_labels.append(row['label'])
                if len(buffer)>=64:
                    train_embeddings.append(infer(buffer)[1]);buffer=[]
    if buffer:train_embeddings.append(infer(buffer)[1])
    embeddings=np.concatenate(train_embeddings);mean=embeddings.mean(0);scale=embeddings.std(0).clip(.05);normalized=(embeddings-mean)/scale
    centers=[];center_labels=[];radii={};train_labels=np.array(train_labels)
    for label in p['outputLabels']:
        values=normalized[train_labels==label]
        if not len(values):raise ValueError('Missing training class')
        c=cluster(values);centers.extend(c.tolist());center_labels.extend([label]*len(c));radii[label]=max(1e-6,float(np.quantile(distances(values,c).min(1),.99)))
    guard=dict(checkpointSha256=p['checkpointSha256'],mean=mean.tolist(),scale=scale.tolist(),centers=centers,centerLabels=center_labels,radiusByLabel=radii)
    write(ROOT/'guard.json',guard);batch.trainer.LABELS=p['labels'];screens=[]
    for factor in plan['scales']:
        rows=[scaled(r,factor) for r in val];probs,emb=infer(rows);baseline=calibration.predictions(rows,probs,p);pred=apply_guard(baseline,emb,guard)
        if any(v is not None and v!=b for v,b in zip(pred,baseline)):raise ValueError('Guard invented a suggestion')
        screens.append(dict(scale=factor,metrics=batch.trainer.metrics(rows,pred),baselineMetrics=batch.trainer.metrics(rows,baseline)))
    handle.remove();result=dict(passesDevelopmentScreen=all(batch.trainer.gate(r['metrics']) for r in screens),framingValidation=screens,guardSha256=sha(ROOT/'guard.json'),checkpointSha256=p['checkpointSha256'],deployed=False)
    write(ROOT/'validation.json',result);write(REPORT/'validation.json',result);write(REPORT/'plan.json',plan);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
