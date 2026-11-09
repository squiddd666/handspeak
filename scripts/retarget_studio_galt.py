"""Bake Studio Galt's Mixamo FBX rotations into Kai-native, animation-only GLBs.

Run inside Blender 4.5+: blender --background --python scripts/retarget_studio_galt.py --
Run fetch_studio_galt.py first. This keeps Kai's original mesh/materials untouched.
World-space rest-pose correction avoids copying incompatible FBX local Euler axes.
The FBX export's initial calibration/T-pose frame is omitted. Root translation and
leg motion are deliberately excluded; all thirty weighted finger joints are kept.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector


REPO = Path(__file__).resolve().parents[1]
B2G = Quaternion((1, 0, 0), -math.pi / 2)
G2B = B2G.inverted()
FINGERS = ("Thumb", "Index", "Middle", "Ring", "Pinky")
BODY = ["Spine", "Spine1", "Spine2", "Neck", "Head"]
MAPPED = BODY + [side + part for side in ("Left", "Right") for part in ("Shoulder", "Arm", "ForeArm", "Hand")]
MAPPED += [side + "Hand" + finger + str(j) for side in ("Left", "Right") for finger in FINGERS for j in (1, 2, 3)]


def read_glb(path: Path) -> dict:
    raw = path.read_bytes()
    if len(raw) < 20 or struct.unpack_from("<4sII", raw) != (b"glTF", 2, len(raw)):
        raise ValueError("Expected a complete glTF 2 GLB: " + str(path))
    offset = 12
    while offset < len(raw):
        length, kind = struct.unpack_from("<II", raw, offset)
        if kind == 0x4E4F534A:
            return json.loads(raw[offset + 8:offset + 8 + length])
        offset += 8 + length
    raise ValueError("GLB has no JSON chunk")


def local_matrix(node: dict) -> Matrix:
    if "matrix" in node:
        flat = node["matrix"]
        return Matrix([[flat[col * 4 + row] for col in range(4)] for row in range(4)])
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    return Matrix.LocRotScale(Vector(node.get("translation", [0, 0, 0])), Quaternion((w, x, y, z)), Vector(node.get("scale", [1, 1, 1])))


def target_rig(gltf: dict):
    nodes = gltf["nodes"]
    parents = {child: i for i, node in enumerate(nodes) for child in node.get("children", [])}
    names = {node.get("name"): i for i, node in enumerate(nodes)}
    missing = [name for name in MAPPED if name not in names]
    if missing:
        raise ValueError("Kai is missing required joints: " + ", ".join(missing))
    order, world = [], {}

    def visit(i):
        if i in world:
            return
        parent = parents.get(i)
        if parent is not None:
            visit(parent)
        world[i] = (world[parent] if parent is not None else Matrix.Identity(4)) @ local_matrix(nodes[i])
        order.append(i)

    for i in range(len(nodes)):
        visit(i)
    return names, parents, order, world


def body_basis(left: Vector, right: Vector, head: Vector, hips: Vector) -> Matrix:
    x = (left - right).normalized()
    up = head - hips
    up = (up - x * up.dot(x)).normalized()
    forward = x.cross(up).normalized()
    return Matrix((x, up, forward)).transposed()


def canonical(name: str) -> str:
    return re.sub(r"^mixamorig\d*[:_]?", "", name)


def palm_frame(wrist: Vector, index: Vector, middle: Vector, pinky: Vector) -> Quaternion:
    """Anatomical palm axes, independent of either exporter's joint roll."""
    y = (middle - wrist).normalized()
    x = index - pinky
    x = (x - y * x.dot(y)).normalized()
    z = x.cross(y).normalized()
    return Matrix((x, y, z)).transposed().to_quaternion().normalized()


def finger_frame(direction: Vector, palm_normal: Vector) -> Quaternion:
    y = direction.normalized()
    z = palm_normal - y * palm_normal.dot(y)
    if z.length_squared < 1e-10:
        fallback = Vector((1, 0, 0)) if abs(y.x) < 0.9 else Vector((0, 1, 0))
        z = fallback - y * fallback.dot(y)
    z.normalize()
    x = y.cross(z).normalized()
    return Matrix((x, y, z)).transposed().to_quaternion().normalized()


