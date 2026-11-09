import test from 'node:test';
import assert from 'node:assert/strict';
import {imageSize, restoreCrop, wristCrop, recoverSlots, createHandRecovery, createWorkerHandRecovery, needsHandRecovery} from '../body-hand-recovery.js';
const hand = (x, y) => Array.from({length: 21}, (_, i) => ({x: x + i * .004, y: y + i * .005, z: -.02}));
function pose() {
  const p = Array.from({length: 33}, () => ({x: .5, y: .5, visibility: 1}));
  p[11] = {x: .3, y: .3};p[12] = {x: .7, y: .3};
  p[15] = {x: .4, y: .5};p[16] = {x: .6, y: .5};
  return p;
}
test('frozen canvas and live video dimensions are both supported', () => {
  assert.deepEqual(imageSize({width: 640, height: 480}), [640, 480]);
  assert.deepEqual(imageSize({videoWidth: 960, videoHeight: 720}), [960, 720]);
});
test('crop points return to the full image, with depth scaled by width', () => {
  const h = restoreCrop(hand(.5, .5), {x: 100, y: 50, width: 200, height: 100}, 800, 600);
  assert.equal(h[0].x, .25);assert.equal(h[0].y, 1 / 6);assert.equal(h[0].z, -.005);
  assert.equal(restoreCrop([{x: NaN, y: 0}], {}, 640, 480), null);
});
test('crossed hands are assigned by pose anatomy rather than screen order', () => {
  const p = pose();p[15].x = .65;p[16].x = .35;
  const left = hand(.65, .5), right = hand(.35, .5);
  const r = recoverSlots({poseLandmarks: p}, [right, left], 640, 480);
  assert.equal(r.leftHandLandmarks, left);assert.equal(r.rightHandLandmarks, right);
});
test('one observation cannot fill two missing slots', () => {
  const r = recoverSlots({poseLandmarks: pose()}, [hand(.5, .5)], 640, 480);
  assert.equal([r.leftHandLandmarks, r.rightHandLandmarks].filter(Boolean).length, 1);
});
test('known Holistic hand is retained and cannot be duplicated by recovery', () => {
  const left = hand(.4, .5);
  const r = recoverSlots({poseLandmarks: pose(), leftHandLandmarks: left}, [hand(.401, .5)], 640, 480);
  assert.equal(r.leftHandLandmarks, left);assert.equal(r.rightHandLandmarks, undefined);
});
test('distant and tiny detections cannot invent hands', () => {
  const r = recoverSlots({poseLandmarks: pose()}, [hand(2, 2), Array(21).fill({x: .5, y: .5})], 640, 480);
  assert.equal(r.usedHandFallback, undefined);
});
test('unseen wrists are not cropped and crops stay within the image', () => {
  const p = pose();p[15].visibility = .1;
  assert.equal(wristCrop(p, 15, 19, 640, 480), null);
  p[15] = {x: .01, y: .01};
  const crop = wristCrop(p, 15, 19, 640, 480);
  assert.ok(crop.x >= 0 && crop.y >= 0 && crop.x + crop.width <= 640 && crop.y + crop.height <= 480);
});
test('dedicated recovery uses IMAGE mode and the same frozen frame', async () => {
  let options, seen;
  const image = {width: 640, height: 480};
  const model = await createHandRecovery({vision: {HandLandmarker: {async createFromOptions(files, config) {
    options = config;return {detect(i) {seen = i;return {landmarks: [hand(.4, .5), hand(.6, .5)]};}, close() {}};
  }}}, files: {}, createCanvas: () => ({getContext: () => ({drawImage() {}})})});
  assert.equal(options.runningMode, 'IMAGE');
  const r = model.recover({poseLandmarks: pose()}, image);
  assert.equal(seen, image);assert.equal(r.usedHandFallback, true);
  model.close();
});

