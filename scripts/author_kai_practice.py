"""Bake the five missing Watch & practice gestures directly for Kai's skeleton.

Blender 4.5+: blender --background --factory-startup --python scripts/author_kai_practice.py --

These are hand-authored approximations, NOT new Studio Galt mocap performances.
Only frozen CC0 hand/rest poses are reused from the existing verified clips.
Word-specific paths, orientations and modified V/bent-middle handshapes are
authored here. No reference-video landmarks or recognition models are changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import retarget_studio_galt as rt


REPO = Path(__file__).resolve().parents[1]
FPS = 60
SIDES = ("Left", "Right")
UP = Vector((0, 1, 0))
FORWARD = Vector((0, 0, 1))


def sample_rotations(path: Path, sample: int) -> dict[str, Quaternion]:
    raw = path.read_bytes()
    doc = rt.read_glb(path)
    offset, binary = 12, None
    while offset < len(raw):
        size, kind = struct.unpack_from("<II", raw, offset)
        if kind == 0x004E4942:
            binary = raw[offset + 8:offset + 8 + size]
        offset += 8 + size
    if binary is None:
        raise ValueError("Animation has no embedded buffer: " + str(path))
    result = {}
    animation = doc["animations"][0]
    for channel in animation["channels"]:
        if channel["target"]["path"] != "rotation":
            raise ValueError("Expected rotation-only template")
        accessor = doc["accessors"][animation["samplers"][channel["sampler"]]["output"]]
        if accessor["componentType"] != 5126 or accessor["type"] != "VEC4" or not 0 <= sample < accessor["count"]:
            raise ValueError("Invalid hand template sample")
        view = doc["bufferViews"][accessor["bufferView"]]
        start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0) + sample * 16
        x, y, z, w = struct.unpack_from("<4f", binary, start)
        result[doc["nodes"][channel["target"]["node"]]["name"]] = Quaternion((w, x, y, z)).normalized()
    return result


class KaiAuthor:
    def __init__(self, model: Path, clips: Path):
        self.model = model
        self.target = rt.read_glb(model)
        self.names, self.parents, self.order, self.bind = rt.target_rig(self.target)
        self.bind_local = {i: rt.local_matrix(node).to_quaternion().normalized()
                           for i, node in enumerate(self.target["nodes"])}
        index = json.loads((clips / "index.json").read_text(encoding="utf-8"))
        self.template_sources = []

        def frozen(sign, sample):
            entry = index["signs"][sign]
            path = clips / entry["file"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError("Unverified static template: " + str(path))
            if entry["source"]["kind"] != "studio-galt" or entry["license"] != "CC0-1.0":
                raise ValueError("Only the verified CC0 static templates may be reused")
            if entry["targetModelSha256"] != hashlib.sha256(model.read_bytes()).hexdigest():
                raise ValueError("Template was baked for a different Kai model")
            self.template_sources.append({"id": sign, "file": entry["file"], "sha256": entry["sha256"],
                                          "sample": sample, "sourceFrame": sample + entry["sourceFrameRange"][0],
                                          "license": "CC0-1.0", "source": entry["source"]})
            return sample_rotations(path, sample)

        neutral = frozen("hello", 0)
        self.neutral = {self.names[name]: q for name, q in neutral.items()}
        self.neutral_world = self.world(self.neutral)
        self.neutral_q = {i: m.to_quaternion().normalized() for i, m in self.neutral_world.items()}
        self.hand_offsets, self.finger_offsets = {}, {}
        for side in SIDES:
            hand = side + "Hand"
            palm = rt.palm_frame(*(self.bind[self.names[hand + part]].translation
                                   for part in ("", "Index1", "Middle1", "Pinky1")))
            self.hand_offsets[side] = self.bind[self.names[hand]].to_quaternion().inverted() @ palm
            for digit in rt.FINGERS:
                for joint in (1, 2, 3):
                    name = hand + digit + str(joint)
                    direction = (self.bind[self.names[hand + digit + str(joint + 1)]].translation
                                 - self.bind[self.names[name]].translation)
                    frame = rt.finger_frame(direction, palm @ Vector((0, 0, 1)))
                    self.finger_offsets[name] = self.bind[self.names[name]].to_quaternion().inverted() @ frame
        flat = frozen("hello", 48)
        pointing = frozen("brother", 136)
        right_fingers = [name for name in rt.MAPPED if name.startswith("RightHand") and name != "RightHand"]
        relaxed = {name: neutral[name].copy() for name in right_fingers}
        b_hand = {name: flat[name].copy() for name in right_fingers}
        point = {name: (flat[name] if "Thumb" in name else pointing[name]).copy() for name in right_fingers}
        v_hand = {name: (flat[name] if any(d in name for d in ("Index", "Middle", "Thumb")) else point[name]).copy()
                  for name in right_fingers}
        self.rotate_digit(v_hand, "Index", [(1, "z", -13)])
        self.rotate_digit(v_hand, "Middle", [(1, "z", 7)])
        bent_middle = {name: b_hand[name].copy() for name in right_fingers}
        for digit, angle in (("Index", -18), ("Ring", 13), ("Pinky", 25)):
            self.rotate_digit(bent_middle, digit, [(1, "z", angle)])
        self.rotate_digit(bent_middle, "Middle", [(1, "x", 48), (2, "x", 18), (3, "x", 10)])
        self.shapes = {}
        for name, right in (("relaxed", relaxed), ("flat", b_hand), ("point", point),
                            ("v", v_hand), ("bent-middle", bent_middle)):
            self.shapes[name] = {"Right": right, "Left": self.mirror_shape(right)}
        self.rest = {side: {"wrist": self.neutral_world[self.names[side + "Hand"]].translation.copy(),
                            "rotation": self.neutral_q[self.names[side + "Hand"]].copy(), "shape": "relaxed"}
                     for side in SIDES}

    def world(self, locals_: dict) -> dict:
        world = {}
        for i in self.order:
            parent = self.parents.get(i)
            loc, q, scale = rt.local_matrix(self.target["nodes"][i]).decompose()
            world[i] = (world[parent] if parent is not None else Matrix.Identity(4)) @ Matrix.LocRotScale(
                loc, locals_.get(i, q).normalized(), scale)
        return world

    def shape_world(self, right: dict) -> dict:
        return self.world({**self.neutral, **{self.names[name]: q for name, q in right.items()}})

    def rotate_digit(self, shape, digit, edits):
        # Apply a semantic palm-axis bend/spread, not an exporter-specific Euler axis.
        for joint, axis, angle in edits:
            world = self.shape_world(shape)
            palm = rt.palm_frame(*(world[self.names["RightHand" + part]].translation
                                   for part in ("", "Index1", "Middle1", "Pinky1")))
            name = "RightHand" + digit + str(joint)
            parent = self.parents[self.names[name]]
            local_axis = world[parent].to_quaternion().inverted() @ (palm @ Vector((1, 0, 0) if axis == "x" else (0, 0, 1)))
            shape[name] = (Quaternion(local_axis, math.radians(angle)) @ shape[name]).normalized()

    def mirror_shape(self, right: dict) -> dict:
        # Reflect anatomical directions, then reapply LEFT bind-axis offsets.
        # Raw right-hand local quaternions are not compatible with Kai's left hand.
        world = self.shape_world(right)
        reflect = lambda p: Vector((-p.x, p.y, p.z))
        palm = rt.palm_frame(*(reflect(world[self.names["RightHand" + part]].translation)
                               for part in ("", "Index1", "Middle1", "Pinky1")))
        desired = {"LeftHand": (palm @ self.hand_offsets["Left"].inverted()).normalized()}
        result = {}
        for digit in rt.FINGERS:
            for joint in (1, 2, 3):
                name = "LeftHand" + digit + str(joint)
                source = "RightHand" + digit + str(joint)
                following = "RightHand" + digit + str(joint + 1)
                direction = reflect(world[self.names[following]].translation - world[self.names[source]].translation)
                desired[name] = (rt.finger_frame(direction, palm @ Vector((0, 0, 1)))
                                 @ self.finger_offsets[name].inverted()).normalized()
                parent = self.target["nodes"][self.parents[self.names[name]]]["name"]
                result[name] = (desired[parent].inverted() @ desired[name]).normalized()
        return result

    def pose(self, side, wrist, direction, palm_normal, shape="flat"):
        y = Vector(direction).normalized()
        z = Vector(palm_normal) * (1 if side == "Right" else -1)
        z = (z - y * z.dot(y)).normalized()
        x = y.cross(z).normalized()
        palm = Matrix((x, y, z)).transposed().to_quaternion().normalized()
        return {"wrist": Vector(wrist), "rotation": (palm @ self.hand_offsets[side].inverted()).normalized(), "shape": shape}

    def at_tip(self, side, tip, direction, palm_normal, shape, digit):
        pose = self.pose(side, (0, 0, 0), direction, palm_normal, shape)
        locals_ = {**self.neutral, **{self.names[name]: q for name, q in self.shapes[shape][side].items()}}
        hand = self.names[side + "Hand"]
        parent_q = self.neutral_q[self.parents[hand]]
        locals_[hand] = parent_q.inverted() @ pose["rotation"]
        world = self.world(locals_)
        offset = world[self.names[side + "Hand" + digit + "4"]].translation - world[hand].translation
        pose["wrist"] = Vector(tip) - offset
        return pose

    def specs(self):
        head = self.neutral_world[self.names["Head"]].translation
        eye = self.neutral_world[self.names["RightEye"]].translation
        hips = self.neutral_world[self.names["Hips"]].translation
        keys = lambda t, right=None, left=None: {"time": t, "Right": right or self.rest["Right"], "Left": left or self.rest["Left"]}

        fish_keys = [keys(0), keys(.25)]
        for time, x, yaw in ((.65, -.26, 0), (.9, -.21, -22), (1.2, -.135, 22), (1.5, -.06, -22),
                             (1.8, .025, 22), (2.1, .04, -18), (2.3, .04, 0)):
            turn = Quaternion(UP, math.radians(yaw))
            fish_keys.append(keys(time, self.pose("Right", (x, head.y - .3, .33), turn @ Vector((1, 0, 0)),
                                                  turn @ -FORWARD)))
        fish_keys += [keys(2.85), keys(3.1)]

        pain_keys = [keys(0), keys(.2)]
        for time, twist, gap in ((.7, 0, .035), (1.0, 55, .02), (1.3, -25, .035),
                                 (1.6, 55, .02), (1.9, -25, .035), (2.15, 0, .035)):
            hands = {}
            for side, sign in (("Right", -1), ("Left", 1)):
                direction = Vector((-sign, 0, 0))
                normal = Quaternion(direction, math.radians(twist)) @ UP
                hands[side] = self.at_tip(side, (sign * gap, head.y - .3, .34), direction, normal, "point", "Index")
            pain_keys.append(keys(time, hands["Right"], hands["Left"]))
        pain_keys += [keys(2.75), keys(3.0)]

        see_tip = eye + Vector((-.016, .005, .085))
        see_start = self.at_tip("Right", see_tip, UP, -FORWARD, "v", "Index")
        see_out = self.at_tip("Right", see_tip + Vector((.025, -.035, .235)), UP, -FORWARD, "v", "Index")
        see_keys = [keys(0), keys(.2), keys(.8, see_start), keys(1.05, see_start),
                    keys(1.65, see_out), keys(1.95, see_out), keys(2.55), keys(2.8)]

        forehead = eye + Vector((.03, .058, .065))
        stomach = Vector((.025, hips.y + .20, .19))
        sick_right = self.at_tip("Right", forehead, UP, -FORWARD, "bent-middle", "Middle")
        sick_left = self.at_tip("Left", stomach, UP, -FORWARD, "bent-middle", "Middle")
        sick_keys = [keys(0), keys(.2), keys(.9, sick_right, sick_left), keys(1.65, sick_right, sick_left),
                     keys(1.85, sick_right, sick_left), keys(2.55), keys(2.8)]

        support = self.pose("Left", (.12, head.y - .4, .32), (-1, 0, 0), -UP)
        horizon = self.pose("Right", (-.035, head.y - .285, .405), (1, 0, 0), -UP)
        down = self.pose("Right", (-.035, head.y - .345, .405), (.22, -.9755, 0), (-.9755, -.22, 0))
        night_keys = [keys(0), keys(.2), keys(.75, horizon, support), keys(1.0, horizon, support),
                      keys(1.65, down, support), keys(1.95, down, support), keys(2.65), keys(2.9)]
        return {
            "fish": {"keys": fish_keys, "keyPoseSamples": [72, 108],
                     "gesture": "Upright flat dominant hand swims sideways with alternating wrist turns."},
            "pain": {"keys": pain_keys, "keyPoseSamples": [60, 96],
                     "gesture": "Two extended index fingers approach each other and twist at chest level (general PAIN/HURT)."},
            "see": {"keys": see_keys, "keyPoseSamples": [48, 99],
                    "gesture": "Dominant V-hand starts near the eye and travels forward."},
            "sick": {"keys": sick_keys, "keyPoseSamples": [54, 99],
                     "gesture": "Bent middle fingers indicate the forehead and stomach; other fingers stay open."},
            "night": {"keys": night_keys, "keyPoseSamples": [45, 99],
                      "gesture": "Dominant flat hand descends over a horizontal nondominant hand (sun below horizon)."},
        }

    def bake(self, id_, spec, output: Path):
        keys = spec["keys"]
        times = [i / FPS for i in range(round(keys[-1]["time"] * FPS) + 1)]
        tracks = {self.names[name]: [] for name in rt.MAPPED}
        previous, previous_poles = {}, {}
        max_error, max_step = 0.0, 0.0
        k = 0
        for time in times:
            while k < len(keys) - 2 and time > keys[k + 1]["time"]:
                k += 1
            a, b = keys[k], keys[k + 1]
            u = max(0.0, min(1.0, (time - a["time"]) / (b["time"] - a["time"])))
            u = u ** 3 * (u * (u * 6 - 15) + 10)  # C2 easing; no starts/stops with rotation spikes.
            desired = {i: self.neutral_q[i].copy() for i in tracks if not self.target["nodes"][i]["name"].startswith(("LeftHand", "RightHand"))}
            fingers = {}
            goals = {}
            for side, sign in (("Left", 1), ("Right", -1)):
                start, end = a[side], b[side]
                wrist = start["wrist"].lerp(end["wrist"], u)
                hand = self.names[side + "Hand"]
                desired[hand] = start["rotation"].slerp(end["rotation"], u).normalized()
                for name, q in self.shapes[start["shape"]][side].items():
                    fingers[self.names[name]] = q.slerp(self.shapes[end["shape"]][side][name], u).normalized()
                arm, forearm = (self.names[side + part] for part in ("Arm", "ForeArm"))
                shoulder = self.neutral_world[arm].translation
                old_upper = self.neutral_world[forearm].translation - shoulder
                old_lower = self.neutral_world[hand].translation - self.neutral_world[forearm].translation
                pole = shoulder + Vector((sign * .8, -.55, -.12))
                elbow, solved_wrist, bend = rt.fit_arm(shoulder, wrist, pole, old_upper.length, old_lower.length, previous_poles.get(side))
                previous_poles[side] = bend
                desired[arm] = (old_upper.rotation_difference(elbow - shoulder) @ self.neutral_q[arm]).normalized()
                desired[forearm] = (old_lower.rotation_difference(solved_wrist - elbow) @ self.neutral_q[forearm]).normalized()
                goals[hand] = wrist
            locals_, world_q = {}, {}
            for i in self.order:
                parent = self.parents.get(i)
                parent_q = world_q[parent] if parent is not None else Quaternion()
                local = fingers.get(i, self.bind_local[i])
                world_q[i] = desired.get(i, parent_q @ local)
                q = (parent_q.inverted() @ world_q[i]).normalized()
                locals_[i] = q
                if i not in tracks:
                    continue
                if i in previous:
                    if previous[i].dot(q) < 0:
                        q.negate()
                    max_step = max(max_step, 2 * math.acos(min(1, max(-1, previous[i].dot(q)))))
                previous[i] = q.copy()
                tracks[i].extend([q.x, q.y, q.z, q.w])
            world = self.world(locals_)
            for side, sign in (("Left", 1), ("Right", -1)):
                if sign * world[self.names[side + "ForeArm"]].translation.x < .10:
                    raise ValueError(f"{id_}: {side} elbow entered torso at {time:.3f} seconds")
            max_error = max(max_error, max((world[i].translation - goal).length for i, goal in goals.items()))
        if max_error > .00001:
            raise ValueError(f"{id_}: wrist path is unreachable ({max_error:.5f} m)")
        if max_step > math.radians(15):
            raise ValueError(f"{id_}: rotation spike ({math.degrees(max_step):.2f} degrees)")
        metadata = {
            "id": id_, "label": id_.upper(), "language": "ASL", "license": "project-authored",
            "source": {"name": "HandSpeak", "kind": "authored", "script": "scripts/author_kai_practice.py",
                       "description": spec["gesture"], "staticPoseTemplates": self.template_sources},
            "approximation": True, "targetModelSha256": hashlib.sha256(self.model.read_bytes()).hexdigest(),
            "targetModelLicense": "CC-BY-4.0", "fps": FPS, "duration": times[-1], "frameCount": len(times),
            "mappedBones": rt.MAPPED, "fingerJointCount": 30, "includesFingers": True,
            "faceMotion": False, "rootMotion": False, "retargeted": True, "independentTiming": True,
            "learningOnly": False, "referenceVideo": f"media/signs/{id_}.mp4",
            "lessonUrl": f"https://www.lifeprint.com/asl101/pages-signs/{'h' if id_ == 'pain' else id_[0]}/{'hurt' if id_ == 'pain' else id_}.htm",
            "keyPoseSamples": spec["keyPoseSamples"], "maxWristTargetErrorM": max_error,
            "maxLocalStepDegrees": math.degrees(max_step), "maxPoleStepDegrees": 8,
            "method": "Word-specific hand-authored wrist paths and palm frames, mirrored anatomical static finger templates, eased quaternion interpolation and outward/down two-bone IK; Kai-native rotation-only tracks",
            "reviewNote": "Stylized learning approximation, not captured ASL or a frame-matched copy of the reference. Sign variants and contact details should be checked with the video/lesson. No captured facial grammar or new camera model.",
        }
        file = output / (id_ + "-kai-authored.glb")
        rt.write_glb(self.target, tracks, times, file, metadata, generator="HandSpeak Kai hand-authored animator v1")
        return {**metadata, "file": file.name, "bytes": file.stat().st_size,
                "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=REPO / "media/avatar/signer.glb")
    parser.add_argument("--output", type=Path, default=REPO / "media/avatar/clips")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    author = KaiAuthor(args.model, args.output)
    index_path = args.output / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    for id_, spec in author.specs().items():
        entry = author.bake(id_, spec, args.output)
        index["signs"][id_] = entry
        print(json.dumps({"id": id_, "frames": entry["frameCount"], "duration": entry["duration"],
                          "maxWristErrorM": entry["maxWristTargetErrorM"], "maxStepDegrees": entry["maxLocalStepDegrees"]}), flush=True)
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print("Kai authored index: " + str(index_path), flush=True)


if __name__ == "__main__":
    main()
