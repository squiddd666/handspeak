"""Re-extract every PopSign clip with live-style contiguous sampling.

Writes extracted-contiguous.json beside the uniform-sample cache. Same MediaPipe options and
the same motionFrame/encodeMotion implementation as the shipped harness; only the frame
selection changes (30 consecutive frames centred on the signing window instead of 30 frames
spread across the whole clip).
"""
import json
import sys
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import quickjs
from concurrent.futures import ProcessPoolExecutor

SITE = Path("/opt/handspeak/repository")
CACHE = Path("/opt/handspeak-training/popsign/extracted.json")
OUT = Path("/opt/handspeak-training/popsign/extracted-contiguous.json")
WINDOW = 30

_JS = None


def js():
    global _JS
    if _JS is None:
        _JS = quickjs.Context()
        for name in ["gesture-model.js", "motion-model.js"]:
            _JS.eval((SITE / name).read_text().replace("export ", ""))
    return _JS


def extract(row):
    cap = cv2.VideoCapture(row["file"], cv2.CAP_FFMPEG, [cv2.CAP_PROP_N_THREADS, 1])
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    start = max(0, total // 2 - WINDOW // 2)
    selected = list(range(start, min(total, start + WINDOW)))
    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path="/opt/handspeak-training/hand_landmarker.task"),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, num_hands=2,
        min_hand_detection_confidence=.65, min_hand_presence_confidence=.65,
        min_tracking_confidence=.6)
    hands, aspect, tick = [], 1, 0
    with mp.tasks.vision.HandLandmarker.create_from_options(options) as detector:
        for index in selected:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
            ok, bgr = cap.read()
            if not ok:
                continue
            height, width = bgr.shape[:2]
            aspect = height / width
            factor = min(1, 640 / max(height, width))
            rgb = cv2.cvtColor(cv2.resize(bgr, (round(width * factor), round(height * factor))),
                               cv2.COLOR_BGR2RGB)
            tick += 1
            result = detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb),
                                               tick * 33)
            detection = {"landmarks": [[dict(x=p.x, y=p.y, z=p.z) for p in ps] for ps in result.hand_landmarks],
                         "handedness": [[{"categoryName": h.category_name} for h in hs] for hs in result.handedness]}
            js().eval("var d=" + json.dumps(detection) + ";")
            frame = json.loads(js().eval(
                "JSON.stringify(motionFrame({landmarks:d.landmarks.filter(isUsableHand),"
                "handedness:d.handedness.filter((_,i)=>isUsableHand(d.landmarks[i]))}))"))
            hands.append(frame)
    cap.release()
    sequence = json.loads(js().eval("JSON.stringify(encodeMotion(" + json.dumps(hands) + "," + str(aspect) + "))"))
    return {**row, "rawFrames": hands, "imageAspect": aspect, "sequence": sequence,
            "sampling": f"contiguous{WINDOW}"}


def main():
    rows = json.loads(CACHE.read_text())
    for row in rows:
        row["label"] = "THANK YOU" if row["label"] == "THANKYOU" else row["label"]
    print("rows:", len(rows), flush=True)
    result = []
    with ProcessPoolExecutor(max_workers=2) as pool:
        for row in pool.map(extract, rows):
            result.append(row)
            if len(result) % 12 == 0:
                ok = sum(1 for r in result if r["sequence"] is not None)
                print(f"extracted {len(result)}/{len(rows)} usable {ok}", flush=True)
    OUT.write_text(json.dumps(result, separators=(",", ":")))
    ok = [r for r in result if r["sequence"] is not None]
    print("complete:", len(result), "usable:", len(ok), "->", OUT, flush=True)


if __name__ == "__main__":
    main()
