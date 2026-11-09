"""Bake local video landmarks into Kai-native, rotation-only finger/arm tracks.

Blender 4.5+: blender --background --factory-startup --python
scripts/retarget_reference_motion.py -- [--ids hello please ...]

Reconstruction is an estimate of monocular video, not certified ASL mocap.
The reference's anatomical hands, individual finger segments, palm directions
and original seconds are retained. Kai's mesh, bind axes and limb lengths are
not changed. Tracking gaps are recorded, never silently described as exact.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import numpy as np
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import retarget_studio_galt as rt
from author_kai_practice import sample_rotations

REPO = Path(__file__).resolve().parents[1]
VERSION = "20261105-reference-3"
SIDES = ("Left", "Right")
DIGIT_POINTS = {"Thumb": (1, 2, 3, 4), "Index": (5, 6, 7, 8),
                "Middle": (9, 10, 11, 12), "Ring": (13, 14, 15, 16), "Pinky": (17, 18, 19, 20)}


def world_from_locals(target, parents, order, locals_):
    world = {}
    for i in order:
        loc, q, scale = rt.local_matrix(target["nodes"][i]).decompose()
        parent = parents.get(i)
        world[i] = (world[parent] if parent is not None else Matrix.Identity(4)) @ Matrix.LocRotScale(loc, locals_.get(i, q), scale)
    return world


def fill_vectors(values, times, default=None):
    good = [i for i, v in enumerate(values) if v is not None and np.isfinite(v).all()]
    if not good:
        if default is None:
            raise ValueError("No reliable pose in reference video")
        return np.repeat(np.asarray(default)[None], len(times), axis=0)
    known = np.asarray([values[i] for i in good], dtype=float)
    flat = known.reshape(len(good), -1)
    filled = np.stack([np.interp(times, np.asarray(times)[good], flat[:, c]) for c in range(flat.shape[1])], axis=1)
    # Three-sample median suppresses spikes without turning NO into a static fist.
    if len(times) >= 3:
        padded = np.pad(filled, ((1, 1), (0, 0)), mode="edge")
        filled = np.median(np.stack((padded[:-2], padded[1:-1], padded[2:])), axis=0)
    return filled.reshape((len(times),) + known.shape[1:])


def fill_quaternions(values, times, active, default, window=3):
    values = list(values)
    original = list(values)
    half = window // 2
    for i, value in enumerate(original):
        if value is None:
            continue
        neighbours = [q for k, q in enumerate(original[max(0, i-half):min(len(values), i+half+1)], max(0, i-half))
                      if q is not None and abs(times[k] - times[i]) < .09]
        if len(neighbours) >= 3:
            def distance(a, b):
                return 2 * math.acos(max(0, min(1, abs(a.dot(b)))))
            values[i] = min(neighbours, key=lambda a: sum(distance(a, b) for b in neighbours)).copy()
    # Monocular tracking can briefly choose the opposite depth solution. Remove
    # isolated orientation spikes, but preserve genuine sustained finger bends.
    for i in range(1, len(values) - 1):
        a, b, c = values[i - 1:i + 2]
        if a is None or b is None or c is None or times[i + 1] - times[i - 1] > .12:
            continue
        expected = a.slerp(c, (times[i] - times[i - 1]) / (times[i + 1] - times[i - 1]))
        if a.rotation_difference(c).angle < math.radians(45) and b.rotation_difference(expected).angle > math.radians(60):
            values[i] = expected.normalized()
    good = [i for i, q in enumerate(values) if q is not None]
    if not good:
        return [default.copy() for _ in times]
    result = []
    active_indices = [i for i, a in enumerate(active) if a]
    for i, t in enumerate(times):
        p = bisect.bisect_left(good, i)
        before, after = good[max(0, p - 1)], good[min(len(good) - 1, p)]
        if before == after:
            q = values[before].copy()
        else:
            weight = max(0, min(1, (t - times[before]) / (times[after] - times[before])))
            q = values[before].slerp(values[after], weight)
        if not active[i]:
            position = bisect.bisect_left(active_indices, i)
            neighbours = active_indices[max(0, position-1):position+1]
            distance = min((abs(t - times[k]) for k in neighbours), default=1.)
            q = default.slerp(q, max(0, 1 - distance / .12))
        result.append(q.normalized())
    # Very light, symmetric smoothing preserves fast finger openings and timing.
    if len(result) >= 3:
        smooth = [result[0]]
        for i in range(1, len(result) - 1):
            smooth.append(result[i].slerp(result[i - 1], .12).slerp(result[i + 1], .12).normalized())
        result = smooth + [result[-1]]
    return result


def max_gap(mask, times, duration):
    longest = start = 0.
    missing = False
    for i, present in enumerate(mask):
        if not present and not missing:
            start, missing = times[i], True
        if present and missing:
            longest, missing = max(longest, times[i] - start), False
    return max(longest, duration - start if missing else 0)


def envelope_at(anchors, times):
    """Reviewed timestamps with smooth, zero-velocity neutral transitions."""
    knots, weights = zip(*anchors)
    values = np.interp(times, knots, weights)
    return values * values * (3 - 2 * values)


class ReferenceRetargeter:
    def __init__(self, model):
        self.model_hash = hashlib.sha256(model.read_bytes()).hexdigest()
        self.target = rt.read_glb(model)
        self.names, self.parents, self.order, self.bind = rt.target_rig(self.target)
        manifest = json.loads((REPO / "media/avatar/clips/index.json").read_text(encoding="utf-8"))
        entry = manifest["signs"]["hello"]
        template = REPO / "media/avatar/clips" / entry["file"]
        if entry["targetModelSha256"] != self.model_hash or hashlib.sha256(template.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("Neutral template is not verified for this Kai model")
        self.neutral_source = {"file": "media/avatar/clips/" + entry["file"], "sha256": entry["sha256"],
                               "sample": 0, "license": entry["license"], "purpose": "unseen-hand neutral fallback only"}
        self.neutral = {self.names[name]: q for name, q in sample_rotations(template, 0).items()}
        self.neutral_world = world_from_locals(self.target, self.parents, self.order, self.neutral)
        self.neutral_q = {i: m.to_quaternion().normalized() for i, m in self.neutral_world.items()}
        self.shoulders = (self.neutral_world[self.names["LeftArm"]].translation + self.neutral_world[self.names["RightArm"]].translation) / 2
        self.width = (self.neutral_world[self.names["LeftArm"]].translation - self.neutral_world[self.names["RightArm"]].translation).length
        self.nose = (self.neutral_world[self.names["LeftEye"]].translation + self.neutral_world[self.names["RightEye"]].translation) / 2 + Vector((0, -.025, .033))
        self.offsets = {}
        for side in SIDES:
            hand = side + "Hand"
            palm = rt.palm_frame(*(self.bind[self.names[hand + part]].translation for part in ("", "Index1", "Middle1", "Pinky1")))
            self.offsets[hand] = self.bind[self.names[hand]].to_quaternion().inverted() @ palm
        corrections_file = Path(__file__).with_name("kai-reference-corrections.json")
        self.corrections = json.loads(corrections_file.read_text(encoding="utf-8"))
        self.corrections_hash = hashlib.sha256(corrections_file.read_bytes()).hexdigest()
        print("Kai calibration: shoulder width",round(self.width, 4),"nose",list(self.nose), flush=True)

    def supporting_hand_pose(self, correction):
        """Estimated occluded grip in native axes; never masquerades as tracking."""
        side = correction["supportSide"]
        y = Vector(correction["palmForward"]).normalized()
        x = Vector(correction["indexAcross"])
        x = (x - y * x.dot(y)).normalized()
        z = x.cross(y).normalized()
        palm = Matrix((x, y, z)).transposed().to_quaternion().normalized()
        hand = self.names[side + "Hand"]
        rotations = {hand: (palm @ self.offsets[side + "Hand"].inverted()).normalized()}
        locals_ = {}
        for digit in DIGIT_POINTS:
            for joint in (1, 2, 3):
                node = self.names[side + "Hand" + digit + str(joint)]
                parent_q = rotations[self.parents[node]]
                initial = (parent_q @ rt.local_matrix(self.target["nodes"][node]).to_quaternion()).normalized()
                following = self.names[side + "Hand" + digit + str(joint + 1)]
                bind_direction = rt.local_matrix(self.target["nodes"][following]).translation
                if digit == "Thumb":
                    a, b, c = correction["thumbDirectionsPalm"][joint - 1]
                    direction = x * a + y * b + z * c
                else:
                    angle = math.radians(correction["fingerCumulativeDegrees"][digit][joint - 1])
                    direction = y * math.cos(angle) - z * math.sin(angle)
                rotations[node] = ((initial @ bind_direction).rotation_difference(direction) @ initial).normalized()
                locals_[node] = (parent_q.inverted() @ rotations[node]).normalized()
        return rotations[hand], locals_

    def bake(self, data, out, audit=None):
        reference, frames = data["reference"], data["frames"]
        video = REPO / reference["file"]
        if hashlib.sha256(video.read_bytes()).hexdigest() != reference["sha256"]:
            raise ValueError("Reference video changed: " + reference["file"])
        correction = self.corrections["signs"].get(data["id"])
        if correction and correction["referenceSha256"] != reference["sha256"]:
            raise ValueError("Reviewed contact needs re-review for changed video: " + data["id"])
        times = [float(f["time"]) for f in frames]
        if len(times) < 3 or any(b <= a for a, b in zip(times, times[1:])):
            raise ValueError("Missing/unordered reference timestamps")
        pose = fill_vectors([np.asarray(f["pose"]) if f["pose"] and min(f["pose"][11][3], f["pose"][12][3]) > .3 else None for f in frames], times)
        world = fill_vectors([np.asarray(f["poseWorld"]) if f["poseWorld"] else None for f in frames], times)
        aspect = reference["height"] / reference["width"]
        spans = np.linalg.norm((pose[:, 11, :2] - pose[:, 12, :2]) * [1, aspect], axis=1)
        image_span = max(.05, float(np.median(spans)))
        world_span = max(.05, float(np.median(np.linalg.norm(world[:, 11, :3] - world[:, 12, :3], axis=1))))
        scale, depth_scale = self.width / image_span, self.width / world_span
        active, observed, hand_rotations, wrists = {}, {}, {}, {}
        for side, wrist_index in (("Left", 15), ("Right", 16)):
            seen = [f["hands"].get(side) for f in frames]
            # A solitary low-confidence false positive must not raise the other hand.
            if sum(bool(h) for h in seen) < 3:
                seen = [None] * len(frames)
            has_evidence = any(seen)
            active[side] = [bool(h) or (has_evidence and f["pose"] is not None and f["pose"][wrist_index][3] > .45 and
                                     -.03 <= f["pose"][wrist_index][0] <= 1.03 and 0 <= f["pose"][wrist_index][1] <= 1.02)
                            for f, h in zip(frames, seen)]
            observed[side] = [h is not None for h in seen]
            raw = {side + "Hand": []}
            raw.update({side + "Hand" + digit + str(j): [] for digit in DIGIT_POINTS for j in (1, 2, 3)})
            points = []
            for i, hand in enumerate(seen):
                points.append(np.asarray(hand["landmarks"][0][:2]) if hand else pose[i, wrist_index, :2])
                rotations = {}
                if hand:
                    # MediaPipe camera coordinates: x right, y down, z away.
                    # glTF/Kai: x right, y up, z toward the viewer. No mirroring.
                    hw = [Vector((p[0], -p[1], -p[2])) for p in hand["world"]]
                    palm = rt.palm_frame(hw[0], hw[5], hw[9], hw[17])
                    rotations[side + "Hand"] = (palm @ self.offsets[side + "Hand"].inverted()).normalized()
                    for digit, indices in DIGIT_POINTS.items():
                        for joint, (a, b) in enumerate(zip(indices, indices[1:]), 1):
                            name = side + "Hand" + digit + str(joint)
                            node = self.names[name]
                            parent_name = self.target["nodes"][self.parents[node]]["name"]
                            parent_q = rotations[parent_name]
                            local_bind = rt.local_matrix(self.target["nodes"][node]).to_quaternion().normalized()
                            initial = (parent_q @ local_bind).normalized()
                            following = self.names[side + "Hand" + digit + str(joint + 1)]
                            bind_direction = rt.local_matrix(self.target["nodes"][following]).translation
                            direction = hw[b] - hw[a]
                            # Minimal swing aligns each captured segment, keeping
                            # exporter roll rather than projecting a noisy palm
                            # normal (which can flip curled fingers by 180 degrees).
                            rotations[name] = ((initial @ bind_direction).rotation_difference(direction) @ initial).normalized()
                for name in raw:
                    q = rotations.get(name)
                    if q is not None and name != side + "Hand":
                        parent_name = self.target["nodes"][self.parents[self.names[name]]]["name"]
                        q = (rotations[parent_name].inverted() @ q).normalized()
                    raw[name].append(q)
            wrists[side] = fill_vectors(points, times)
            hand_rotations.update({self.names[name]: fill_quaternions(values, times, active[side],
                                   self.neutral_q[self.names[name]] if name == side + "Hand" else self.neutral[self.names[name]],
                                   window=5 if name == side + "Hand" else 3) for name, values in raw.items()})

        support_weights = face_weights = None
        if correction:
            support_side = correction["supportSide"]
            if any(observed[support_side]):
                raise ValueError("New supporting-hand observations require re-review: " + data["id"])
            support_weights = envelope_at(correction["supportEnvelope"], times)
            face_weights = envelope_at(correction["faceEnvelope"], times)
            active[support_side] = [bool(weight > 0) for weight in support_weights]
            support_q, support_locals = self.supporting_hand_pose(correction)

        tracks = {self.names[name]: [] for name in rt.MAPPED}
        active_indices = {side: [i for i, a in enumerate(active[side]) if a] for side in SIDES}
        previous, poles, audit_frames = {}, {}, []
        max_clamp = max_length_error = 0.
        for fi, time in enumerate(times):
            desired = {i: self.neutral_q[i].copy() for i in tracks}
            # Interpolate finger joints in LOCAL anatomical space, not each
            # world bone independently. World slerp can choose opposite roll
            # branches for parent/child and introduce 180-degree finger flips.
            for side in SIDES:
                hand = self.names[side + "Hand"]
                desired[hand] = hand_rotations[hand][fi]
                estimated_support = correction and side == correction["supportSide"]
                if estimated_support:
                    desired[hand] = self.neutral_q[hand].slerp(support_q, float(support_weights[fi])).normalized()
                for digit in DIGIT_POINTS:
                    for joint in (1, 2, 3):
                        node = self.names[side + "Hand" + digit + str(joint)]
                        local_q = hand_rotations[node][fi]
                        if estimated_support:
                            local_q = self.neutral[node].slerp(support_locals[node], float(support_weights[fi])).normalized()
                        desired[node] = (desired[self.parents[node]] @ local_q).normalized()
            source_shoulders = (pose[fi, 11, :2] + pose[fi, 12, :2]) / 2
            source_nose = pose[fi, 0, :2]
            shoulder_depth = (world[fi, 11, 2] + world[fi, 12, 2]) / 2

            def goal_at(point, source_z):
                delta = Vector(((point[0] - source_shoulders[0]) * scale,
                                (source_shoulders[1] - point[1]) * aspect * scale,
                                max(-.12, min(.42, (shoulder_depth - source_z) * depth_scale))))
                source_head = Vector(((source_nose[0] - source_shoulders[0]) * scale,
                                      (source_shoulders[1] - source_nose[1]) * aspect * scale,
                                      (shoulder_depth - world[fi, 0, 2]) * depth_scale))
                weight = max(0, min(1, delta.y / max(.08, source_head.y)))
                return self.shoulders + delta + (self.nose - (self.shoulders + source_head)) * weight

            frame_audit = {"time": time, "hands": {}}
            preview = rt.posed_matrices(self.target, self.parents, self.order, desired) if correction else None
            arm_order = (("Right", 16, 14), ("Left", 15, 13)) if correction else (("Left", 15, 13), ("Right", 16, 14))
            for side, wrist_index, elbow_index in arm_order:
                arm, forearm, hand = (self.names[side + n] for n in ("Arm", "ForeArm", "Hand"))
                shoulder = self.neutral_world[arm].translation
                estimated_support = correction and side == correction["supportSide"]
                contact = None
                if estimated_support:
                    # The observed dominant arm is solved first. Restore the
                    # reviewed supporting palm around its lower forearm, rather
                    # than activating an unreliable off-screen pose landmark.
                    dominant = frame_audit["hands"][correction["dominantSide"]]
                    dominant_wrist, dominant_elbow = Vector(dominant["wrist"]), Vector(dominant["elbow"])
                    axis = (dominant_wrist - dominant_elbow).normalized()
                    contact = dominant_wrist - axis * correction["contactBelowWristM"] + Vector((0, 0, correction["contactSurfaceOffsetM"]))
                    palm_offset = (preview[self.names[side + "HandMiddle1"]].translation - preview[hand].translation) * correction["contactPalmFraction"]
                    goal = self.neutral_world[hand].translation.lerp(contact - palm_offset, float(support_weights[fi]))
                    support_pole = shoulder + Vector((.12, -.32, .10))
                    pole = self.neutral_world[forearm].translation.lerp(support_pole, float(support_weights[fi]))
                elif active[side][fi]:
                    goal = goal_at(wrists[side][fi], world[fi, wrist_index, 2])
                    if correction and side == correction["dominantSide"] and face_weights[fi] > 0:
                        # The source hand is larger relative to its face than
                        # Kai's. Keep its tracked C shape, but preserve the
                        # visible eye contact instead of leaving it at the chin.
                        circle = (preview[self.names[side + "HandThumb4"]].translation + preview[self.names[side + "HandIndex4"]].translation) / 2
                        offset = circle - preview[hand].translation
                        face = self.neutral_world[self.names[correction["faceTarget"]]].translation + Vector(correction["faceOffsetM"])
                        goal = goal.lerp(face - offset, float(face_weights[fi]))
                    # Keep reconstructed hand centres in front of the torso, not
                    # embedded in it when monocular depth is underestimated.
                    if goal.y > self.shoulders.y - .30:
                        goal.z = max(goal.z, self.shoulders.z + .095)
                    pole = goal_at(pose[fi, elbow_index, :2], world[fi, elbow_index, 2])
                else:
                    goal = self.neutral_world[hand].translation.copy()
                    pole = self.neutral_world[forearm].translation.copy()
                    p = bisect.bisect_left(active_indices[side], fi)
                    neighbours = active_indices[side][max(0, p-1):p+1]
                    if neighbours:
                        nearest = min(neighbours, key=lambda i: abs(times[i] - time))
                        weight = max(0, 1 - abs(times[nearest] - time) / .15)
                        if weight:
                            visible_goal = goal_at(wrists[side][nearest], world[nearest, wrist_index, 2])
                            if visible_goal.y > self.shoulders.y - .30:
                                visible_goal.z = max(visible_goal.z, self.shoulders.z + .095)
                            goal = goal.lerp(visible_goal, weight)
                            pole = pole.lerp(goal_at(pose[nearest, elbow_index, :2], world[nearest, elbow_index, 2]), weight)
                old_upper = self.neutral_world[forearm].translation - shoulder
                old_lower = self.neutral_world[hand].translation - self.neutral_world[forearm].translation
                elbow, wrist, bend = rt.fit_arm(shoulder, goal, pole, old_upper.length, old_lower.length, poles.get(side))
                poles[side] = bend
                desired[arm] = (old_upper.rotation_difference(elbow - shoulder) @ self.neutral_q[arm]).normalized()
                initial_forearm = (desired[arm] @ self.neutral[forearm]).normalized()
                local_hand = rt.local_matrix(self.target["nodes"][hand]).translation
                desired[forearm] = ((initial_forearm @ local_hand).rotation_difference(wrist - elbow) @ initial_forearm).normalized()
                max_clamp = max(max_clamp, (wrist - goal).length)
                frame_audit["hands"][side] = {"goal": list(goal), "wrist": list(wrist), "elbow": list(elbow), "observed": observed[side][fi], "active": active[side][fi]}
                if estimated_support:
                    frame_audit["hands"][side].update(estimatedSupportWeight=float(support_weights[fi]), contact=list(contact))
            solved = rt.posed_matrices(self.target, self.parents, self.order, desired)
            for i in tracks:
                parent = self.parents.get(i)
                q = ((solved[parent].to_quaternion().inverted() if parent is not None else Quaternion()) @ desired[i]).normalized()
                if i in previous and previous[i].dot(q) < 0:
                    q.negate()
                previous[i] = q.copy()
                tracks[i].extend((q.x, q.y, q.z, q.w))
            for side in SIDES:
                arm, forearm, hand = (self.names[side + n] for n in ("Arm", "ForeArm", "Hand"))
                for a, b in ((arm, forearm), (forearm, hand)):
                    max_length_error = max(max_length_error, abs((solved[a].translation - solved[b].translation).length - (self.bind[a].translation - self.bind[b].translation).length))
            audit_frames.append(frame_audit)
        duration = float(reference["duration"])
        if duration > times[-1] + 1e-6:
            times.append(duration)
            for values in tracks.values():
                values.extend(values[-4:])
        quality = {"poseCoverage": round(sum(bool(f["pose"]) for f in frames) / len(frames), 4),
                   "hands": {}, "maxWristReachClampM": round(max_clamp, 5), "maxLimbLengthErrorM": round(max_length_error, 7)}
        for side in SIDES:
            count = sum(active[side])
            tracked = sum(a and o for a, o in zip(active[side], observed[side]))
            mask = [not a or o for a, o in zip(active[side], observed[side])]
            quality["hands"][side] = {"activeFrames": count, "trackedFrames": tracked,
                                      "coverage": round(tracked / count, 4) if count else 1,
                                      "maxEstimatedGapSeconds": round(max_gap(mask, [f["time"] for f in frames], duration), 4)}
        quality["reviewRequired"] = quality["poseCoverage"] < .8 or any(h["coverage"] < .8 or h["maxEstimatedGapSeconds"] > .3 for h in quality["hands"].values())
        if correction:
            quality["hands"][correction["supportSide"]]["estimatedReason"] = correction["estimatedDetails"]
            quality["reviewRequired"] = True
        metadata = {"id": data["id"], "duration": duration, "fps": data["sampleFps"], "samples": len(times),
                    "source": {"name": "Bundled reference video", "kind": "reference-video"},
                    "reference": reference, "referenceVideo": "./" + reference["file"],
                    "targetModelSha256": self.model_hash, "retargeted": True, "includesFingers": True,
                    "referenceMatched": True, "reconstructed": True, "independentTiming": False,
                    "quality": quality, "neutralTemplate": self.neutral_source,
                    "method": "Anatomical pose-wrist hand assignment; calibrated 3D palm frames and hierarchical per-segment minimal-swing fingers preserving Kai bind roll; local finger interpolation, quaternion median/depth-spike rejection and neutral feathering; head/chest-relative image paths and two-bone IK; original reference seconds",
                    "trackingVersion": data["version"], "trackingTools": data["tools"], "trackingModels": data["models"]}
        if correction:
            metadata["reviewedCorrection"] = {**correction, "version": self.corrections["version"],
                                               "file": "scripts/kai-reference-corrections.json", "sha256": self.corrections_hash}
            metadata["method"] += "; exact-video reviewed supporting-forearm grip and eye-contact correction, with occluded supporting fingers explicitly estimated"
        output = out / (data["id"] + "-reference.glb")
        rt.write_glb(self.target, tracks, times, output, metadata, generator="HandSpeak reference-video-to-Kai reconstruction v1")
        entry = {**metadata, "file": output.name, "bytes": output.stat().st_size,
                 "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
        if audit:
            audit.mkdir(parents=True, exist_ok=True)
            (audit / (data["id"] + ".json")).write_text(json.dumps({"entry": entry, "frames": audit_frames}), encoding="utf-8")
        return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--all-local", action="store_true", help="Include reference files not currently listed in Watch & practice")
    parser.add_argument("--cache", type=Path, default=REPO / "asl-cache/kai-reference")
    parser.add_argument("--model", type=Path, default=REPO / "media/avatar/signer.glb")
    parser.add_argument("--output", type=Path, default=REPO / "media/avatar/reference")
    parser.add_argument("--audit", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    args.output.mkdir(parents=True, exist_ok=True)
    retargeter = ReferenceRetargeter(args.model)
    index_path = args.output / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"signs": {}}
    index.update(version=VERSION, targetModelSha256=retargeter.model_hash)
    if args.ids:
        ids = args.ids
    elif args.all_local:
        ids = sorted(p.stem for p in args.cache.glob("*.json"))
    else:
        html = (REPO / "index.html").read_text(encoding="utf-8")
        listed = set(re.findall(r'data-sign-example="([a-z0-9-]+)"', html))
        catalog = json.loads((REPO / "models/motion-vocabulary.json").read_text(encoding="utf-8"))
        groups = json.loads((REPO / "models/motion-categories/index.json").read_text(encoding="utf-8"))["groups"]
        listed.update(item["id"] for item in catalog["items"] if any(item["label"] in group.get("labels", []) and group["id"] in item.get("cameraGroups", []) for group in groups))
        ids = sorted(id_ for id_ in listed if (REPO / "media/signs" / (id_ + ".mp4")).exists())
    for n, id_ in enumerate(ids, 1):
        data = json.loads((args.cache / (id_ + ".json")).read_text(encoding="utf-8"))
        entry = retargeter.bake(data, args.output, args.audit)
        index["signs"][id_] = entry
        print(f'{n}/{len(ids)} {id_}: {entry["samples"]} samples; hand coverage '
              + ", ".join(f'{side} {entry["quality"]["hands"][side]["coverage"]:.0%}' for side in SIDES), flush=True)
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
