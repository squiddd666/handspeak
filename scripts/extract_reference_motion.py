"""Extract the *bundled reference performance*, not a generic sign animation.

python scripts/extract_reference_motion.py [--ids hello please ...]
Downloads official MediaPipe task models into the git-ignored asl-cache folder.
Landmarks stay local; no recordings are uploaded. Retarget with Blender using
retarget_reference_motion.py. Existing videos/recognition models are untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import urllib.request

REPO = Path(__file__).resolve().parents[1]
VERSION = "kai-reference-landmarks-v3"
SIDES = {"Left": 15, "Right": 16}
MODEL_URLS = {
    "pose": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task",
    "hands": "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assign_hands(candidates: list, pose: list | None, previous: dict, width: int, height: int) -> dict:
    """One-to-one anatomical slots anchored to pose wrists, NEVER screen X.

    Screen-X assignment swaps the hands when they cross (PAIN, BOOK, etc.).
    Handedness alone is unreliable for non-selfie videos and overlapping hands.
    Pose wrist anchors plus short-term continuity also preserve two-hand signs.
    """
    if not candidates:
        return {}
    if pose:
        shoulder_span = math.hypot((pose[11][0] - pose[12][0]) * width,
                                   (pose[11][1] - pose[12][1]) * height)
    else:
        shoulder_span = width * .35
    span = max(shoulder_span, width * .12)

    def distance(a, b):
        return math.hypot((a[0] - b[0]) * width, (a[1] - b[1]) * height) / span

    def cost(side, candidate):
        wrist = candidate["landmarks"][0]
        anchor = pose[SIDES[side]] if pose else None
        anchored = anchor is not None and anchor[3] >= .25 and -.2 <= anchor[0] <= 1.2 and -.1 <= anchor[1] <= 1.2
        prior = previous.get(side)
        label_penalty = .35 * candidate["score"] if candidate.get("label") in SIDES and candidate["label"] != side else 0
        if anchor is not None and anchor[3] >= .25 and distance(wrist, anchor) > 1.5:
            return 100 + distance(wrist, anchor)
        if anchored:
            d = distance(wrist, anchor)
            # A hand crop can include its neighbour; do not assign it twice.
            if d > 1.15:
                return 100 + d
            return .65 * d + (.3 * distance(wrist, prior) if prior else 0) + label_penalty - .04 * candidate["score"]
        if prior:
            return distance(wrist, prior) + .25 + label_penalty
        if candidate.get("label") == side and candidate["score"] >= .7:
            return .9  # last resort only: confident handedness without a pose anchor
        return 10  # no anatomical evidence: leave this detection unassigned

    best, best_cost = {}, float("inf")
    # Include an unassigned slot rather than inventing the missing hand.
    for li, ri in itertools.product(range(-1, len(candidates)), repeat=2):
        if li >= 0 and li == ri:
            continue
        slots = {"Left": li, "Right": ri}
        total = sum(cost(side, candidates[i]) if i >= 0 else 1.5 for side, i in slots.items())
        if total < best_cost:
            best_cost = total
            best = {side: candidates[i] for side, i in slots.items() if i >= 0}
    return best


def update_cached_slots(record):
    """Repair anatomical assignment without needlessly rerunning neural models."""
    previous, previous_time = {}, {}
    ref = record["reference"]
    for frame in record["frames"]:
        time = frame["time"]
        previous = {side: p for side, p in previous.items() if time - previous_time[side] < .35}
        frame["hands"] = assign_hands(list(frame["hands"].values()), frame["pose"], previous, ref["width"], ref["height"])
        for side, hand in frame["hands"].items():
            previous[side], previous_time[side] = hand["landmarks"][0], time
    record["version"] = VERSION
    return record


def coordinates(points, visibility=False):
    return [[round(p.x, 6), round(p.y, 6), round(p.z, 6)] +
            ([round(float(getattr(p, "visibility", 1) or 0), 6)] if visibility else [])
            for p in points]


def hand_candidates(result, crop=None, width=1, height=1):
    candidates = []
    for i, points in enumerate(result.hand_landmarks):
        norm = coordinates(points)
        if crop:
            x, y, w, h = crop
            for p in norm:
                p[0] = (x + p[0] * w) / width
                p[1] = (y + p[1] * h) / height
                p[2] *= w / width
        categories = result.handedness[i] if i < len(result.handedness) else []
        category = categories[0] if categories else None
        candidates.append({"landmarks": norm, "world": coordinates(result.hand_world_landmarks[i]),
                           "score": round(float(category.score if category else .5), 6),
                           "label": category.category_name if category else "",
                           "cropRecovery": bool(crop)})
    return candidates


def extract(path: Path, cache: Path, models: dict, sample_fps: float, force=False) -> dict:
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python as tasks
    from mediapipe.tasks.python import vision

    output = cache / (path.stem + ".json")
    source_hash = sha256(path)
    if output.exists() and not force:
        old = json.loads(output.read_text(encoding="utf-8"))
        if old.get("version") in ("kai-reference-landmarks-v1", "kai-reference-landmarks-v2") and old.get("reference", {}).get("sha256") == source_hash and old.get("sampleFps") == sample_fps:
            old = update_cached_slots(old)
            output.write_text(json.dumps(old, separators=(",", ":")), encoding="utf-8")
        if old.get("version") == VERSION and old.get("reference", {}).get("sha256") == source_hash and old.get("sampleFps") == sample_fps:
            return old
    cap = cv2.VideoCapture(str(path))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if fps <= 0 or count < 2:
        raise ValueError("Undecodable reference: " + str(path))
    wanted = {min(count - 1, round(t * fps / sample_fps)) for t in range(math.ceil(count / fps * sample_fps))}
    wanted.update((0, count - 1))
    pose_options = vision.PoseLandmarkerOptions(
        base_options=tasks.BaseOptions(model_asset_path=str(models["pose"])),
        running_mode=vision.RunningMode.VIDEO, num_poses=1,
        min_pose_detection_confidence=.35, min_pose_presence_confidence=.35, min_tracking_confidence=.35)
    hand_options = vision.HandLandmarkerOptions(
        base_options=tasks.BaseOptions(model_asset_path=str(models["hands"])),
        running_mode=vision.RunningMode.VIDEO, num_hands=2,
        min_hand_detection_confidence=.25, min_hand_presence_confidence=.25, min_tracking_confidence=.3)
    crop_options = vision.HandLandmarkerOptions(
        base_options=tasks.BaseOptions(model_asset_path=str(models["hands"])),
        running_mode=vision.RunningMode.IMAGE, num_hands=2,
        min_hand_detection_confidence=.25, min_hand_presence_confidence=.25)
    frames, previous, previous_time = [], {}, {}
    try:
        with vision.PoseLandmarker.create_from_options(pose_options) as pose_detector, \
                vision.HandLandmarker.create_from_options(hand_options) as hand_detector, \
                vision.HandLandmarker.create_from_options(crop_options) as crop_detector:
            for frame_index in range(count):
                ok, bgr = cap.read()
                if not ok:
                    raise ValueError(f"Reference {path.stem} stopped at frame {frame_index}/{count}")
                if frame_index not in wanted:
                    continue
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                # Full-resolution 1944x2592 refs need not consume excessive CPU.
                ratio = min(1., 960 / max(width, height))
                if ratio < 1:
                    rgb = cv2.resize(rgb, None, fx=ratio, fy=ratio, interpolation=cv2.INTER_AREA)
                work_h, work_w = rgb.shape[:2]
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                milliseconds = round(frame_index / fps * 1000)
                pose_result = pose_detector.detect_for_video(image, milliseconds)
                pose = coordinates(pose_result.pose_landmarks[0], True) if pose_result.pose_landmarks else None
                world = coordinates(pose_result.pose_world_landmarks[0], True) if pose_result.pose_world_landmarks else None
                candidates = hand_candidates(hand_detector.detect_for_video(image, milliseconds))
                # Expire temporal anchors: a returning hand is not last second's hand.
                previous = {side: p for side, p in previous.items() if milliseconds / 1000 - previous_time[side] < .35}
                assigned = assign_hands(candidates, pose, previous, work_w, work_h)
                if pose:
                    span = math.hypot((pose[11][0] - pose[12][0]) * work_w,
                                      (pose[11][1] - pose[12][1]) * work_h)
                    for side in SIDES:
                        if side in assigned:
                            continue
                        wrist, index = pose[SIDES[side]], pose[19 if side == "Left" else 20]
                        if wrist[3] < .25 or not (0 <= wrist[0] <= 1 and 0 <= wrist[1] <= 1):
                            continue
                        cx = (wrist[0] * .65 + index[0] * .35) * work_w
                        cy = (wrist[1] * .65 + index[1] * .35) * work_h
                        size = max(100, min(work_w * .55, span * .8))
                        x0, y0 = max(0, int(cx - size / 2)), max(0, int(cy - size / 2))
                        x1, y1 = min(work_w, int(cx + size / 2)), min(work_h, int(cy + size / 2))
                        if x1 - x0 < 32 or y1 - y0 < 32:
                            continue
                        roi = rgb[y0:y1, x0:x1].copy()
                        recovered = hand_candidates(crop_detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=roi)),
                                                    (x0, y0, x1 - x0, y1 - y0), work_w, work_h)
                        for candidate in recovered:
                            p = candidate["landmarks"][0]
                            if any(math.hypot((p[0] - c["landmarks"][0][0]) * work_w,
                                              (p[1] - c["landmarks"][0][1]) * work_h) < span * .12 for c in candidates):
                                continue
                            candidates.append(candidate)
                    assigned = assign_hands(candidates, pose, previous, work_w, work_h)
                for side, hand in assigned.items():
                    previous[side], previous_time[side] = hand["landmarks"][0], milliseconds / 1000
                frames.append({"time": round(frame_index / fps, 7), "pose": pose, "poseWorld": world, "hands": assigned})
    finally:
        cap.release()
    record = {"version": VERSION, "id": path.stem, "sampleFps": sample_fps,
              "reference": {"file": path.relative_to(REPO).as_posix(), "sha256": source_hash,
                            "fps": fps, "frames": count, "duration": count / fps, "width": width, "height": height},
              "tools": {"mediapipe": mp.__version__, "opencv": cv2.__version__},
              "models": {key: {"url": MODEL_URLS[key], "sha256": sha256(model)} for key, model in models.items()},
              "frames": frames}
    output.write_text(json.dumps(record, separators=(",", ":")), encoding="utf-8")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--cache", type=Path, default=REPO / "asl-cache/kai-reference")
    parser.add_argument("--fps", type=float, default=30)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if not 5 <= args.fps <= 60:
        parser.error("--fps must be between 5 and 60")
    args.cache.mkdir(parents=True, exist_ok=True)
    models = {}
    for key, url in MODEL_URLS.items():
        model = args.cache / (key + ".task")
        if not model.exists():
            temporary = model.with_suffix(".download")
            urllib.request.urlretrieve(url, temporary)
            temporary.replace(model)
        models[key] = model
    ids = args.ids or sorted(p.stem for p in (REPO / "media/signs").glob("*.mp4") if not p.stem.startswith("test-"))
    for n, id_ in enumerate(ids, 1):
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", id_):
            parser.error("Invalid sign id: " + id_)
        record = extract(REPO / "media/signs" / (id_ + ".mp4"), args.cache, models, args.fps, args.force)
        frames = record["frames"]
        print(f'{n}/{len(ids)} {id_}: {len(frames)} frames; pose {sum(bool(f["pose"]) for f in frames)}; '
              + "; ".join(f'{side} hand {sum(side in f["hands"] for f in frames)}' for side in SIDES), flush=True)


if __name__ == "__main__":
    main()
