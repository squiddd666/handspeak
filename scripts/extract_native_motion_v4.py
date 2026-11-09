"""Native full-clip feature extraction, not browser/camera automation.

Keeps every selected source timestamp, including missing-hand frames. Uses
Holistic body coordinates and separate Tasks hand sequences compatible with
the local manual camera encoding. Original recordings stay outside the site.
"""
from __future__ import annotations
import argparse,json,os,time,urllib.request
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import cv2,numpy as np,mediapipe as mp

POSE=[0,2,5,11,12,13,14]
MODEL_URL="https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
_holistic=None;_model=None;_samples=32


def initialize(model,samples):
    global _holistic,_model,_samples
    cv2.setNumThreads(1);_model=Path(model).read_bytes();_samples=samples
    _holistic=mp.solutions.holistic.Holistic(static_image_mode=False,model_complexity=1,
        smooth_landmarks=True,min_detection_confidence=.5,min_tracking_confidence=.5)


def extract(row):
    global _holistic
    start=time.perf_counter();cap=cv2.VideoCapture(row["path"])
    try:
        count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));fps=cap.get(cv2.CAP_PROP_FPS)
        if count<1 or not np.isfinite(fps) or fps<=0:raise ValueError("Invalid video metadata")
        ids=set(np.unique(np.linspace(0,count-1,min(_samples,count)).round().astype(int)))
        frames=[];manual=[];stamps=[];sizes=[];body_stamps=[]
        _holistic.reset()
        options=mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_buffer=_model),running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=2,min_hand_detection_confidence=.5,min_hand_presence_confidence=.5,min_tracking_confidence=.5)
        with mp.tasks.vision.HandLandmarker.create_from_options(options) as hands:
            # Decode sequentially; repeated GOP seeks needlessly re-decode the
            # same source frames. Inference still uses only unique timestamps.
            for index in range(count):
                if not cap.grab():break
                if index not in ids:continue
                ok,bgr=cap.retrieve()
                if not ok:continue
                h,w=bgr.shape[:2];scale=min(1,640/max(h,w));sizes=[w,h]
                rgb=cv2.cvtColor(cv2.resize(bgr,(round(w*scale),round(h*scale))),cv2.COLOR_BGR2RGB)
                result=_holistic.process(rgb)
                pts=lambda lm:[[float(p.x),float(p.y),float(p.z)] for p in lm.landmark] if lm else None
                pose=pts(result.pose_landmarks)
                # Actual body-hand identities come from Holistic, not screen X.
                frames.append({"pose":[pose[i] for i in POSE] if pose else None,
                               "left":pts(result.left_hand_landmarks),"right":pts(result.right_hand_landmarks)})
                if pose is not None:body_stamps.append(round(float(index/fps),6))
                detected=hands.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb),round(index/fps*1000))
                slots=[None,None]
                for hand,category in zip(detected.hand_landmarks,detected.handedness):
                    side=0 if category[0].category_name=="Left" else 1
                    if slots[side] is not None:side=1-side
                    slots[side]=[{"x":float(p.x),"y":float(p.y),"z":float(p.z)} for p in hand]
                manual.append(slots);stamps.append(round(float(index/fps),6))
        # Body classifiers require valid pose frames; no coordinates are invented.
        body=[f for f in frames if f["pose"] is not None]
        return {**{k:v for k,v in row.items() if k not in ("cached","path")},"frames":body,"rawFrames":manual,
                "imageAspect":sizes[1]/sizes[0],"sourceDimensions":sizes,"timestamps":stamps,
                "bodyTimestamps":body_stamps,
                "duration":count/fps,"selectedFrames":len(stamps),
                "trackedFrames":sum(bool(f["left"] or f["right"]) for f in body),
                "manualTrackedFrames":sum(any(f) for f in manual),"extractor":"native-holistic-0.10.21+tasks-video-640",
                "maximumImageSide":640,"detectionConfidence":.5,"trackingConfidence":.5,
                "sampling":"uniform source timestamps, whole clip, missing hands retained","seconds":round(time.perf_counter()-start,3)}
    except Exception as error:return {**row,"frames":[],"rawFrames":[],"error":str(error)}
    finally:cap.release()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest",type=Path,required=True);parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--workers",type=int,default=2);parser.add_argument("--samples",type=int,default=32)
    parser.add_argument("--limit",type=int,default=0)
    parser.add_argument("--splits",nargs="+",choices=("train","val","test"),default=["train","val"])
    args=parser.parse_args();rows=json.loads(args.manifest.read_text(encoding="utf-8"))
    done=set()
    if args.out.exists():
        previous={json.loads(l)["file"]:json.loads(l) for l in args.out.read_text(encoding="utf-8").splitlines() if l.strip()}
        done={file for file,r in previous.items() if not r.get("error")}
    todo=[r for r in rows if r["file"] not in done and r["split"] in args.splits and Path(r["path"]).exists()]
    if args.limit:todo=todo[:args.limit]
    args.out.parent.mkdir(parents=True,exist_ok=True)
    model=args.out.parent/"hand_landmarker.task"
    if not model.exists():urllib.request.urlretrieve(MODEL_URL,model)
    print("Extracting",len(todo),"existing",len(done),flush=True)
    start=time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers,initializer=initialize,initargs=(str(model),args.samples)) as pool,args.out.open("a",encoding="utf-8") as sink:
        for i,r in enumerate(pool.map(extract,todo),1):
            sink.write(json.dumps(r,separators=(",",":"))+"\n");sink.flush()
            if i%10==0 or i==len(todo):print(i,"/",len(todo),"seconds",round(time.perf_counter()-start,1),"last tracked",r.get("trackedFrames"),flush=True)


if __name__=="__main__":main()