def posed_matrices(target: dict, parents: dict, order: list, rotations: dict) -> dict:
    world = {}
    for i in order:
        parent = parents.get(i)
        pm = world[parent] if parent is not None else Matrix.Identity(4)
        loc, local_q, scale = local_matrix(target["nodes"][i]).decompose()
        if i in rotations:
            local_q = pm.to_quaternion().inverted() @ rotations[i]
        world[i] = pm @ Matrix.LocRotScale(loc, local_q.normalized(), scale)
    return world


def fit_arm(shoulder: Vector, wrist: Vector, pole: Vector, upper: float, lower: float, previous: Vector | None = None) -> tuple[Vector, Vector, Vector]:
    """Analytic two-bone IK, retaining the captured elbow bend plane."""
    direction = wrist - shoulder
    distance = max(direction.length, 1e-8)
    axis = direction / distance
    reachable = min(upper + lower - 1e-6, max(abs(upper - lower) + 1e-6, distance))
    wrist = shoulder + axis * reachable
    along = (upper * upper + reachable * reachable - lower * lower) / (2 * reachable)
    height = math.sqrt(max(0, upper * upper - along * along))
    bend = pole - shoulder
    bend -= axis * bend.dot(axis)
    if bend.length_squared < 1e-10:
        fallback = Vector((1, 0, 0)) if abs(axis.x) < 0.9 else Vector((0, 0, 1))
        bend = fallback - axis * fallback.dot(axis)
    bend.normalize()
    if previous is not None:
        prior = previous - axis * previous.dot(axis)
        if prior.length_squared > 1e-10:
            prior.normalize()
            change = prior.rotation_difference(bend)
            if change.angle > math.radians(8):
                bend = Quaternion().slerp(change, math.radians(8) / change.angle) @ prior
    elbow = shoulder + axis * along + bend * height
    return elbow, wrist, bend


def elbow_direction(source_shoulder: Vector, source_elbow: Vector, source_wrist: Vector,
                    align: Quaternion, target_axis: Vector, outward: Vector, forward: Vector) -> Vector:
    """Transfer a shoulder-relative bend plane, regularizing near-straight arms.

    A millimetre-scale inward bend is harmless on the source's almost straight
    arm, but Kai's different proportions amplify it enough to put an elbow
    inside the torso. Prefer an anatomical outward/back pole at low flexion;
    use the captured plane fully once the source elbow is meaningfully bent.
    Neither the wrist path nor any captured palm/finger rotation is changed.
    """
    upper = source_elbow - source_shoulder
    lower = source_wrist - source_elbow
    source_axis = (source_wrist - source_shoulder).normalized()
    neutral = outward - forward * 0.15
    neutral -= target_axis * neutral.dot(target_axis)
    neutral.normalize()
    captured = upper - source_axis * upper.dot(source_axis)
    captured = B2G @ (align @ captured)
    captured -= target_axis * captured.dot(target_axis)
    if captured.length_squared < 1e-12:
        return neutral
    captured.normalize()
    flexion = math.acos(max(-1, min(1, upper.normalized().dot(lower.normalized()))))
    blend = max(0, min(1, (flexion - math.radians(15)) / math.radians(20)))
    blend = blend * blend * (3 - 2 * blend)
    # Rotate within the bend plane instead of linearly mixing antipodal poles.
    angle = math.atan2(target_axis.dot(neutral.cross(captured)), neutral.dot(captured))
    return (Quaternion(target_axis, angle * blend) @ neutral).normalized()


def add_floats(gltf: dict, buffer: bytearray, values: list[float], kind: str, count: int, bounds=False) -> int:
    while len(buffer) % 4:
        buffer.append(0)
    data = struct.pack("<" + str(len(values)) + "f", *values)
    view = len(gltf["bufferViews"])
    gltf["bufferViews"].append({"buffer": 0, "byteOffset": len(buffer), "byteLength": len(data)})
    buffer.extend(data)
    accessor = {"bufferView": view, "componentType": 5126, "count": count, "type": kind}
    if bounds:
        stored = struct.unpack("<" + str(len(values)) + "f", data)
        accessor.update(min=[min(stored)], max=[max(stored)])
    index = len(gltf["accessors"])
    gltf["accessors"].append(accessor)
    return index


