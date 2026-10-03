"""Fit private DTW and compact temporal models, choosing on validation only."""
import sys,json,hashlib,itertools,argparse,copy
from pathlib import Path
import numpy as np
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'catalog'),str(Path(__file__).resolve().parents[1]/'accuracy'),str(Path(__file__).resolve().parents[1])]
import fit
import temporal as encoding
import torch
from torch import nn
ROOT=Path('/opt/handspeak-training/daily-words/citizen-research');fit.ROOT=ROOT
LABELS=['NAME','HOME','HAVE','WANT','LOVE'];OTHER='OTHER MOVEMENT'
torch.set_num_threads(2)
class Net(nn.Module):
 def __init__(self,width):
  super().__init__();self.net=nn.Sequential(nn.Conv1d(153,width,5,padding=2),nn.ReLU(),nn.Dropout(.15),nn.Conv1d(width,width,3,padding=1),nn.ReLU(),nn.AdaptiveAvgPool1d(1),nn.Flatten(),nn.Linear(width,6))
 def forward(self,x):return self.net(x)
def metrics(rows,out):
 m=fit.metrics(rows,out,LABELS)
 m['perWord']={l:{'total':sum(r['label']==l for r in rows),'correct':sum(r['label']==l and p==l for r,p in zip(rows,out))} for l in LABELS}
 return m
def gate(m):return m['correct']>=m['total']*.5 and m['wrong']==0 and m['negativeFalse']==0 and all(v['correct']>0 for v in m['perWord'].values())
def score(m):return (not gate(m),4*(m['wrong']+m['negativeFalse'])+m['missed'],-m['correct'],m['wrong']+m['negativeFalse'])
def outputs(rows,probs,threshold,margin):
 order=np.argsort(probs,axis=1);best=order[:,-1];gap=probs[np.arange(len(probs)),best]-probs[np.arange(len(probs)),order[:,-2]]
 return [LABELS[i] if i<5 and rows[n].get('sequence') is not None and probs[n,i]>=threshold and gap[n]>=margin else None for n,i in enumerate(best)]
def train_dtw(train,val):
 refs=[dict(label=r['label'] if r['label'] in LABELS else OTHER,sequence=r['sequence']) for r in train]
 mat=fit.matrix(val,refs,'citizen-validation');best=None
 for limit,ratio,votes in itertools.product([.15,.25,.35,.5,.65,.8,1.0],[1.1,1.3,1.5,2.0],[1,2,3]):
  p=dict(maxDistance=limit,minRatio=ratio,minVotes=votes,mirror=True,strongRatio=2.0)
  out=fit.outputs(mat,refs,p,LABELS);m=metrics(val,out)
  if best is None or score(m)<score(best['validation']):best=dict(parameters=p,validation=m)
 model=dict(version=1,encoding='two-hand-motion-v3',labels=LABELS,samples=refs,parameters=best['parameters'],status='private-research-only')
 path=ROOT/'dtw-private.json';path.write_text(json.dumps(model,separators=(',',':')))
 best.update(passesValidation=gate(best['validation']),sha256=hashlib.sha256(path.read_bytes()).hexdigest());(ROOT/'dtw-validation.json').write_text(json.dumps(best,indent=2));print('DTW result',json.dumps(best),flush=True)
def train_temporal(train,val):
 augmented=train+[encoding.mirrored(r) for r in train]
 x=torch.tensor(np.stack([encoding.features(r) for r in augmented]));vx=torch.tensor(np.stack([encoding.features(r) for r in val]));y=torch.tensor([LABELS.index(r['label']) if r['label'] in LABELS else 5 for r in augmented])
 weights=1/torch.bincount(y,minlength=6).float().clamp(min=1);weights/=weights.mean();best=None;trials=[]
 for seed,width in [(17,16),(29,32)]:
  torch.manual_seed(seed);net=Net(width);opt=torch.optim.AdamW(net.parameters(),lr=.003,weight_decay=.01)
  for epoch in range(1,121):
   net.train()
   for ids in torch.randperm(len(x)).split(32):
    batch=x[ids]+torch.randn_like(x[ids])*.01;opt.zero_grad();loss=nn.functional.cross_entropy(net(batch),y[ids],weight=weights);loss.backward();opt.step()
   if epoch not in [10,20,40,80,120]:continue
   net.eval()
   with torch.no_grad():probs=net(vx).softmax(1).numpy()
   for threshold,margin in itertools.product([.35,.5,.65,.8,.9,.97],[0,.1,.25,.4]):
    m=metrics(val,outputs(val,probs,threshold,margin));entry=dict(seed=seed,width=width,epoch=epoch,threshold=threshold,margin=margin,validation=m);trials.append(entry)
    if best is None or score(m)<score(best['validation']):
     best=entry;torch.save({'state':copy.deepcopy(net.state_dict()),'config':entry},ROOT/'temporal-private.pt')
   print('Temporal checkpoint',seed,epoch,'best',best['validation'],flush=True)
 best={**best,'passesValidation':gate(best['validation']),'sha256':hashlib.sha256((ROOT/'temporal-private.pt').read_bytes()).hexdigest()}
 (ROOT/'temporal-validation.json').write_text(json.dumps({'selected':best,'trials':trials},indent=2));print('Temporal result',json.dumps(best),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--model',choices=['dtw','temporal'],required=True);args=p.parse_args()
 data=json.loads((ROOT/'development-features.json').read_text());alltrain=[r for r in data if r['split']=='train'];val=[r for r in data if r['split']=='val'];train=[r for r in alltrain if r.get('sequence') is not None]
 assert not({r['participant'] for r in alltrain}&{r['participant'] for r in val});assert not({r['sha256'] for r in alltrain}&{r['sha256'] for r in val})
 coverage={'trainClips':len(alltrain),'usableTrainingClips':len(train),'validationClips':len(val),'validationWithUsableSequence':sum(r.get('sequence') is not None for r in val),'perWord':{l:{'train':sum(r['label']==l for r in alltrain),'usableTrain':sum(r['label']==l for r in train),'val':sum(r['label']==l for r in val)} for l in LABELS},'featureExtraction':'30 unique source frames; source timestamps; existing hand-quality gate; center-frame upper-body reference; tracking failures count as misses.','dataUse':'Private noncommercial research only; do not deploy raw videos, landmark templates, or checkpoints.'}
 (ROOT/'coverage.json').write_text(json.dumps(coverage,indent=2));print(json.dumps(coverage),flush=True)
 (train_dtw if args.model=='dtw' else train_temporal)(train,val)
