"""Extract the exact 49-landmark sequences expected by CAPSTONE_ASL.

Raw ASL Citizen videos and derived landmarks stay outside the served repository.
The official test partition is intentionally not read by this development step.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision as mp_vision

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "third_party" / "capstone_asl"))
import pipeline

ROOT = Path("/opt/handspeak-training/capstone100-retrain")
HAND_MODEL = ROOT / "models" / "hand_landmarker.task"
POSE_MODEL = ROOT / "models" / "pose_landmarker_full.task"
_HAND = _POSE = None
_TIMESTAMP = 0


def _init_worker():
    global _HAND, _POSE
    cv2.setNumThreads(1)
    _HAND = mp_vision.HandLandmarker.create_from_options(mp_vision.HandLandmarkerOptions(
        base_options=mp_tasks.BaseOptions(model_asset_path=str(HAND_MODEL)),
        running_mode=mp_vision.RunningMode.VIDEO, num_hands=2,
        min_hand_detection_confidence=.1, min_hand_presence_confidence=.1,
        min_tracking_confidence=.1))
    _POSE = mp_vision.PoseLandmarker.create_from_options(mp_vision.PoseLandmarkerOptions(
        base_options=mp_tasks.BaseOptions(model_asset_path=str(POSE_MODEL)),
        running_mode=mp_vision.RunningMode.VIDEO, num_poses=1,
        min_pose_detection_confidence=.5, min_tracking_confidence=.5))


def _detect(frame):
    global _TIMESTAMP
    _TIMESTAMP += 34
    image=mp.Image(image_format=mp.ImageFormat.SRGB,data=frame)
    hands=_HAND.detect_for_video(image,_TIMESTAMP)
    poses=_POSE.detect_for_video(image,_TIMESTAMP)
    pose=np.zeros((7,3),np.float32); lh=np.zeros((21,3),np.float32); rh=np.zeros((21,3),np.float32)
    pok=bool(poses.pose_landmarks)
    if pok:
        for out,index in enumerate(pipeline.POSE_IDXS):
            point=poses.pose_landmarks[0][index]; pose[out]=(point.x,point.y,point.z)
    lok=rok=False
    for landmarks,handed in zip(hands.hand_landmarks,hands.handedness):
        left=handed[0].category_name=="Left"; target=lh if left else rh
        for index,point in enumerate(landmarks): target[index]=(point.x,point.y,point.z)
        if left: lok=True
        else: rok=True
    return pose,lh,rh,pok,lok,rok


def _sample_frames(path: str, count: int = 30):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        cap.release()
        raise ValueError("video_open_failed")
    # Sequential decoding is much faster than 60 random seeks in short MP4s.
    decoded = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        height, width = frame.shape[:2]
        scale = min(1.0, 640.0 / max(height, width))
        if scale < 1:
            frame = cv2.resize(frame, None, fx=scale, fy=scale,
                               interpolation=cv2.INTER_AREA)
        decoded.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    cap.release()
    if not decoded:
        raise ValueError("video_has_no_frames")
    indices = np.linspace(0, len(decoded) - 1, count).round().astype(int)
    return [decoded[index] for index in indices]


def _extract(item):
    row, protocol_hash = item
    key = row["sha256"]
    target = ROOT / "landmarks" / row["split"] / row["label"].lower() / f"{key}.npz"
    if target.exists():
        try:
            with np.load(target, allow_pickle=False) as data:
                if str(data["protocol_hash"]) == protocol_hash:
                    return {**row, "landmarks": str(target), "status": "cached",
                            "pose_frames": int(data["pose_mask"].sum()),
                            "hand_frames": int(np.logical_or(data["lh_mask"], data["rh_mask"]).sum())}
        except Exception:
            target.unlink(missing_ok=True)
    try:
        pose, lh, rh, pm, lm, rm = [], [], [], [], [], []
        for frame in _sample_frames(row["file"]):
            values = _detect(frame)
            p, l, r, pok, lok, rok = values
            pose.append(p); lh.append(l); rh.append(r)
            pm.append(pok); lm.append(lok); rm.append(rok)
        # Restore the live 60-frame cadence after detector sampling. Linear
        # landmark interpolation retains motion scale while halving CPU work.
        source_x = np.linspace(0.0, 1.0, len(pose))
        target_x = np.linspace(0.0, 1.0, 60)
        def resample(values):
            a=np.asarray(values)
            flat=a.reshape(len(a),-1)
            out=np.stack([np.interp(target_x,source_x,flat[:,j]) for j in range(flat.shape[1])],1)
            return out.reshape((60,)+a.shape[1:]).astype(np.float32)
        nearest=np.rint(np.linspace(0,len(pm)-1,60)).astype(int)
        pose,lh,rh=resample(pose),resample(lh),resample(rh)
        pm=np.asarray(pm,bool)[nearest]; lm=np.asarray(lm,bool)[nearest]; rm=np.asarray(rm,bool)[nearest]
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".partial.npz")
        np.savez_compressed(temporary, pose=np.asarray(pose, np.float32),
                            lh=np.asarray(lh, np.float32), rh=np.asarray(rh, np.float32),
                            pose_mask=np.asarray(pm, bool), lh_mask=np.asarray(lm, bool),
                            rh_mask=np.asarray(rm, bool), protocol_hash=protocol_hash)
        temporary.replace(target)
        return {**row, "landmarks": str(target), "status": "ok",
                "pose_frames": int(sum(pm)),
                "hand_frames": int(sum(a or b for a, b in zip(lm, rm)))}
    except Exception as error:
        return {**row, "status": "error", "error": f"{type(error).__name__}:{error}"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    manifest_path = ROOT / "development-manifest.json"
    rows = json.loads(manifest_path.read_text())
    protocol = {
        "source_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "pipeline_sha256": hashlib.sha256(Path(pipeline.__file__).read_bytes()).hexdigest(),
        "extractor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "detector_frames": 30, "sequence_frames": 60, "resampling": "linear landmarks",
        "mediapipe_mode": "VIDEO",
        "max_side": 640,
        "pose_indices": pipeline.POSE_IDXS,
        "partition": "official ASL Citizen train and validation only",
        "test_opened": False,
    }
    HAND_MODEL.parent.mkdir(parents=True, exist_ok=True)
    # Download detector assets once before worker startup.
    hand, pose = pipeline.make_landmarkers(HAND_MODEL, POSE_MODEL)
    hand.close(); pose.close()
    protocol["hand_model_sha256"] = hashlib.sha256(HAND_MODEL.read_bytes()).hexdigest()
    protocol["pose_model_sha256"] = hashlib.sha256(POSE_MODEL.read_bytes()).hexdigest()
    protocol_hash = hashlib.sha256(json.dumps(protocol, sort_keys=True).encode()).hexdigest()
    (ROOT / "extraction-protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    results = []
    ctx = __import__("multiprocessing").get_context("spawn")
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,
            mp_context=ctx, initializer=_init_worker) as pool:
        for result in pool.map(_extract, ((row, protocol_hash) for row in rows), chunksize=2):
            results.append(result)
            if len(results) % 25 == 0 or len(results) == len(rows):
                usable = sum(x.get("hand_frames", 0) >= 8 for x in results)
                print(f"{len(results)}/{len(rows)} extracted · {usable} usable", flush=True)
    output = ROOT / "landmark-manifest.json"
    output.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({"total": len(results),
                      "errors": sum(x["status"] == "error" for x in results),
                      "usable": sum(x.get("hand_frames", 0) >= 8 for x in results),
                      "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()