def write_glb(target: dict, tracks: dict, times: list[float], output: Path, metadata: dict,
              generator: str = "HandSpeak StudioGalt-to-Kai retargeter v1") -> None:
    # Include only the original rig nodes and their ancestors, never another mesh.
    selected = set(target["skins"][0]["joints"])
    parents = {c: i for i, n in enumerate(target["nodes"]) for c in n.get("children", [])}
    for i in list(selected):
        while i in parents:
            i = parents[i]
            selected.add(i)
    order = sorted(selected)
    remap = {old: new for new, old in enumerate(order)}
    nodes = []
    for old in order:
        n = target["nodes"][old]
        copy = {key: n[key] for key in ("name", "translation", "rotation", "scale", "matrix") if key in n}
        children = [remap[c] for c in n.get("children", []) if c in selected]
        if children:
            copy["children"] = children
        nodes.append(copy)
    gltf = {
        "asset": {"version": "2.0", "generator": generator},
        "scene": 0, "scenes": [{"nodes": [remap[i] for i in order if parents.get(i) not in selected]}],
        "nodes": nodes, "buffers": [], "bufferViews": [], "accessors": [],
        "animations": [{"name": "Sign", "samplers": [], "channels": []}], "extras": metadata,
    }
    buffer = bytearray()
    time_accessor = add_floats(gltf, buffer, times, "SCALAR", len(times), bounds=True)
    animation = gltf["animations"][0]
    for old, values in tracks.items():
        value_accessor = add_floats(gltf, buffer, values, "VEC4", len(times))
        sampler = len(animation["samplers"])
        animation["samplers"].append({"input": time_accessor, "output": value_accessor, "interpolation": "LINEAR"})
        animation["channels"].append({"sampler": sampler, "target": {"node": remap[old], "path": "rotation"}})
    gltf["buffers"] = [{"byteLength": len(buffer)}]
    text = json.dumps(gltf, separators=(",", ":"), ensure_ascii=True).encode()
    text += b" " * (-len(text) % 4)
    buffer.extend(b"\0" * (-len(buffer) % 4))
    length = 12 + 8 + len(text) + 8 + len(buffer)
    output.write_bytes(struct.pack("<4sII", b"glTF", 2, length) + struct.pack("<II", len(text), 0x4E4F534A) + text + struct.pack("<II", len(buffer), 0x004E4942) + buffer)


