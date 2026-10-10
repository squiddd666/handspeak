import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';

function setup() {
  let now = 0, worker, gaps = 0;
  const detections = [], errors = [];
  class Worker {
    sent = []; stopped = false;
    constructor() { worker = this; }
    postMessage(packet) { this.sent.push(packet); }
    terminate() { this.stopped = true; }
    emit(data) { this.onmessage({data}); }
  }
  const canvas = {width: 0, height: 0, getContext: () => ({drawImage() {}, getImageData: () => ({data: new Uint8ClampedArray(4)})})};
  const context = vm.createContext({Worker, document: {createElement: () => canvas}, performance: {now: () => now}, Error});
  vm.runInContext(fs.readFileSync(new URL('../temporal-camera.js', import.meta.url), 'utf8').replace('export function', 'function'), context);
  const camera = context.createTemporalCamera({onDetection: data => detections.push(data), onGap: () => gaps++, onError: e => errors.push(e)});
  const video = {videoWidth: 640, videoHeight: 480};
  return {camera, worker, detections, errors, gaps: () => gaps, push(t) {now = t; camera.push(video, t, true);}, time(t) {now = t;}, ready() {worker.emit({type: 'ready', delegate: 'CPU'});}};
}

test('reset discards an in-flight result and continues with new frames', async () => {
  const s = setup(); s.ready(); await s.camera.ready;
  s.push(0); const old = s.worker.sent.at(-1); s.camera.reset(); s.push(100);
  s.worker.emit({...old, type: 'frame'}); assert.equal(s.detections.length, 0);
  s.worker.emit({...s.worker.sent.at(-1), type: 'frame'}); assert.equal(s.detections.length, 1);
  s.camera.close();
});
test('late results cancel capture instead of producing stale suggestions', async () => {
  const s = setup(); s.ready(); await s.camera.ready; s.push(0);
  const frame = s.worker.sent.at(-1), before = s.gaps(); s.time(2600);
  s.worker.emit({...frame, type: 'frame'});
  assert.equal(s.detections.length, 0); assert.equal(s.gaps(), before + 1); s.camera.close();
});
test('queue overload resets capture and never emits the previous generation', async () => {
  const s = setup(); s.ready(); await s.camera.ready; s.push(0);
  const first = s.worker.sent.at(-1), before = s.gaps();
  for (let i = 1; i <= 40; i++) s.push(i * 60);
  assert.ok(s.gaps() > before); assert.equal(s.worker.sent.length, 2);
  s.worker.emit({...first, type: 'frame'}); assert.equal(s.detections.length, 0); s.camera.close();
});
test('closing terminates the worker and ignores responses and new frames', async () => {
  const s = setup(); s.ready(); await s.camera.ready; s.push(0); const frame = s.worker.sent.at(-1);
  s.camera.close(); s.camera.close(); s.worker.emit({...frame, type: 'frame'}); s.push(100);
  assert.ok(s.worker.stopped); assert.equal(s.detections.length, 0); assert.equal(s.worker.sent.length, 2);
});
test('initialization errors reject readiness and report the failure', async () => {
  const s = setup(), rejected = assert.rejects(s.camera.ready, /download failed/);
  s.worker.emit({type: 'error', message: 'download failed'}); await rejected;
  assert.deepEqual(s.errors, ['download failed']); s.camera.close();
});
