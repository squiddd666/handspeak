/** Reference pairing, native finger/arm assets, timing and actual Three.js mixer. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {join} from 'node:path';
import vm from 'node:vm';

const root = new URL('../', import.meta.url);
const read = name => readFileSync(new URL(name, root));
const text = name => read(name).toString();
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const index = JSON.parse(text('media/avatar/reference/index.json'));
const source = text('sign-avatar.js'), referenceSource = text('sign-reference.js');
const quiet = {warn() {}};
const allowed = /^(?:Spine[12]?|Neck|Head|(?:Left|Right)(?:Shoulder|Arm|ForeArm|Hand(?:(?:Thumb|Index|Middle|Ring|Pinky)[123])?))$/;

function glb(bytes) {
  assert.equal(bytes.toString('ascii', 0, 4), 'glTF');
  assert.equal(bytes.readUInt32LE(4), 2);
  assert.equal(bytes.readUInt32LE(8), bytes.length);
  let json, bin;
  for (let offset = 12; offset < bytes.length;) {
    const size = bytes.readUInt32LE(offset), kind = bytes.readUInt32LE(offset + 4);
    assert.equal(size % 4, 0); assert.ok(offset + 8 + size <= bytes.length);
    const chunk = bytes.subarray(offset + 8, offset + 8 + size);
    if (kind === 0x4e4f534a) json = JSON.parse(chunk.toString());
    if (kind === 0x004e4942) bin = chunk;
    offset += 8 + size;
  }
  assert.ok(json && bin);
  return {json, bin};
}
function floats(data, ai) {
  const a = data.json.accessors[ai], v = data.json.bufferViews[a.bufferView];
  assert.equal(a.componentType, 5126);
  const width = {SCALAR: 1, VEC4: 4}[a.type]; assert.ok(width);
  const start = (v.byteOffset || 0) + (a.byteOffset || 0), n = a.count * width;
  assert.ok(start + n * 4 <= data.bin.length);
  return Array.from({length: n}, (_, i) => data.bin.readFloatLE(start + i * 4));
}
function tracks(data) {
  return data.json.animations[0].channels.map(c => {
    const s = data.json.animations[0].samplers[c.sampler];
    return {name: data.json.nodes[c.target.node].name, path: c.target.path,
      times: floats(data, s.input), values: floats(data, s.output), node: c.target.node};
  });
}
function extract(start, end) {
  const a = source.indexOf(start), b = source.indexOf(end, a + start.length);
  assert.ok(a >= 0 && b > a); return source.slice(a, b);
}
const modelBytes = read('media/avatar/signer.glb'), model = glb(modelBytes);
const original = new Map(model.json.nodes.map(n => [n.name, n]));

test('all and only the 40 currently displayed local reference performances are paired; Kai is unchanged', () => {
  const html = text('index.html'), catalog = JSON.parse(text('models/motion-vocabulary.json'));
  const groups = JSON.parse(text('models/motion-categories/index.json')).groups;
  const ids = new Set([...html.matchAll(/data-sign-example="([a-z0-9-]+)"/g)].map(m => m[1]));
  catalog.items.filter(item => groups.some(g => g.labels?.includes(item.label) && item.cameraGroups?.includes(g.id)))
    .forEach(item => ids.add(item.id));
  const expected = [...ids].filter(id => {
    try {read(`media/signs/${id}.mp4`); return true;} catch {return false;}
  }).sort();
  assert.equal(expected.length, 40);
  assert.deepEqual(Object.keys(index.signs).sort(), expected);
  assert.equal(hash(modelBytes), '0818af838616531c6fc053edb1c66d7f4cc71323a0ca3524704f6647e8707196');
  assert.equal(index.targetModelSha256, hash(modelBytes));
});

for (const [id, entry] of Object.entries(index.signs)) {
  test(`${id.toUpperCase()}: verified same-video source, all 30 finger segments, intact native axes and seconds`, () => {
    const bytes = read(`media/avatar/reference/${entry.file}`), data = glb(bytes);
    assert.equal(bytes.length, entry.bytes); assert.equal(hash(bytes), entry.sha256);
    assert.equal(entry.reference.file, `media/signs/${id}.mp4`);
    assert.equal(hash(read(entry.reference.file)), entry.reference.sha256);
    assert.equal(entry.targetModelSha256, hash(modelBytes));
    assert.equal(entry.source.kind, 'reference-video');
    assert.equal(entry.referenceMatched, true); assert.equal(entry.reconstructed, true);
    assert.equal(entry.independentTiming, false); assert.equal(entry.includesFingers, true);
    assert.ok(!data.json.meshes && !data.json.materials && !data.json.images);
    assert.equal(data.json.extras.reference.sha256, entry.reference.sha256);
    assert.equal(data.json.animations.length, 1);
    for (const node of data.json.nodes) {
      const bind = original.get(node.name); assert.ok(bind, node.name);
      for (const key of ['rotation', 'translation', 'scale', 'matrix']) assert.deepEqual(node[key], bind[key]);
    }
    const ts = tracks(data); assert.equal(ts.length, 43);
    for (const side of ['Left', 'Right']) {
      for (const part of ['Shoulder', 'Arm', 'ForeArm', 'Hand']) assert.ok(ts.some(t => t.name === side + part));
      for (const digit of ['Thumb', 'Index', 'Middle', 'Ring', 'Pinky']) {
        for (const j of [1, 2, 3]) assert.ok(ts.some(t => t.name === `${side}Hand${digit}${j}`));
      }
    }
    for (const t of ts) {
      assert.equal(t.path, 'rotation'); assert.match(t.name, allowed);
      assert.equal(t.times.length, entry.samples);
      assert.equal(t.times[0], 0);
      assert.ok(Math.abs(t.times.at(-1) - entry.reference.duration) < 1e-5);
      assert.ok(t.times.every((v, i) => Number.isFinite(v) && (i === 0 || v > t.times[i - 1])));
      assert.ok(t.values.every(Number.isFinite));
      for (let i = 0; i < t.times.length; i++) {
        const q = t.values.slice(i * 4, i * 4 + 4);
        assert.ok(Math.abs(Math.hypot(...q) - 1) < 1e-5);
        if (i) {
          const dot = q.reduce((s, v, k) => s + v * t.values[(i - 1) * 4 + k], 0);
          assert.ok(dot >= -1e-6);
          if (/Hand(?:Thumb|Index|Middle|Ring|Pinky)/.test(t.name)) {
            assert.ok(2 * Math.acos(Math.min(1, Math.abs(dot))) < 170 * Math.PI / 180,
              `${id} ${t.name}: antipodal finger-roll flip`);
          }
        }
      }
    }
    assert.ok(entry.quality.maxLimbLengthErrorM < 1e-5);
  });
}

test('the source variants retain their actual dominant hand instead of generic mirrored/two-handed poses', () => {
  for (const [id, side] of Object.entries({hello: 'Right', please: 'Right', no: 'Right', fish: 'Right',
      pain: 'Right', see: 'Right', sick: 'Left', finish: 'Left', night: 'Left'})) {
    const quality = index.signs[id].quality.hands, other = side === 'Left' ? 'Right' : 'Left';
    assert.ok(quality[side].trackedFrames >= 10, id);
    assert.equal(quality[other].activeFrames, 0, `${id}: unused hand must stay neutral`);
  }
});

test('MICROSCOPE restores only its reviewed supporting hand and explicitly marks unseen detail as estimated', () => {
  const corrections = JSON.parse(text('scripts/kai-reference-corrections.json'));
  const entry = index.signs.microscope, correction = entry.reviewedCorrection;
  assert.deepEqual(Object.keys(index.signs).filter(id => index.signs[id].reviewedCorrection), ['microscope']);
  assert.equal(correction.referenceSha256, entry.reference.sha256);
  assert.equal(correction.sha256, hash(read('scripts/kai-reference-corrections.json')));
  assert.equal(correction.version, corrections.version);
  assert.equal(correction.supportSide, 'Left'); assert.equal(correction.dominantSide, 'Right');
  assert.equal(correction.faceTarget, 'RightEye');
  const quality = entry.quality.hands.Left;
  assert.ok(quality.activeFrames >= 25);
  assert.equal(quality.trackedFrames, 0); assert.equal(quality.coverage, 0);
  assert.ok(quality.maxEstimatedGapSeconds > .5);
  assert.match(quality.estimatedReason, /occluded.*estimates/);
  assert.equal(entry.quality.reviewRequired, true);
  const ts = tracks(glb(read(`media/avatar/reference/${entry.file}`)));
  for (const name of ['LeftArm', 'LeftForeArm', 'LeftHand', 'LeftHandIndex2']) {
    const t = ts.find(t => t.name === name), start = t.values.slice(0, 4), end = t.values.slice(-4);
    assert.ok(Math.abs(start.reduce((s, v, k) => s + v * end[k], 0)) > .9999, `${name}: return to rest`);
    assert.ok(t.values.some((v, i) => Math.abs(v - start[i % 4]) > .05), `${name}: missing supporting motion`);
  }
  // The reviewed exception must not turn other one-handed references into two-handed guesses.
  assert.equal(index.signs.no.quality.hands.Left.activeFrames, 0);
});

function referenceHarness(entry = index.signs.hello, options = {}) {
  const names = ['Spine', 'Spine1', 'Spine2', 'Neck', 'Head'];
  for (const side of ['Left', 'Right']) {
    for (const part of ['Shoulder', 'Arm', 'ForeArm', 'Hand']) names.push(side + part);
    for (const digit of ['Thumb', 'Index', 'Middle', 'Ring', 'Pinky']) for (const j of [1, 2, 3]) names.push(`${side}Hand${digit}${j}`);
  }
  let loads = 0;
  class Loader {
    load(url, ok, _progress, fail) {
      loads++;
      if (options.fail) {fail(new Error('offline')); return;}
      ok({parser: {json: {extras: options.metadata || entry}}, animations: [{name: 'Sign', duration: entry.duration,
        tracks: names.filter(n => n !== options.omit).map(name => ({name: `${name}.quaternion`}))}]});
    }
  }
  const code = referenceSource.replace(/^import .*;$/gm, '').replace(/^export /gm, '');
  return vm.runInNewContext(`${code}\n({loadReferenceClip, hasReferenceClip, sameReference, loads: () => loads()});`, {
    URL, GLTFLoader: Loader, console: quiet, sanitizeUpperBodyClip: animation => animation,
    fetch: async () => ({ok: true, json: async () => ({targetModelSha256: index.targetModelSha256, signs: {hello: entry}})}),
    loads: () => loads,
  });
}

test('loader accepts only the displayed source, rejects external/wrong/unsafe files and partial hands', async () => {
  const loader = referenceHarness();
  assert.equal(loader.sameReference('media/signs/hello.mp4', './media/signs/hello.mp4?v=2'), true);
  assert.equal(loader.sameReference('media/signs/hello.mp4', './media/signs/please.mp4'), false);
  assert.equal(loader.sameReference('media/signs/hello.mp4', 'https://other.example/media/signs/hello.mp4'), false);
  assert.equal(await loader.loadReferenceClip('hello', './media/signs/please.mp4'), null);
  assert.equal(await loader.loadReferenceClip('../hello', './media/signs/hello.mp4'), null);
  const loaded = await loader.loadReferenceClip('hello', './media/signs/hello.mp4');
  assert.equal(loaded.referenceMatched, true); assert.equal(loaded.includesFingers, true);
  assert.equal(await referenceHarness(index.signs.hello, {omit: 'RightHandIndex2'}).loadReferenceClip('hello', './media/signs/hello.mp4'), null);
  assert.equal(await referenceHarness(index.signs.hello, {omit: 'LeftForeArm'}).loadReferenceClip('hello', './media/signs/hello.mp4'), null);
  assert.equal(await referenceHarness(index.signs.hello, {metadata: {...index.signs.hello, reference: {sha256: 'bad'}}}).loadReferenceClip('hello', './media/signs/hello.mp4'), null);
  assert.equal(await referenceHarness(index.signs.hello, {fail: true}).loadReferenceClip('hello', './media/signs/hello.mp4'), null);
});

test('a matched performance takes priority over different mocap/authored hands; missing reconstruction falls back', async () => {
  const native = {animation: {}, referenceMatched: true, includesFingers: true};
  const legacy = {animation: {}, retargeted: true};
  let found = native, legacyLoads = 0;
  const resolve = vm.runInNewContext(`${extract('  async function resolveClip(', '\n  function currentPose(')}\nresolveClip;`, {
    loadReferenceClip: async () => found,
    loadSkeletalClip: async () => {legacyLoads++; return legacy;}, SIGN_ANIMATIONS: {hello: {frames: [{}]}},
    loadBakedAnimation: () => assert.fail('must not borrow another performance'),
    loadHandCleanup: () => assert.fail('must not replace reconstructed fingers'),
  });
  const result = await resolve('hello', './media/signs/hello.mp4');
  assert.equal(result.clip, native); assert.equal(result.overlay, null); assert.equal(legacyLoads, 0);
  found = null;
  assert.equal((await resolve('hello', './media/signs/hello.mp4')).clip, legacy);
  assert.equal((await resolve('hello')).clip, legacy);
});

test('reference seconds, pause/seek/end and a changed video cannot drift or scrub the previous word', () => {
  const clip = {referenceMatched: true, duration: 2, referenceVideo: './media/signs/hello.mp4'};
  const video = {duration: 2.05, currentTime: .75, ended: false, loop: false,
    getAttribute: () => './media/signs/please.mp4'};
  const progress = vm.runInNewContext(`${extract('  function progressFromVideo(', '\n  function tick(')}\nprogressFromVideo;`, {syncVideo: video, clip});
  assert.equal(progress(), .375);
  video.currentTime = 1.5; assert.equal(progress(), .75);
  video.ended = true; assert.equal(progress(), 1);
  const sync = vm.runInNewContext(`${extract('  function applySyncedToVideo(', '\n  function resize(')}\napplySyncedToVideo;`, {
    avatar: {}, clip, syncVideo: video,
    sameReference: referenceHarness().sameReference,
    progressFromVideo: () => assert.fail('scrubbed old word with new reference'),
  });
  assert.equal(sync(), false);
});

test('Watch & practice passes the actual selected video source and labels reconstructed motion honestly', async () => {
  const ui = text('sign-examples.js');
  const segment = (a, b) => ui.slice(ui.indexOf(a), ui.indexOf(b, ui.indexOf(a) + a.length));
  const played = [];
  const player = {setSpeed() {}, play(...args) {played.push(args); return true;}};
  const video = {getAttribute: () => './media/signs/hello.mp4'};
  const play = vm.runInNewContext(`let playbackRevision=0; ${segment('async function playSign(', '\nfunction chooseSign(')}\nplaySign;`, {
    setReferenceLayout(){},referenceOnlySelection:()=>false,
    ensureAvatar: () => player, playback: {}, status: {}, label: 'HELLO', speed: {value: '1'},
    playReferenceVideo() {}, hasSignAnimation: () => true, mocapOnly: new Set(), video,
  });
  await play('hello'); assert.equal(played[0][1].reference, './media/signs/hello.mp4');
  const avatar = {referenceMatched: true, approximate: true, mocap: false, reconstructionQuality: {reviewRequired: true}};
  const status = vm.runInNewContext(`${segment('function motionStatus(', '\nfunction videoSrcFor(')}\nmotionStatus;`, {
    referenceOnlySelection:()=>false,
    avatar, label: 'HOME', speedLabel: () => '0.5× speed',
  });
  assert.match(status(), /follows this reference.*reconstructed 3D.*estimated/);
  assert.doesNotMatch(status(), /ASL mocap|hand-authored/);
});

test('actual Three.js 0.160 loader/mixer scrubs all 40 native reconstructions, including fingers and endpoints', {
  skip: !process.env.HANDSPEAK_THREE_PACKAGE && 'set HANDSPEAK_THREE_PACKAGE for native integration',
}, async () => {
  const dir = process.env.HANDSPEAK_THREE_PACKAGE;
  const THREE = await import(pathToFileURL(join(dir, 'build/three.module.js')));
  const {GLTFLoader} = await import(pathToFileURL(join(dir, 'examples/jsm/loaders/GLTFLoader.js')));
  assert.equal(THREE.REVISION, '160');
  const joints = new Set(model.json.skins[0].joints), group = new THREE.Group();
  const objects = model.json.nodes.map((n, i) => {
    const o = joints.has(i) ? new THREE.Bone() : new THREE.Object3D(); o.name = n.name || '';
    if (n.matrix) new THREE.Matrix4().fromArray(n.matrix).decompose(o.position, o.quaternion, o.scale);
    else {if (n.translation) o.position.fromArray(n.translation); if (n.rotation) o.quaternion.fromArray(n.rotation); if (n.scale) o.scale.fromArray(n.scale);}
    if (o.isBone) {o.userData.bindQuat = o.quaternion.clone(); o.userData.bindPos = o.position.clone();}
    return o;
  });
  model.json.nodes.forEach((n, i) => n.children?.forEach(c => objects[i].add(objects[c])));
  model.json.scenes[model.json.scene || 0].nodes.forEach(i => group.add(objects[i]));
  const player = vm.runInNewContext(`let mixer=null,mixerAction=null;
    ${extract('  function stopMixer(', '\n  /**\n   * Prefer Kai-native')}
    ({startMixerClip,scrub(time){mixerAction.time=time;mixer.update(0);}});`, {THREE, avatar: {root: group}});
  for (const entry of Object.values(index.signs)) {
    const bytes = read(`media/avatar/reference/${entry.file}`), data = glb(bytes), ts = tracks(data);
    const loaded = await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '');
    assert.equal(loaded.animations[0].tracks.length, 43);
    assert.equal(player.startMixerClip({animation: loaded.animations[0]}), true);
    for (const sample of [0, Math.floor(ts[0].times.length / 2), ts[0].times.length - 1]) {
      player.scrub(ts[0].times[sample]);
      for (const t of ts) {
        const q = new THREE.Quaternion().fromArray(t.values.slice(sample * 4, sample * 4 + 4)).normalize();
        assert.ok(group.getObjectByName(t.name).quaternion.clone().normalize().angleTo(q) < .001, `${entry.id} ${t.name} ${sample}`);
      }
      if (entry.id === 'microscope' && sample === Math.floor(ts[0].times.length / 2)) {
        group.updateMatrixWorld(true);
        const pos = name => group.getObjectByName(name).getWorldPosition(new THREE.Vector3());
        const correction = entry.reviewedCorrection;
        const wrist = pos('RightHand'), axis = wrist.clone().sub(pos('RightForeArm')).normalize();
        const contact = wrist.clone().addScaledVector(axis, -correction.contactBelowWristM)
          .add(new THREE.Vector3(0, 0, correction.contactSurfaceOffsetM));
        const palm = pos('LeftHand').lerp(pos('LeftHandMiddle1'), correction.contactPalmFraction);
        assert.ok(palm.distanceTo(contact) < .005, 'supporting palm must cup the actual dominant forearm');
        const circle = pos('RightHandThumb4').add(pos('RightHandIndex4')).multiplyScalar(.5);
        const eye = pos(correction.faceTarget).add(new THREE.Vector3().fromArray(correction.faceOffsetM));
        assert.ok(circle.distanceTo(eye) < .005, 'tracked C shape must be held at the eye, not the chin');
      }
    }
  }
});
