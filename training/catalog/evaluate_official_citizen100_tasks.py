"""Evaluate Microsoft ST-GCN with deployment-compatible MediaPipe Tasks input."""
from __future__ import annotations
import argparse,csv,json,sys,time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import cv2, numpy as np, torch
import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision as mp_vision

HERE=Path(__file__).parent; sys.path.insert(0,str(HERE))
from check_pretrained_citizen import EDGES,ROOT as PRETRAINED,encode
ROOT=Path("/opt/handspeak-training/capstone100-retrain")
MODELS=ROOT/"models"; CACHE=PRETRAINED/"tasks30-poses"
_HAND=_POSE=None; _TIME=0

def init_worker():
 global _HAND,_POSE
 cv2.setNumThreads(1)
 _HAND=mp_vision.HandLandmarker.create_from_options(mp_vision.HandLandmarkerOptions(
  base_options=mp_tasks.BaseOptions(model_asset_path=str(MODELS/"hand_landmarker.task")),
  running_mode=mp_vision.RunningMode.VIDEO,num_hands=2,min_hand_detection_confidence=.1,
  min_hand_presence_confidence=.1,min_tracking_confidence=.1))
 _POSE=mp_vision.PoseLandmarker.create_from_options(mp_vision.PoseLandmarkerOptions(
  base_options=mp_tasks.BaseOptions(model_asset_path=str(MODELS/"pose_landmarker_full.task")),
  running_mode=mp_vision.RunningMode.VIDEO,num_poses=1,min_pose_detection_confidence=.5,
  min_tracking_confidence=.5))

def extract(row):
 global _TIME
 target=CACHE/f"{row['sha256']}.npz"
 if target.exists():
  with np.load(target,allow_pickle=False) as d:return row["sha256"],d["features"]
 cap=cv2.VideoCapture(row["file"]); decoded=[]
 while True:
  ok,frame=cap.read()
  if not ok:break
  h,w=frame.shape[:2]; scale=min(1,640/max(h,w))
  if scale<1:frame=cv2.resize(frame,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
  decoded.append(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
 cap.release()
 if not decoded:raise ValueError("empty video")
 sample=np.linspace(0,len(decoded)-1,30).round().astype(int); detected=[]
 for index in sample:
  _TIME+=34; image=mp.Image(image_format=mp.ImageFormat.SRGB,data=decoded[index])
  pose=_POSE.detect_for_video(image,_TIME); hands=_HAND.detect_for_video(image,_TIME)
  data=np.zeros((75,2),np.float64)
  if pose.pose_landmarks:
   for i,p in enumerate(pose.pose_landmarks[0]):data[i]=(p.x,p.y)
  for landmarks,handed in zip(hands.hand_landmarks,hands.handedness):
   offset=54 if handed[0].category_name=="Left" else 33
   for i,p in enumerate(landmarks):data[offset+i]=(p.x,p.y)
  detected.append(data)
 source=np.linspace(0,1,30); destination=np.linspace(0,1,min(len(decoded),128))
 flat=np.asarray(detected).reshape(30,-1)
 restored=np.stack([np.interp(destination,source,flat[:,i]) for i in range(flat.shape[1])],1).reshape(-1,75,2)
 features=encode(restored);target.parent.mkdir(exist_ok=True)
 with target.with_suffix(".partial").open("wb") as f:np.savez_compressed(f,features=features)
 target.with_suffix(".partial").replace(target)
 return row["sha256"],features

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--test",action="store_true");args=p.parse_args()
 split="test" if args.test else "val"
 manifest=Path("/opt/handspeak-training/capstone100-test/test-manifest.json") if args.test else ROOT/"landmark-manifest.json"
 rows=[r for r in json.loads(manifest.read_text()) if r["split"]==split]
 with Path("/opt/handspeak-training/daily-words/metadata/ASL_Citizen/splits/train.csv").open() as f:
  labels=sorted({r["Gloss"].strip() for r in csv.DictReader(f)})
 targets=sorted({r["label"] for r in rows});indices=np.asarray([labels.index(x) for x in targets]); ids={x:i for i,x in enumerate(targets)}
 features={}
 with ProcessPoolExecutor(max_workers=4,initializer=init_worker) as pool:
  for i,(sha,data) in enumerate(pool.map(extract,rows,chunksize=2),1):
   features[sha]=data
   if i%25==0 or i==len(rows):print(f"{i}/{len(rows)} Tasks poses",flush=True)
 source=PRETRAINED/"source/ST-GCN";sys.path.insert(0,str(source))
 from architecture.st_gcn import STGCN
 from architecture.fc import FC
 from architecture.network import Network
 model=Network(STGCN(2,dict(num_nodes=27,center=0,inward_edges=EDGES),True),FC(256,len(labels),dropout_ratio=.05)).double().eval()
 model.load_state_dict(torch.load(PRETRAINED/"model.pt",map_location="cpu",weights_only=True));torch.set_num_threads(4)
 y=[];pred=[];top5=0;started=time.monotonic()
 with torch.no_grad():
  for row in rows:
   logits=model(torch.tensor(features[row["sha256"]][None]))[0].numpy()[indices];order=np.argsort(logits)[::-1]
   expected=ids[row["label"]];y.append(expected);pred.append(int(order[0]));top5+=expected in order[:5]
 y=np.asarray(y);pred=np.asarray(pred);f1=[]
 for c in range(100):
  tp=np.sum((y==c)&(pred==c));fp=np.sum((y!=c)&(pred==c));fn=np.sum((y==c)&(pred!=c));f1.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0)
 result={"model":"Microsoft ASL Citizen ST-GCN","preprocessing":"MediaPipe Tasks 30-frame browser-compatible",
  "partition":split,"clips":len(rows),"top1":float(np.mean(y==pred)),"top5":top5/len(rows),
  "macro_f1":float(np.mean(f1)),"inference_seconds":time.monotonic()-started,"deployed":False}
 (ROOT/f"official-stgcn-100-tasks30-{split}.json").write_text(json.dumps(result,indent=2)+"\n");print(json.dumps(result,indent=2))

if __name__=="__main__":main()