async function withWorker(fn) {
  const priorWorker = globalThis.Worker, priorBitmap = globalThis.createImageBitmap;
  let worker, bitmap, imageSeen;
  class FakeWorker {
    constructor(url, options) {worker = this;this.url = url;this.options = options;this.messages = [];}
    postMessage(data, transfers) {
      this.messages.push({data, transfers});
      if (data.type === 'init') queueMicrotask(() => this.onmessage({data: {type: 'ready'}}));
    }
    terminate() {this.terminated = true;}
  }
  globalThis.Worker = FakeWorker;
  globalThis.createImageBitmap = async input => {imageSeen = input;bitmap = {close() {this.closed = true;}};return bitmap;};
  try {await fn({worker: () => worker, bitmap: () => bitmap, seen: () => imageSeen});}
  finally {globalThis.Worker = priorWorker;globalThis.createImageBitmap = priorBitmap;}
}
test('recovery worker is classic and transfers the same frozen input without a face payload', async () => {
  await withWorker(async s => {
    const recovery = await createWorkerHandRecovery(), image = {width: 640, height: 480};
    assert.equal(s.worker().options, undefined);
    const pending = recovery.recover({poseLandmarks: pose(), faceLandmarks: ['not sent']}, image);
    await Promise.resolve();await Promise.resolve();
    const packet = s.worker().messages.at(-1);
    assert.equal(s.seen(), image);assert.deepEqual(packet.transfers, [s.bitmap()]);
    assert.equal(packet.data.result.faceLandmarks, undefined);
    s.worker().onmessage({data: {id: packet.data.id, result: {leftHandLandmarks: hand(.4, .5), usedHandFallback: true}}});
    assert.equal((await pending).usedHandFallback, true);
    recovery.close();assert.equal(s.worker().terminated, true);
  });
});
test('an observed primary hand does not invent an offscreen second hand', async () => {
  await withWorker(async s => {
    const recovery = await createWorkerHandRecovery();
    const p = pose();p[16].y = 1.2;
    const result = {poseLandmarks: p, leftHandLandmarks: hand(.4, .5)};
    assert.equal(await recovery.recover(result, {}), result);
    assert.equal(s.worker().messages.length, 1);recovery.close();
  });
});

test('a visible missing second hand is recovered on the same frozen input', async () => {
  await withWorker(async s => {
    const recovery = await createWorkerHandRecovery(), primary = hand(.4,.5);
    const input = {poseLandmarks: pose(), leftHandLandmarks: primary};
    const pending = recovery.recover(input, {width:640,height:480});
    await Promise.resolve();await Promise.resolve();
    const packet = s.worker().messages.at(-1);
    assert.equal(packet.data.type,'frame');
    assert.equal(packet.data.result.leftHandLandmarks,primary);
    s.worker().onmessage({data:{id:packet.data.id,result:{rightHandLandmarks:hand(.6,.5),usedHandFallback:true}}});
    const result = await pending;
    assert.equal(result.leftHandLandmarks,primary);
    assert.ok(result.rightHandLandmarks);
    recovery.close();
  });
});

test('two observed hands and an uncertain resting wrist bypass recovery',()=>{
  const p = pose();p[16].visibility=.5;
  assert.equal(needsHandRecovery({poseLandmarks:p,leftHandLandmarks:hand(.4,.5)}),false);
  assert.equal(needsHandRecovery({poseLandmarks:pose(),leftHandLandmarks:hand(.4,.5),rightHandLandmarks:hand(.6,.5)}),false);
});
test('closing while a bitmap is created releases it without sending a stale frame', async () => {
  await withWorker(async s => {
    const recovery = await createWorkerHandRecovery();
    const pending = recovery.recover({poseLandmarks: pose()}, {});
    recovery.close();await assert.rejects(pending, /stopped/);
    assert.equal(s.bitmap().closed, true);assert.equal(s.worker().messages.length, 1);
  });
});
test('worker frame errors reject the pending request instead of leaving a hung take', async () => {
  await withWorker(async s => {
    const recovery = await createWorkerHandRecovery();
    const pending = recovery.recover({poseLandmarks: pose()}, {});
    await Promise.resolve();await Promise.resolve();
    s.worker().onmessage({data: {type: 'error', message: 'bad frame'}});
    await assert.rejects(pending, /bad frame/);recovery.close();
  });
});
