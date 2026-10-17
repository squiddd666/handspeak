"""Can the recorded tracking failures be recovered by live-style contiguous sampling?

The recorded clips were sampled as 30 frames spread uniformly across the video. The live app
instead captures contiguous frames over the signing window, so re-sampling the same videos
contiguously (and slightly more densely) tests whether the failures are a harness artifact
rather than genuinely untrackable signing.
"""
import json
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import quickjs

SITE = Path("/opt/handspeak/repository")
CACHE = Path("/opt/handspeak-training/popsign/extracted.json")
MODES = {"uniform30": None, "contiguous30": 30, "contiguous45": 45}


def load_js():
    js = quickjs.Context()
    for name in ["gesture-model.js", "motion-model.js"]:
        js.eval((SITE / name).read_text().replace("export ", ""))
    return js


def run(js, row, mode, window):
    cap = cv2.VideoCapture(row["file"], cv2.CAP_FFMPEG, [cv2.CAP_PROP_N_THREADS, 1])
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if mode is None:
        selected = list(np.unique(np.linspace(0, max(0, total - 1), 30).astype(int)))
    else:
        center = total // 2
        start = max(0, center - window // 2)
        selected = list(range(start, min(total, start + window)))
    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path="/opt/handspeak-training/hand_landmarker.task"),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, num_hands=2,
        min_hand_detection_confidence=.65, min_hand_presence_confidence=.65, min_tracking_confidence=.6)
    hands = []
    aspect = 1
    tick = 0
    with mp.tasks.vision.HandLandmarker.create_from_options(options) as detector:
        for index in selected:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
            ok, bgr = cap.read()
            if not ok:
                continue
            height, width = bgr.shape[:2]
            aspect = height / width
            factor = min(1, 640 / max(height, width))
            rgb = cv2.cvtColor(cv2.resize(bgr, (round(width * factor), round(height * factor))), cv2.COLOR_BGR2RGB)
            tick += 1
            result = detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), tick * 33)
            detection = {"landmarks": [[dict(x=p.x, y=p.y, z=p.z) for p in ps] for ps in result.hand_landmarks],
                         "handedness": [[{"categoryName": h.category_name} for h in hs] for hs in result.handedness]}
            js.eval("var d=" + json.dumps(detection) + ";")
            frame = json.loads(js.eval("JSON.stringify(motionFrame({landmarks:d.landmarks.filter(isUsableHand),"
                                       "handedness:d.handedness.filter((_,i)=>isUsableHand(d.landmarks[i]))}))"))
            hands.append(frame)
    cap.release()
    sequence = json.loads(js.eval("JSON.stringify(encodeMotion(" + json.dumps(hands) + "," + str(aspect) + "))"))
    return sequence, len(hands), sum(1 for f in hands if f and any(f))


def main():
    rows = json.loads(CACHE.read_text())
    failures = [r for r in rows if r["split"] == "test" and r.get("sequence") is None and r["label"] != "DRINK"]
    print("tracking failures:", len(failures), "frames per mode exists:",
          all(Path(r["file"]).exists() for r in failures))
    js = load_js()
    recovered = {}
    for row in failures:
        outcome = {}
        for mode, window in MODES.items():
            sequence, sampled, visible = run(js, row, window, window or 0)
            outcome[mode] = dict(valid=sequence is not None, sampled=sampled, visible=visible)
        recovered[row["label"]] = recovered.get(row["label"], [])
        recovered[row["label"]].append(outcome)
        print(f"{row['label']:<12}", {m: ("OK" if v["valid"] else f"no({v['visible']}/{v['sampled']})")
                                      for m, v in outcome.items()}, flush=True)
    for mode in MODES:
        total = sum(1 for entries in recovered.values() for e in entries if e[mode]["valid"])
        print(f"{mode}: recovered {total}/{len(failures)}")


if __name__ == "__main__":
    main()