def bake(item: dict, manifest: dict, cache: Path, model: Path, out: Path) -> dict:
    source = cache / (item["id"] + ".fbx")
    raw = source.read_bytes()
    if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
        raise ValueError("Unverified source FBX: " + str(source))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    fps = manifest["fps"]
    scene.render.fps = fps
    scene.render.fps_base = 1
    bpy.ops.import_scene.fbx(filepath=str(source), use_anim=True, automatic_bone_orientation=False, ignore_leaf_bones=False)
    rigs = [o for o in scene.objects if o.type == "ARMATURE" and o.animation_data and o.animation_data.action]
    if len(rigs) != 1:
        raise ValueError("Expected one animated source armature")
    rig = rigs[0]
    source_bones = {canonical(b.name): b for b in rig.pose.bones}
    missing = [name for name in MAPPED if name not in source_bones]
    if missing:
        raise ValueError("Source lacks body/finger joints: " + ", ".join(missing))
    source_rest = {name: rig.matrix_world @ source_bones[name].bone.matrix_local for name in source_bones}
    target = read_glb(model)
    names, parents, order, target_world = target_rig(target)
    target_q = {i: m.to_quaternion().normalized() for i, m in target_world.items()}
    local_q = {i: local_matrix(n).to_quaternion().normalized() for i, n in enumerate(target["nodes"])}
    target_basis = body_basis(*(G2B @ target_world[names[n]].translation for n in ("LeftArm", "RightArm", "Head", "Hips")))
    source_basis = body_basis(*(source_rest[n].translation for n in ("LeftArm", "RightArm", "Head", "Hips")))
    align = (target_basis @ source_basis.inverted()).to_quaternion().normalized()
    source_q = {name: m.to_quaternion().normalized() for name, m in source_rest.items()}
    # Kai's bind fingers are naturally curled/fanned; Galtis' are not. Merely
    # transferring rest deltas would retain that curl and corrupt flat B-hands.
    # Transfer absolute anatomical palm/finger frames, preserving the original
    # local bone axes via semantic offsets rather than using raw FBX quaternions.
    semantic = {}
    for side in ("Left", "Right"):
        hand = side + "Hand"
        points = (hand, hand + "Index1", hand + "Middle1", hand + "Pinky1")
        spalm = palm_frame(*(source_rest[n].translation for n in points))
        tpalm = palm_frame(*(G2B @ target_world[names[n]].translation for n in points))
        tnode = G2B @ target_q[names[hand]]
        semantic[hand] = (source_q[hand].inverted() @ spalm, tnode.inverted() @ tpalm)
        for finger in FINGERS:
            for j in (1, 2, 3):
                name = hand + finger + str(j)
                following = hand + finger + str(j + 1)
                sdir = source_rest[following].translation - source_rest[name].translation if j < 3 else source_rest[name].to_3x3() @ Vector((0, 1, 0))
                tdir = G2B @ (target_world[names[following]].translation - target_world[names[name]].translation)
                sframe = finger_frame(sdir, spalm @ Vector((0, 0, 1)))
                tframe = finger_frame(tdir, tpalm @ Vector((0, 0, 1)))
                tnode = G2B @ target_q[names[name]]
                semantic[name] = (source_q[name].inverted() @ sframe, tnode.inverted() @ tframe)
    start, end = rig.animation_data.action.frame_range
    start = math.ceil(start) + manifest.get("skipBindFrames", 1)
    end = math.floor(end)
    if end <= start:
        raise ValueError("Source has no motion after its calibration frame")
    if item.get("sourceFrameRange") and item["sourceFrameRange"] != [start, end]:
        raise ValueError("Unexpected source frame range for " + item["id"])
    times = [(f - start) / fps for f in range(start, end + 1)]
    tracks = {names[name]: [] for name in MAPPED}
    previous = {}
    previous_poles = {}
    torso_scale = (target_world[names["Head"]].translation - target_world[names["Hips"]].translation).length / (source_rest["Head"].translation - source_rest["Hips"].translation).length
    max_wrist_error = 0.0
    for frame in range(start, end + 1):
        scene.frame_set(frame)
        desired = {}
        for name in MAPPED:
            posed = (rig.matrix_world @ source_bones[name].matrix).to_quaternion().normalized()
            if name in semantic:
                soffset, toffset = semantic[name]
                desired[names[name]] = (B2G @ align @ posed @ soffset @ toffset.inverted()).normalized()
            else:
                delta = align @ (posed @ source_q[name].inverted()) @ align.inverted()
                desired[names[name]] = (B2G @ delta @ G2B @ target_q[names[name]]).normalized()
        # Rotation-only retargeting loses face/chest contact when arm proportions
        # differ. Preserve captured wrist paths relative to the head and use IK
        # to adapt Kai's fixed arm lengths. This is baked, not a runtime solver.
        proto = posed_matrices(target, parents, order, desired)
        target_head = proto[names["Head"]].translation
        source_head = (rig.matrix_world @ source_bones["Head"].matrix).translation
        neutral_basis = body_basis(proto[names["LeftArm"]].translation,
                                   proto[names["RightArm"]].translation,
                                   target_head, proto[names["Hips"]].translation)
        outward_axis = neutral_basis @ Vector((1, 0, 0))
        forward_axis = neutral_basis @ Vector((0, 0, 1))
        goals = {}
        for side in ("Left", "Right"):
            arm, forearm, hand = (side + part for part in ("Arm", "ForeArm", "Hand"))
            source_wrist = (rig.matrix_world @ source_bones[hand].matrix).translation
            source_elbow = (rig.matrix_world @ source_bones[forearm].matrix).translation
            source_shoulder = (rig.matrix_world @ source_bones[arm].matrix).translation
            goal = target_head + (B2G @ (align @ (source_wrist - source_head))) * torso_scale
            shoulder = proto[names[arm]].translation
            target_axis = (goal - shoulder).normalized()
            bend = elbow_direction(source_shoulder, source_elbow, source_wrist,
                                   align, target_axis,
                                   outward_axis * (1 if side == "Left" else -1), forward_axis)
            pole = shoulder + bend
            old_upper = proto[names[forearm]].translation - shoulder
            old_lower = proto[names[hand]].translation - proto[names[forearm]].translation
            elbow, wrist, bend = fit_arm(shoulder, goal, pole, old_upper.length, old_lower.length, previous_poles.get(side))
            previous_poles[side] = bend
            desired[names[arm]] = (old_upper.rotation_difference(elbow - shoulder) @ desired[names[arm]]).normalized()
            desired[names[forearm]] = (old_lower.rotation_difference(wrist - elbow) @ desired[names[forearm]]).normalized()
            goals[names[hand]] = goal
        solved = posed_matrices(target, parents, order, desired)
        max_wrist_error = max(max_wrist_error, max((solved[i].translation - goal).length for i, goal in goals.items()))
        posed_world = {}
        for i in order:
            parent = parents.get(i)
            parent_q = posed_world[parent] if parent is not None else Quaternion()
            posed_world[i] = desired.get(i, parent_q @ local_q[i])
            if i not in tracks:
                continue
            q = (parent_q.inverted() @ posed_world[i]).normalized()
            if i in previous and previous[i].dot(q) < 0:
                q.negate()
            previous[i] = q.copy()
            tracks[i].extend([q.x, q.y, q.z, q.w])
    metadata = {
        "id": item["id"], "label": item["label"], "language": manifest["language"], "license": manifest["license"],
        "source": {"name": "Studio Galt", "kind": "studio-galt", "repository": manifest["repository"], "commit": manifest["commit"], "path": item["path"], "sha256": item["sha256"], "date": item["date"]},
        "targetModelSha256": hashlib.sha256(model.read_bytes()).hexdigest(), "fps": fps,
        "sourceFrameRange": [start, end], "frameCount": len(times), "duration": times[-1],
        "mappedBones": MAPPED, "fingerJointCount": 30, "includesFingers": True, "faceMotion": False,
        "rootMotion": False, "retargeted": True, "independentTiming": True,
        "learningOnly": item.get("learningOnly", False),
        "referenceVideo": item.get("referenceVideo"), "lessonUrl": item.get("lessonUrl"),
        "maxWristTargetErrorM": max_wrist_error,
        "maxPoleStepDegrees": 8,
        "neutralElbowFlexionDegrees": [15, 35],
        "method": "Aligned body rotation deltas; absolute anatomical palm/finger frames; head-relative wrist paths; shoulder-relative elbow bend planes with outward neutral-extension regularization and two-bone IK; Kai-native rotation-only tracks",
    }
    file = out / (item["id"] + "-studio-galt.glb")
    write_glb(target, tracks, times, file, metadata)
    result = {**metadata, "file": file.name, "bytes": file.stat().st_size, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
    print(json.dumps({"sign": item["label"], "frames": len(times), "duration": times[-1], "bodyAndFingerTracks": len(tracks), "bytes": result["bytes"]}))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("studio-galt-sources.json"))
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--model", type=Path, default=REPO / "media/avatar/signer.glb")
    parser.add_argument("--output", type=Path, default=REPO / "media/avatar/clips")
    arguments = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = parser.parse_args(arguments)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if args.cache is None:
        base = Path(os.environ["LOCALAPPDATA"]) / "HandSpeak" if os.environ.get("LOCALAPPDATA") else Path.home() / ".cache/handspeak"
        args.cache = base / "mocap-cache/studio-galt" / manifest["commit"]
    args.output.mkdir(parents=True, exist_ok=True)
    index_path = args.output / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"version": 1, "signs": {}}
    for item in manifest["clips"]:
        index["signs"][item["id"]] = bake(item, manifest, args.cache, args.model, args.output)
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print("Kai mocap index: " + str(index_path))


if __name__ == "__main__":
    main()
