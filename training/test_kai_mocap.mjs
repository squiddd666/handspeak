/** Offline asset/player regression checks. No browser, GPU or npm install needed. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {join} from 'node:path';
import vm from 'node:vm';

const repo = fileURLToPath(new URL('../', import.meta.url));
const read = (path) => readFileSync(join(repo, path));
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');
const manifest = JSON.parse(read('scripts/studio-galt-sources.json'));
const index = JSON.parse(read('media/avatar/clips/index.json'));
const avatarSource = read('sign-avatar.js').toString();
const clipSource = read('sign-clips.js').toString();

function glb(bytes) {
  assert.equal(bytes.toString('ascii', 0, 4), 'glTF');
  assert.equal(bytes.readUInt32LE(4), 2);
  assert.equal(bytes.readUInt32LE(8), bytes.length);
  let json, bin;
  for (let offset = 12; offset < bytes.length;) {
    const size = bytes.readUInt32LE(offset), kind = bytes.readUInt32LE(offset + 4);
    assert.equal(size % 4, 0);
    assert.ok(offset + 8 + size <= bytes.length);
    const chunk = bytes.subarray(offset + 8, offset + 8 + size);
    if (kind === 0x4e4f534a) json = JSON.parse(chunk.toString());
    if (kind === 0x004e4942) bin = chunk;
    offset += 8 + size;
  }
  assert.ok(json && bin);
  return {json, bin};
}

function floats(data, accessorIndex) {
  const accessor = data.json.accessors[accessorIndex];
  assert.equal(accessor.componentType, 5126);
  assert.ok(!accessor.sparse);
  const view = data.json.bufferViews[accessor.bufferView];
  assert.equal(view.buffer, 0);
  const width = {SCALAR: 1, VEC4: 4}[accessor.type];
  assert.ok(width);
  const offset = (view.byteOffset || 0) + (accessor.byteOffset || 0);
  const count = accessor.count * width;
  assert.ok(offset + count * 4 <= data.bin.length);
  return Array.from({length: count}, (_, i) => data.bin.readFloatLE(offset + i * 4));
}

const kaiBytes = read('media/avatar/signer.glb');
const kai = glb(kaiBytes);
const kaiNodes = new Map(kai.json.nodes.map((node) => [node.name, node]));
const body = ['Spine', 'Spine1', 'Spine2', 'Neck', 'Head'];
const fingers = [];
for (const side of ['Left', 'Right']) {
  for (const part of ['Shoulder', 'Arm', 'ForeArm', 'Hand']) body.push(side + part);
  for (const digit of ['Thumb', 'Index', 'Middle', 'Ring', 'Pinky']) {
    for (const joint of [1, 2, 3]) fingers.push(`${side}Hand${digit}${joint}`);
  }
}
const expectedBones = [...body, ...fingers].sort();
const authoredIds = ['fish', 'pain', 'see', 'sick', 'night'];

function multiplyMatrices(a, b) {
  return Array.from({length: 16}, (_, i) => {
    const row = i % 4, column = Math.floor(i / 4);
    let result = 0;
    for (let k = 0; k < 4; k++) result += a[k * 4 + row] * b[column * 4 + k];
    return result;
  });
}
function nodeMatrix(node, rotation) {
  if (node.matrix && !rotation) return node.matrix;
  const [x, y, z, w] = rotation || node.rotation || [0, 0, 0, 1];
  const [sx, sy, sz] = node.scale || [1, 1, 1];
  const [tx, ty, tz] = node.translation || [0, 0, 0];
  return [
    (1 - 2 * (y * y + z * z)) * sx, 2 * (x * y + w * z) * sx, 2 * (x * z - w * y) * sx, 0,
    2 * (x * y - w * z) * sy, (1 - 2 * (x * x + z * z)) * sy, 2 * (y * z + w * x) * sy, 0,
    2 * (x * z + w * y) * sz, 2 * (y * z - w * x) * sz, (1 - 2 * (x * x + y * y)) * sz, 0,
    tx, ty, tz, 1,
  ];
}
function rigPositions(rotations = new Map()) {
  const parents = new Map();
  kai.json.nodes.forEach((node, i) => node.children?.forEach((child) => parents.set(child, i)));
  const matrices = new Map();
  function world(i) {
    if (!matrices.has(i)) {
      const node = kai.json.nodes[i], local = nodeMatrix(node, rotations.get(node.name));
      matrices.set(i, parents.has(i) ? multiplyMatrices(world(parents.get(i)), local) : local);
    }
    return matrices.get(i);
  }
  return new Map(kai.json.nodes.map((node, i) => [node.name, world(i).slice(12, 15)]));
}
const minus = (a, b) => a.map((value, i) => value - b[i]);
const dot = (a, b) => a.reduce((result, value, i) => result + value * b[i], 0);
const length = (v) => Math.hypot(...v);
const bindPositions = rigPositions();

function rotationsAt(data, sample) {
  const animation = data.json.animations[0];
  return new Map(animation.channels.map((channel) => {
    const values = floats(data, animation.samplers[channel.sampler].output);
    return [data.json.nodes[channel.target.node].name, values.slice(sample * 4, sample * 4 + 4)];
  }));
}
function authoredPositions(id, sample) {
  return rigPositions(rotationsAt(glb(read(`media/avatar/clips/${index.signs[id].file}`)), sample));
}

for (const source of manifest.clips) {
  test(`${source.label}: pinned animation-only asset, Kai bind axes and native fingers`, () => {
    const entry = index.signs[source.id];
    const bytes = read(`media/avatar/clips/${entry.file}`);
    const data = glb(bytes), doc = data.json;
    assert.equal(bytes.length, entry.bytes);
    assert.equal(sha256(bytes), entry.sha256);
    assert.equal(entry.targetModelSha256, sha256(kaiBytes));
    assert.equal(entry.source.commit, manifest.commit);
    assert.equal(entry.source.sha256, source.sha256);
    assert.equal(entry.source.path, source.path);
    assert.equal(entry.language, 'ASL');
    assert.equal(entry.license, 'CC0-1.0');
    assert.deepEqual(entry.sourceFrameRange, source.sourceFrameRange);
    assert.equal(entry.sourceFrameRange[0], 2, 'omit the initial T-pose');
    assert.equal(entry.frameCount, source.sourceFrameRange[1] - source.sourceFrameRange[0] + 1);
    assert.equal(entry.fps, 60);
    assert.equal(entry.duration, (entry.frameCount - 1) / 60);
    assert.equal(entry.retargeted, true);
    assert.equal(entry.independentTiming, true);
    assert.equal(entry.includesFingers, true);
    assert.equal(entry.learningOnly, source.learningOnly);
    assert.equal(entry.referenceVideo, source.referenceVideo);
    assert.equal(entry.lessonUrl, source.lessonUrl || null);
    assert.equal(entry.fingerJointCount, 30);
    assert.equal(entry.faceMotion, false);
    assert.equal(entry.rootMotion, false);
    assert.ok(entry.maxWristTargetErrorM < 0.00001);
    assert.equal(entry.maxPoleStepDegrees, 8);
    assert.deepEqual(entry.neutralElbowFlexionDegrees, [15, 35]);
    for (const field of ['meshes', 'materials', 'images', 'textures', 'skins']) {
      assert.equal(doc[field], undefined, `no imported ${field}`);
    }
    for (const node of doc.nodes) {
      const original = kaiNodes.get(node.name);
      assert.ok(original, `unknown target node ${node.name}`);
      for (const field of ['translation', 'rotation', 'scale', 'matrix']) {
        assert.deepEqual(node[field], original[field], `${node.name} ${field}`);
      }
    }
    assert.equal(doc.animations.length, 1);
    const animation = doc.animations[0];
    assert.equal(animation.channels.length, 43);
    assert.deepEqual(animation.channels.map((c) => doc.nodes[c.target.node].name).sort(), expectedBones);
    let maximumBodyStep = 0, maximumFingerStep = 0, movingTracks = 0;
    for (const channel of animation.channels) {
      assert.equal(channel.target.path, 'rotation');
      const sampler = animation.samplers[channel.sampler];
      assert.equal(sampler.interpolation, 'LINEAR');
      const times = floats(data, sampler.input), values = floats(data, sampler.output);
      assert.equal(times.length, entry.frameCount);
      assert.equal(values.length, times.length * 4);
      for (let i = 0; i < times.length; i++) {
        assert.ok(Number.isFinite(times[i]));
        assert.ok(Math.abs(times[i] - i / 60) < 0.000001);
        const q = values.slice(i * 4, i * 4 + 4);
        assert.ok(q.every(Number.isFinite));
        assert.ok(Math.abs(Math.hypot(...q) - 1) < 0.000002);
        if (i) {
          const previous = values.slice((i - 1) * 4, i * 4);
          const dot = q.reduce((sum, value, j) => sum + value * previous[j], 0);
          assert.ok(dot >= 0, 'quaternion hemispheres must be continuous');
          const step = 2 * Math.acos(Math.min(1, dot));
          if (fingers.includes(doc.nodes[channel.target.node].name)) maximumFingerStep = Math.max(maximumFingerStep, step);
          else maximumBodyStep = Math.max(maximumBodyStep, step);
        }
      }
      if (values.some((value, i) => Math.abs(value - values[i % 4]) > 0.001)) movingTracks++;
    }
    assert.ok(movingTracks > 20, 'body and fingers must contain actual motion');
    assert.ok(maximumBodyStep < Math.PI / 12, `body rotation spike: ${maximumBodyStep * 180 / Math.PI} degrees`);
    if (source.nativeFingerPeak) {
      // These two releases are equally fast in the pinned source FBXs. Preserve
      // captured hand motion rather than confusing it with an IK/elbow flip.
      assert.ok(Math.abs(maximumFingerStep * 180 / Math.PI - source.nativeFingerPeak.degrees) < 0.01);
    } else {
      assert.ok(maximumFingerStep < Math.PI / 12, `finger rotation spike: ${maximumFingerStep * 180 / Math.PI} degrees`);
    }
  });

  test(`${source.label}: initial and finished poses keep elbows outside the torso`, () => {
    const entry = index.signs[source.id], data = glb(read(`media/avatar/clips/${entry.file}`));
    const animation = data.json.animations[0];
    for (const sample of [0, entry.frameCount - 1]) {
      const rotations = new Map(animation.channels.map((channel) => {
        const values = floats(data, animation.samplers[channel.sampler].output);
        return [data.json.nodes[channel.target.node].name, values.slice(sample * 4, sample * 4 + 4)];
      }));
      const positions = rigPositions(rotations);
      const left = positions.get('LeftArm'), right = positions.get('RightArm');
      const axis = minus(left, right), axisLength = length(axis);
      const outward = axis.map((value) => value / axisLength);
      const centre = left.map((value, i) => (value + right[i]) / 2);
      for (const [side, sign] of [['Left', 1], ['Right', -1]]) {
        const shoulder = positions.get(side + 'Arm');
        const elbow = positions.get(side + 'ForeArm'), wrist = positions.get(side + 'Hand');
        assert.ok(wrist[1] < shoulder[1] - 0.25, 'fixture should be an arms-down pose');
        const shoulderLateral = sign * dot(minus(shoulder, centre), outward);
        const elbowLateral = sign * dot(minus(elbow, centre), outward);
        assert.ok(elbowLateral >= shoulderLateral - 0.01,
          `${side} elbow folded into the torso at sample ${sample}: ${elbowLateral} vs shoulder ${shoulderLateral}`);
        const upperLength = length(minus(bindPositions.get(side + 'ForeArm'), bindPositions.get(side + 'Arm')));
        const lowerLength = length(minus(bindPositions.get(side + 'Hand'), bindPositions.get(side + 'ForeArm')));
        assert.ok(Math.abs(length(minus(elbow, shoulder)) - upperLength) < 0.00001);
        assert.ok(Math.abs(length(minus(wrist, elbow)) - lowerLength) < 0.00001);
      }
    }
  });
}

for (const id of authoredIds) {
  test(`${id.toUpperCase()}: distinct Kai-native authored asset, honest provenance and native fingers`, () => {
    const entry = index.signs[id], bytes = read(`media/avatar/clips/${entry.file}`), data = glb(bytes), doc = data.json;
    assert.equal(entry.id, id);
    assert.equal(bytes.length, entry.bytes);
    assert.equal(sha256(bytes), entry.sha256);
    assert.equal(entry.targetModelSha256, sha256(kaiBytes));
    assert.equal(entry.source.kind, 'authored');
    assert.equal(entry.approximation, true);
    assert.equal(entry.license, 'project-authored', 'do not claim a new captured CC0 performance');
    assert.equal(entry.sourceFrameRange, undefined);
    assert.match(doc.asset.generator, /hand-authored/);
    assert.deepEqual(doc.extras.source, entry.source);
    assert.equal(entry.language, 'ASL');
    assert.equal(entry.fps, 60);
    assert.equal(entry.duration, (entry.frameCount - 1) / 60);
    assert.equal(entry.includesFingers, true);
    assert.equal(entry.fingerJointCount, 30);
    assert.equal(entry.retargeted, true);
    assert.equal(entry.independentTiming, true);
    assert.equal(entry.rootMotion, false);
    assert.equal(entry.faceMotion, false);
    assert.ok(entry.maxWristTargetErrorM < 0.00001);
    assert.ok(entry.maxLocalStepDegrees < 15);
    for (const template of entry.source.staticPoseTemplates) {
      assert.equal(template.license, 'CC0-1.0');
      assert.equal(template.sha256, sha256(read(`media/avatar/clips/${template.file}`)));
      assert.ok(template.sample >= 0 && template.sample < index.signs[template.id].frameCount);
    }
    for (const field of ['meshes', 'materials', 'images', 'textures', 'skins']) assert.equal(doc[field], undefined);
    for (const node of doc.nodes) {
      const original = kaiNodes.get(node.name);
      assert.ok(original);
      for (const field of ['translation', 'rotation', 'scale', 'matrix']) assert.deepEqual(node[field], original[field]);
    }
    assert.equal(doc.animations.length, 1);
    const animation = doc.animations[0];
    assert.deepEqual(animation.channels.map((c) => doc.nodes[c.target.node].name).sort(), expectedBones);
    let movingFingers = 0;
    for (const channel of animation.channels) {
      assert.equal(channel.target.path, 'rotation');
      const sampler = animation.samplers[channel.sampler];
      assert.equal(sampler.interpolation, 'LINEAR');
      const times = floats(data, sampler.input), values = floats(data, sampler.output);
      assert.equal(times.length, entry.frameCount);
      assert.equal(values.length, times.length * 4);
      for (let i = 0; i < times.length; i++) {
        assert.ok(Math.abs(times[i] - i / 60) < 0.000001);
        const q = values.slice(i * 4, i * 4 + 4);
        assert.ok(q.every(Number.isFinite));
        assert.ok(Math.abs(Math.hypot(...q) - 1) < 0.000002);
        if (i) {
          const previous = values.slice((i - 1) * 4, i * 4);
          const product = dot(q, previous);
          assert.ok(product >= 0, 'continuous quaternion hemispheres');
          assert.ok(2 * Math.acos(Math.min(1, product)) < Math.PI / 12, 'no body/finger rotation spikes');
        }
      }
      if (fingers.includes(doc.nodes[channel.target.node].name) && values.some((value, i) => Math.abs(value - values[i % 4]) > .001)) movingFingers++;
      const start = values.slice(0, 4), finish = values.slice(-4);
      assert.ok(Math.abs(dot(start, finish)) > .99999, 'return to the same safe rest pose for looping');
    }
    assert.ok(movingFingers >= 14, 'gesture has actual changing native finger shapes');
  });

  test(`${id.toUpperCase()}: arms retain limb lengths throughout and finish safely outside the torso`, () => {
    const entry = index.signs[id], data = glb(read(`media/avatar/clips/${entry.file}`));
    for (let sample = 0; sample < entry.frameCount; sample++) {
      const positions = rigPositions(rotationsAt(data, sample));
      for (const [side, sign] of [['Left', 1], ['Right', -1]]) {
        const shoulder = positions.get(side + 'Arm'), elbow = positions.get(side + 'ForeArm'), wrist = positions.get(side + 'Hand');
        for (const [start, end, actual] of [['Arm', 'ForeArm', minus(elbow, shoulder)], ['ForeArm', 'Hand', minus(wrist, elbow)]]) {
          const fixed = length(minus(bindPositions.get(side + end), bindPositions.get(side + start)));
          assert.ok(Math.abs(length(actual) - fixed) < .00001, `stretched ${side} limb at ${sample}`);
        }
        assert.ok(sign * elbow[0] > .10, `elbow entered torso at ${sample}`);
        if (sample === 0 || sample === entry.frameCount - 1) {
          assert.ok(wrist[1] < shoulder[1] - .25);
          assert.ok(sign * elbow[0] >= sign * shoulder[0] - .01);
        }
      }
    }
  });
}

test('the five authored gestures are distinct, not a reused generic animation', () => {
  assert.equal(new Set(authoredIds.map((id) => index.signs[id].sha256)).size, 5);
  const fishA = authoredPositions('fish', 54), fishB = authoredPositions('fish', 108);
  assert.ok(fishB.get('RightHand')[0] - fishA.get('RightHand')[0] > .2, 'FISH swims sideways');
  for (const sample of [54, 72, 90]) {
    const p = authoredPositions('fish', sample), direction = minus(p.get('RightHandMiddle1'), p.get('RightHand'));
    assert.ok(direction[0] > Math.abs(direction[1]) * 2, 'FISH hand points horizontally');
  }

  const pain = authoredPositions('pain', 60);
  assert.ok(length(minus(pain.get('LeftHandIndex4'), pain.get('RightHandIndex4'))) < .055);
  assert.ok(pain.get('RightHandIndex4')[0] - pain.get('RightHand')[0] > .13);
  assert.ok(pain.get('LeftHand')[0] - pain.get('LeftHandIndex4')[0] > .13);
  for (const side of ['Left', 'Right']) {
    assert.ok(length(minus(pain.get(side + 'HandMiddle4'), pain.get(side + 'Hand'))) < .14, 'PAIN uses index-only fists');
  }

  const seeIn = authoredPositions('see', 48), seeOut = authoredPositions('see', 99);
  assert.ok(length(minus(seeIn.get('RightHandIndex4'), seeIn.get('RightEye'))) < .10, 'SEE starts by the actual eye');
  assert.ok(seeOut.get('RightHandIndex4')[2] - seeIn.get('RightHandIndex4')[2] > .22, 'SEE moves forward');
  assert.ok(seeIn.get('RightHandMiddle4')[1] - seeIn.get('RightHandRing4')[1] > .10, 'SEE keeps a V hand, not a flat hand');
  assert.ok(length(minus(seeIn.get('RightHandIndex4'), seeIn.get('RightHandMiddle4'))) > .035, 'V fingers are separated');

  const sick = authoredPositions('sick', 54);
  assert.ok(sick.get('RightHandMiddle4')[1] - sick.get('RightEye')[1] > .045, 'SICK indicates the forehead');
  assert.ok(sick.get('RightHandMiddle4')[2] > sick.get('RightEye')[2] + .04, 'finger stays outside the face');
  assert.ok(sick.get('LeftHandMiddle4')[1] < sick.get('Head')[1] - .4, 'second SICK hand indicates the stomach');
  for (const side of ['Left', 'Right']) {
    assert.ok(sick.get(side + 'HandIndex4')[1] > sick.get(side + 'HandMiddle4')[1] + .025, 'middle finger is bent while index stays open');
  }

  const nightUp = authoredPositions('night', 45), nightDown = authoredPositions('night', 99);
  assert.ok(nightUp.get('RightHandMiddle4')[1] - nightDown.get('RightHandMiddle4')[1] > .2, 'NIGHT dominant hand descends');
  assert.ok(length(minus(nightUp.get('LeftHand'), nightDown.get('LeftHand'))) < .00001, 'NIGHT support stays horizontal and still');
  assert.ok(nightDown.get('RightHandMiddle4')[1] < nightDown.get('LeftHand')[1] - .1);
});

function between(start, end) {
  const a = avatarSource.indexOf(start), b = avatarSource.indexOf(end, a + start.length);
  assert.ok(a >= 0 && b > a, `could not locate player code: ${start}`);
  return avatarSource.slice(a, b);
}

const resolutionSource = between('  async function resolveClip(', '\n  function currentPose(');
const silentConsole = {warn() {}};

test('native mocap has priority and does not wait for unrelated reference/cleanup files', async () => {
  const native = {animation: {}, retargeted: true, includesFingers: true};
  const resolve = vm.runInNewContext(`${resolutionSource}\nresolveClip;`, {
    SIGN_ANIMATIONS: {hello: {frames: [{}]}},
    loadSkeletalClip: async () => native,
    loadBakedAnimation: () => assert.fail('mocap must not load an unrelated baked performance'),
    loadHandCleanup: () => assert.fail('captured fingers must not load a procedural overlay'),
  });
  const result = await resolve('hello');
  assert.equal(result.clip, native);
  assert.equal(result.skeletal, true);
  assert.equal(result.baked, false);
  assert.equal(result.overlay, null);
});

test('absent/broken mocap retains authored, then baked fallback', async () => {
  const authored = {frames: [{}]}, baked = {frames: [{t: 0}]};
  const resolve = vm.runInNewContext(`${resolutionSource}\nresolveClip;`, {
    SIGN_ANIMATIONS: {hello: authored}, loadSkeletalClip: async () => null,
    loadBakedAnimation: async () => baked, loadHandCleanup: async () => null,
  });
  assert.equal((await resolve('hello')).clip, authored);
  const fallback = await resolve('other');
  assert.equal(fallback.clip, baked);
  assert.equal(fallback.baked, true);
});

test('captured fingers and independent mocap time cannot be overwritten by video overlays', () => {
  const clip = {retargeted: true, independentTiming: true};
  const applyHands = vm.runInNewContext(
    `${between('  function applyHandOverlay(', '\n  /** Lock motion')}\napplyHandOverlay;`,
    {avatar: {}, clip, handOverlay: {frames: [{}]}, sampleClip: () => assert.fail('overwrote mocap fingers')},
  );
  assert.equal(applyHands(0.5), false);
  const sync = vm.runInNewContext(
    `${between('  function applySyncedToVideo(', '\n  function resize(')}\napplySyncedToVideo;`,
    {avatar: {}, clip, syncVideo: {}, progressFromVideo: () => assert.fail('used unrelated video time')},
  );
  assert.equal(sync(), false);
});

function loaderHarness(signs, animation, fail = false) {
  let loads = 0;
  class Loader {
    load(url, success, progress, error) {
      loads++;
      if (fail) error(new Error('broken GLB'));
      else success({animations: animation ? [animation] : []});
    }
  }
  const source = clipSource.replace(/^import .*;$/gm, '').replace(/^export /gm, '');
  const api = vm.runInNewContext(`${source}\n({loadSkeletalClip, sanitizeUpperBodyClip});`, {
    GLTFLoader: Loader, console: silentConsole, fetch: async () => ({ok: true, json: async () => ({signs})}),
  });
  return {...api, loads: () => loads};
}
function track(name, times = [0, 1], values = [0, 0, 0, 1, 0, 0, 0, 1]) {
  return {name, times: new Float32Array(times), values: new Float32Array(values)};
}
function animation(tracks) {
  return {name: 'Sign', duration: 1, tracks, clone() {return {...this, tracks: [...this.tracks]};}};
}

test('clip loader keeps upper body/fingers and rejects root, leg, invalid and unordered tracks', async () => {
  const raw = animation([
    track('Spine1.quaternion'), track('RightHandIndex3.quaternion'),
    track('Hips.position'), track('LeftLeg.quaternion'),
    track('LeftHand.quaternion', [0, 0]), track('Head.quaternion', [0, 1], [NaN, 0, 0, 1, 0, 0, 0, 1]),
  ]);
  const loader = loaderHarness({hello: index.signs.hello}, raw);
  const clip = await loader.loadSkeletalClip('hello');
  assert.deepEqual(Array.from(clip.animation.tracks, (t) => t.name), ['Spine1.quaternion', 'RightHandIndex3.quaternion']);
  assert.equal(raw.tracks.length, 6, 'do not mutate cached source animation');
  assert.equal(clip.includesFingers, true);
  assert.equal(clip.independentTiming, true);
  assert.equal((await loader.loadSkeletalClip('hello')).animation, clip.animation);
  assert.equal(loader.loads(), 1);
});

test('missing, unsafe, corrupt and empty GLBs return null for fallback playback', async () => {
  const unsafe = loaderHarness({hello: {file: '../signer.glb'}}, null);
  assert.equal(await unsafe.loadSkeletalClip('hello'), null);
  assert.equal(await unsafe.loadSkeletalClip('unknown'), null);
  assert.equal(unsafe.loads(), 0);
  const broken = loaderHarness({hello: index.signs.hello}, null, true);
  assert.equal(await broken.loadSkeletalClip('hello'), null);
  const empty = loaderHarness({hello: index.signs.hello}, animation([track('Hips.position')]));
  assert.equal(await empty.loadSkeletalClip('hello'), null);
});

function playerHarness() {
  const requests = [];
  const source = between('  const api = {', '\n  if (typeof window');
  const state = vm.runInNewContext(`
    let ready=true, currentId='hello', playing=false, loadError=null, disposed=false;
    let clip=null, clipRevision=0, usingBaked=false, usingSkeletal=false, handOverlay=null;
    let retargetMode=false, elapsed=0, endedNotified=false, speed=1, loop=false, mixerAction=null;
    ${source}
    ({api, flags: () => ({usingSkeletal, usingBaked, handOverlay})});
  `, {
    SIGN_ANIMATIONS: {hello: {frames: [{}]}, please: {frames: [{}]}},
    avatar: {}, canvas: {setAttribute() {}}, console: silentConsole,
    stopMixer() {}, startMixerClip() {}, resetBonesToBind() {}, onStatus() {},
    resolveClip: (id) => new Promise((resolve) => requests.push({id, resolve})),
  });
  return {...state, requests};
}
const settle = () => new Promise((resolve) => setImmediate(resolve));

test('late async responses cannot replace a newly selected sign or its playback flags', async () => {
  const player = playerHarness();
  player.api.play('hello');
  player.api.play('please');
  player.requests[1].resolve({clip: {id: 'please', animation: {}, source: {name: 'Studio Galt', kind: 'studio-galt'}}, skeletal: true, baked: false, overlay: null});
  await settle();
  player.requests[0].resolve({clip: {id: 'hello'}, skeletal: false, baked: true, overlay: {frames: [{}]}});
  await settle();
  assert.equal(player.api.currentId, 'please');
  assert.equal(player.api.mocap, true);
  assert.equal(player.flags().usingSkeletal, true);
  assert.equal(player.flags().usingBaked, false);
  assert.equal(player.flags().handOverlay, null);
  assert.equal(player.api.play('../unsafe'), false);
});

test('repeated selection of the same sign is also protected by the revision guard', async () => {
  const player = playerHarness();
  player.api.play('hello');
  player.api.play('hello');
  player.requests[1].resolve({clip: {id: 'hello', retargeted: true, animation: {}, source: {name: 'Studio Galt', kind: 'studio-galt'}}, skeletal: true, baked: false, overlay: null});
  await settle();
  player.requests[0].resolve({clip: {id: 'hello'}, skeletal: false, baked: false, overlay: null});
  await settle();
  assert.equal(player.api.mocap, true);
  assert.equal(player.api.usingSkeletal, true);
});

test('Kai-native authored GLBs take priority, preserve their fingers, and are not reported as mocap', async () => {
  const native = {id: 'sick', animation: {}, retargeted: true, includesFingers: true,
    approximation: true, source: {name: 'HandSpeak', kind: 'authored'}};
  const resolve = vm.runInNewContext(`${resolutionSource}\nresolveClip;`, {
    SIGN_ANIMATIONS: {}, loadSkeletalClip: async () => native,
    loadBakedAnimation: () => assert.fail('must not substitute an unrelated performance'),
    loadHandCleanup: () => assert.fail('must not overwrite authored native fingers'),
  });
  const result = await resolve('sick');
  assert.equal(result.clip, native);
  assert.equal(result.overlay, null);
  const player = playerHarness();
  player.api.play('sick');
  player.requests[0].resolve(result);
  await settle();
  assert.equal(player.api.usingSkeletal, true);
  assert.equal(player.api.approximate, true);
  assert.equal(player.api.mocap, false);
  assert.equal(player.api.motionSource, 'HandSpeak');
  const loaded = await loaderHarness({sick: index.signs.sick}, animation([track('RightHand.quaternion')])).loadSkeletalClip('sick');
  assert.equal(loaded.approximation, true);
  assert.equal(loaded.source.kind, 'authored');
  assert.equal(loaded.independentTiming, true);
});

// Optional deeper check against the application's exact Three.js 0.160.0 package.
// Set HANDSPEAK_THREE_PACKAGE to an unpacked official npm three package directory.
test('Three.js GLTFLoader + actual player mixer scrub Kai bones and hold paused/end poses', {
  skip: !process.env.HANDSPEAK_THREE_PACKAGE && 'set HANDSPEAK_THREE_PACKAGE for the Three.js integration check',
}, async () => {
  const packageDir = process.env.HANDSPEAK_THREE_PACKAGE;
  const THREE = await import(pathToFileURL(join(packageDir, 'build/three.module.js')));
  assert.equal(THREE.REVISION, '160');
  const {GLTFLoader} = await import(pathToFileURL(join(packageDir, 'examples/jsm/loaders/GLTFLoader.js')));
  const jointIds = new Set(kai.json.skins[0].joints);
  const objects = kai.json.nodes.map((node, i) => {
    const object = jointIds.has(i) ? new THREE.Bone() : new THREE.Object3D();
    object.name = node.name || '';
    if (node.matrix) new THREE.Matrix4().fromArray(node.matrix).decompose(object.position, object.quaternion, object.scale);
    else {
      if (node.translation) object.position.fromArray(node.translation);
      if (node.rotation) object.quaternion.fromArray(node.rotation);
      if (node.scale) object.scale.fromArray(node.scale);
    }
    if (object.isBone) {object.userData.bindQuat = object.quaternion.clone(); object.userData.bindPos = object.position.clone();}
    return object;
  });
  kai.json.nodes.forEach((node, i) => node.children?.forEach((child) => objects[i].add(objects[child])));
  const root = new THREE.Group();
  kai.json.scenes[kai.json.scene || 0].nodes.forEach((i) => root.add(objects[i]));
  const mixerCode = between('  function stopMixer(', '\n  /**\n   * Prefer Kai-native');
  const player = vm.runInNewContext(`let mixer=null, mixerAction=null; ${mixerCode}
    ({startMixerClip, scrub: (time) => {mixerAction.time=time; mixer.update(0);}});`, {THREE, avatar: {root}});
  for (const entry of Object.values(index.signs)) {
    const source = manifest.clips.find((item) => item.id === entry.id);
    const bytes = read(`media/avatar/clips/${entry.file}`);
    const parsed = await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '');
    const cleaned = loaderHarness({}, null).sanitizeUpperBodyClip(parsed.animations[0]);
    assert.equal(cleaned.tracks.length, 43);
    assert.equal(player.startMixerClip({animation: cleaned}), true);
    player.scrub(0);
    const before = root.getObjectByName('RightHand').quaternion.clone();
    const sample = source ? source.keyPoseFrames[0] - source.sourceFrameRange[0] : entry.keyPoseSamples[0];
    player.scrub(sample / 60);
    assert.ok(before.angleTo(root.getObjectByName('RightHand').quaternion) > 0.01);
    const data = glb(bytes), animation = data.json.animations[0];
    for (const channel of animation.channels) {
      const name = data.json.nodes[channel.target.node].name;
      const values = floats(data, animation.samplers[channel.sampler].output);
      const expected = new THREE.Quaternion().fromArray(values, sample * 4);
      assert.ok(Math.abs(expected.dot(root.getObjectByName(name).quaternion)) > 0.99999, `unbound or wrong bone ${name}`);
    }
    const paused = root.getObjectByName('RightHand').quaternion.toArray();
    player.scrub(sample / 60);
    assert.deepEqual(root.getObjectByName('RightHand').quaternion.toArray(), paused);
    player.scrub(entry.duration);
    const ended = root.getObjectByName('RightHand').quaternion.toArray();
    player.scrub(entry.duration);
    assert.deepEqual(root.getObjectByName('RightHand').quaternion.toArray(), ended);
  }
});
