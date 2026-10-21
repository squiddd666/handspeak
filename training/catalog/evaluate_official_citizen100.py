"""Evaluate Microsoft's official 2,731-class ST-GCN as a closed 100-word model."""
from __future__ import annotations
import argparse, csv, hashlib, json, sys, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
import torch

HERE=Path(__file__).parent
sys.path.insert(0,str(HERE))
from check_pretrained_citizen import EDGES, ROOT as PRETRAINED, encode

ROOT=Path("/opt/handspeak-training/capstone100-retrain")
SOURCE=PRETRAINED/"source"
_HOLISTIC=None

def init_worker():
 import cv2, mediapipe as mp
 global _HOLISTIC
 cv2.setNumThreads(1)
 _HOLISTIC=mp.solutions.holistic.Holistic(static_image_mode=False,min_detection_confidence=.5)

def extract_fast(row):
 import cv2
 path=Path(row["file"]); cache=PRETRAINED/"pilot-poses"/f"{row['sha256']}.npz"
 if cache.exists():
  with np.load(cache,allow_pickle=False) as saved: return row["sha256"],saved["features"]
 if hashlib.sha256(path.read_bytes()).hexdigest()!=row["sha256"]: raise ValueError("hash mismatch")
 cap=cv2.VideoCapture(str(path)); frames=[]
 while True:
  ok,bgr=cap.read()
  if not ok: break
  h,w=bgr.shape[:2]; factor=min(1,640/max(h,w))
  if factor<1:bgr=cv2.resize(bgr,(round(w*factor),round(h*factor)))
  result=_HOLISTIC.process(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)); data=np.zeros((75,2),np.float64)
  for offset,points in ((0,result.pose_landmarks),(33,result.right_hand_landmarks),(54,result.left_hand_landmarks)):
   if points:
    for i,point in enumerate(points.landmark): data[offset+i]=(point.x,point.y)
  frames.append(data)
 cap.release()
 features=encode(np.asarray(frames)); cache.parent.mkdir(exist_ok=True)
 with cache.with_suffix(".partial").open("wb") as stream:
  np.savez_compressed(stream,features=features,frames=len(frames),seconds=0.)
 cache.with_suffix(".partial").replace(cache)
 return row["sha256"],features

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument("--test",action="store_true")
 parser.add_argument("--cached-only",action="store_true")
 args=parser.parse_args()
 manifest=(Path("/opt/handspeak-training/capstone100-test")/"test-manifest.json"
           if args.test else ROOT/"landmark-manifest.json")
 split="test" if args.test else "val"
 rows=[r for r in json.loads(manifest.read_text()) if r["split"]==split]
 if args.cached_only:
  cache=PRETRAINED/"pilot-poses"
  rows=[r for r in rows if (cache/f"{r['sha256']}.npz").exists()]
 metadata=Path("/opt/handspeak-training/daily-words/metadata/ASL_Citizen/splits/train.csv")
 with metadata.open() as stream:
  labels=sorted({r["Gloss"].strip() for r in csv.DictReader(stream)})
 target_labels=sorted({r["label"] for r in rows})
 target_indices=np.asarray([labels.index(label) for label in target_labels])
 label_to_target={label:i for i,label in enumerate(target_labels)}
 features={}
 with ProcessPoolExecutor(max_workers=4,initializer=init_worker) as pool:
  for i,(sha,data) in enumerate(pool.map(extract_fast,rows,chunksize=2),1):
   features[sha]=data
   if i%25==0 or i==len(rows): print(f"{i}/{len(rows)} ST-GCN poses",flush=True)
 sys.path.insert(0,str(SOURCE/"ST-GCN"))
 from architecture.st_gcn import STGCN
 from architecture.fc import FC
 from architecture.network import Network
 model=Network(STGCN(2,dict(num_nodes=27,center=0,inward_edges=EDGES),True),
               FC(256,len(labels),dropout_ratio=.05)).double().eval()
 model.load_state_dict(torch.load(PRETRAINED/"model.pt",map_location="cpu",weights_only=True))
 torch.set_num_threads(4)
 expected=[]; predictions=[]; top5=0; started=time.monotonic()
 with torch.no_grad():
  for row in rows:
   logits=model(torch.tensor(features[row["sha256"]][None]))[0].numpy()[target_indices]
   order=np.argsort(logits)[::-1]
   expected.append(label_to_target[row["label"]]); predictions.append(int(order[0]))
   top5 += label_to_target[row["label"]] in order[:5]
 y=np.asarray(expected); pred=np.asarray(predictions)
 f1=[]
 for c in range(100):
  tp=np.sum((y==c)&(pred==c)); fp=np.sum((y!=c)&(pred==c)); fn=np.sum((y==c)&(pred!=c))
  f1.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0)
 result={"model":"Microsoft ASL Citizen ST-GCN","classes":100,"partition":split,"clips":len(rows),
         "top1":float(np.mean(y==pred)),"top5":top5/len(rows),"macro_f1":float(np.mean(f1)),
         "inference_seconds":time.monotonic()-started,"deployed":False}
 output=ROOT/f"official-stgcn-100-{split}{'-cached' if args.cached_only else ''}.json"
 output.write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps(result,indent=2))

if __name__=="__main__":main()
