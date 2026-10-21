"""Evaluate fixed equal-weight CAPSTONE100 ensembles on validation."""
from __future__ import annotations
import csv, hashlib, json, sys
from pathlib import Path
import numpy as np
import torch
from torch.utils.data import DataLoader

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/"third_party/capstone_asl"))
sys.path.insert(0,str(Path(__file__).parent))
import pipeline
from train_citizen_capstone100 import Sequences, collate

ROOT=Path("/opt/handspeak-training/capstone100-retrain")
CHECKPOINTS=[
 ROOT/"recognition_tcn_attention_candidate_full-highres-baseline.pt",
 ROOT/"recognition_tcn_attention_candidate_full-highres-s17.pt",
]
DEVICE=torch.device("cpu")

def score(y,p):
 pred=p.argmax(1); top1=float(np.mean(pred==y))
 top5=float(np.mean([a in row for a,row in zip(y,np.argpartition(p,-5,axis=1)[:,-5:])]))
 f1=[]
 for c in range(100):
  tp=np.sum((y==c)&(pred==c)); fp=np.sum((y!=c)&(pred==c)); fn=np.sum((y==c)&(pred!=c))
  f1.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0)
 return {"top1":top1,"top5":top5,"macro_f1":float(np.mean(f1))}

def main():
 protocol=hashlib.sha256((ROOT/"extraction-protocol.json").read_bytes()).hexdigest()[:12]
 prepared=torch.load(ROOT/f"recognition-features-full-{protocol}.pt",weights_only=False)
 val=[(x,p,y) for x,p,y,s in prepared if s=="val"]
 base=pipeline.load_checkpoint(CHECKPOINTS[0],DEVICE)
 mean=pipeline.to_numpy(base["feature_mean"]); std=np.maximum(pipeline.to_numpy(base["feature_std"]),1e-6)
 loader=DataLoader(Sequences(val,mean,std),batch_size=16,shuffle=False,collate_fn=collate)
 models=[]
 for path in CHECKPOINTS:
  ck=pipeline.load_checkpoint(path,DEVICE); c=ck["config"]
  model=pipeline.RecognitionTCNAttentionSafe(c["input_dim"],100,c["hidden_dim"],c["num_blocks"],c["kernel_size"],c["dropout"],c["attention_dropout"])
  model.load_state_dict(ck["model_state_dict"]); model.eval(); models.append(model)
 labels=[]; probabilities=[[] for _ in models]
 with torch.no_grad():
  for x,mask,y in loader:
   labels.extend(y.tolist())
   for target,model in zip(probabilities,models):
    logits,_=model(x,mask); target.extend(torch.softmax(logits,1).numpy())
 y=np.asarray(labels); ps=[np.asarray(p) for p in probabilities]
 result={"count":len(y),"members":[{"checkpoint":str(path),**score(y,p)} for path,p in zip(CHECKPOINTS,ps)],
         "equal_probability_ensemble":score(y,np.mean(ps,axis=0))}
 out=ROOT/"ensemble-validation.json"; out.write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps(result,indent=2))

if __name__=="__main__": main()
