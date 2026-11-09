import test from 'node:test';
import assert from 'node:assert/strict';
import {createLandmarkCapture} from '../landmark-capture.js';

const flush = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };
const landmarks = n => Array.from({length: n}, (_, i) => ({x: .2 + i / 100, y: .3, z: 0}));
const valid = () => ({poseLandmarks: landmarks(33), leftHandLandmarks: landmarks(21)});
function setup({restoreResult=null}={}) {
  let now = 0, serial = 0, created = 0, released = 0;
  const timers = new Map(), models = [], phases = [], completed = [], errors = [];
  const capture = createLandmarkCapture({clock: () => now,
    setTimer: (fn, ms) => {const id = ++serial; timers.set(id, {fn, at: now + ms}); return id;},
    clearTimer: id => timers.delete(id),
    snapshotFrame: video => ({image: {currentTime: video.currentTime}, dimensions: [640, 480],
      cropped:Boolean(restoreResult), restore:restoreResult, dispose: () => released++}),
    createTracker: async () => {
      created++;
      const model = {closed: false, sent: [], resets: 0, onResults(fn) {this.callback = fn;},
        reset() {this.resets++;},
        send({image}) {return new Promise((resolve, reject) => this.sent.push({resolve, reject, time: image.currentTime}));},
        close() {this.closed = true;},
        emit(result = valid()) {this.callback(result); this.sent.at(-1).resolve();}};
      models.push(model); return model;
    },
  });
  const video = {readyState: 2, currentTime: 0};
  const owner = Symbol('test');
  const options = key => ({owner: key, isRunning: () => true,
    onPhase: phase => phases.push(phase), onComplete: (frames, info) => completed.push({frames, info}),
    onError: error => errors.push(error.message)});
  const advance = ms => {
    const target = now + ms;
    for (;;) {
      const due = [...timers.entries()].filter(([, t]) => t.at <= target).sort((a, b) => a[1].at - b[1].at)[0];
      if (!due) break;
      now = due[1].at;
      timers.delete(due[0]); due[1].fn();
    }
    now = target;
  };
  async function frame(result = valid(), ms = 100, key = owner) {
    advance(ms); video.currentTime += ms / 1000;
    const prior = models.at(-1).sent.length;
    capture.frame(key, now, video); await flush();
    if (models.at(-1).sent.length > prior) {models.at(-1).emit(result); await flush();}
  }
  return {capture, owner, options, video, phases, completed, errors, models,
    created: () => created, released: () => released, time: () => now, advance, frame,
    begin: async (key = owner) => {await capture.begin(options(key)); await flush();},
    warm: async () => {await frame(); advance(1400); await flush();},
  };
}

test('countdown warms the real tracker but contributes no model frames', async () => {
  const s = setup(); await s.begin(); await s.warm();
  assert.equal(s.phases.at(-1), 'recording');
  await s.frame(); s.advance(4000); await flush();
  assert.equal(s.completed[0].frames.length, 1);
  assert.equal(s.completed[0].info.warmupFrames, 1);
});

test('each new take resets temporal tracking only after a canceled send finishes',async()=>{
  const s=setup();await s.begin();await s.warm();
  assert.equal(s.models[0].resets,1);
  s.advance(100);s.video.currentTime+=.1;
  s.capture.frame(s.owner,s.time(),s.video);await flush();
  s.capture.cancel(s.owner);
  const next=s.begin();await flush();
  assert.equal(s.models[0].resets,1);
  assert.equal(s.phases.at(-1),'loading');
  s.models[0].emit();await next;
  assert.equal(s.models[0].resets,2);
  assert.equal(s.phases.at(-1),'countdown');
  await s.warm();await s.frame();s.advance(4000);await flush();
  assert.equal(s.completed[0].frames.length,1);
});

test('blank or malformed warm-ups cannot start a body recording', async () => {
  const s = setup(); await s.begin();
  await s.frame({}); s.advance(1400); await flush();
  assert.equal(s.phases.at(-1), 'countdown');
  await s.frame({poseLandmarks: landmarks(32)});
  assert.equal(s.phases.at(-1), 'countdown');
  await s.frame({poseLandmarks: landmarks(33)});
  assert.equal(s.phases.at(-1), 'recording');
  await s.frame(); s.advance(4000); await flush();
  assert.equal(s.completed[0].info.warmupFrames, 3);
  assert.equal(s.completed[0].info.poseWarmupFrames, 1);
  assert.equal(s.completed[0].frames.length, 1);
});

test('persistent missing pose fails readiness rather than recording a blank take', async () => {
  const s = setup(); await s.begin(); await s.frame({});
  s.advance(15000); await flush();
  assert.equal(s.phases.includes('recording'), false);
  assert.equal(s.completed.length, 0);
  assert.match(s.errors[0], /could not warm up/);
});

test('recording cannot start until the in-flight warm-up has completed', async () => {
  const s = setup(); await s.begin();
  s.capture.frame(s.owner, s.time(), s.video); await flush();
  s.advance(1500);
  assert.equal(s.phases.at(-1), 'countdown');
  s.models[0].emit(); await flush();
  assert.equal(s.phases.at(-1), 'recording');
  s.advance(4000); await flush();
  assert.equal(s.completed[0].frames.length, 0);
});

test('deadline drains and retains the last recording result even while busy', async () => {
  const s = setup(); await s.begin(); await s.warm();
  s.advance(100); s.video.currentTime += .1;
  s.capture.frame(s.owner, s.time(), s.video); await flush();
  s.advance(3900);
  assert.equal(s.phases.at(-1), 'draining');
  assert.equal(s.completed.length, 0);
  s.models[0].emit(); await flush();
  assert.equal(s.completed[0].frames.length, 1);
  assert.equal(s.capture.active(s.owner), false);
});

test('capture finishes on a timer without waiting for a new camera frame', async () => {
  const s = setup(); await s.begin(); await s.warm();
  for (let i = 0; i < 5; i++) await s.frame();
  s.advance(3500); await flush();
  assert.equal(s.completed[0].frames.length, 5);
});

test('duplicate images are never counted as fresh tracked frames', async () => {
  const s = setup(); await s.begin(); await s.warm(); await s.frame();
  const count = s.models[0].sent.length;
  s.advance(100); s.capture.frame(s.owner, s.time(), s.video); await flush();
  assert.equal(s.models[0].sent.length, count);
  s.advance(4000); await flush();
  assert.equal(s.completed[0].frames.length, 1);
});

test('invalid pose, malformed hands, and blank frames cannot pass as tracking', async () => {
  const s = setup(); await s.begin(); await s.warm();
  await s.frame({});
  await s.frame({poseLandmarks: landmarks(33), leftHandLandmarks: landmarks(20)});
  const bad = valid(); bad.poseLandmarks[12].x = NaN; await s.frame(bad);
  await s.frame(valid());
  s.advance(4000); await flush();
  assert.equal(s.completed[0].frames.length, 1);
  assert.equal(s.completed[0].frames[0].right, null);
});

test('canceling a countdown cancels its timer and any later tracking result', async () => {
  const s = setup(); await s.begin();
  s.capture.frame(s.owner, s.time(), s.video); await flush();
  s.capture.cancel(s.owner); s.advance(20000); s.models[0].emit(); await flush();
  assert.equal(s.phases.includes('recording'), false);
  assert.equal(s.completed.length, 0);
  assert.equal(s.errors.length, 0);
});

test('two vocabularies reuse one graph and cannot consume each other’s take', async () => {
  const s = setup(); await s.begin(); await s.warm();
  const second = Symbol('second'); await s.begin(second);
  await s.frame(valid(), 100, second); s.advance(1400); await flush();
  const count = s.models[0].sent.length;
  s.video.currentTime += .1; s.capture.frame(s.owner, s.time(), s.video); await flush();
  assert.equal(s.models[0].sent.length, count);
  await s.frame(valid(), 100, second); s.advance(4000); await flush();
  assert.equal(s.created(), 1);
  assert.equal(s.completed[0].frames.length, 1);
});

test('a hung final send times out and a retry builds a fresh tracker', async () => {
  const s = setup(); await s.begin(); await s.warm();
  s.advance(100); s.video.currentTime += .1; s.capture.frame(s.owner, s.time(), s.video); await flush();
  s.advance(28900); await flush();
  assert.match(s.errors[0], /captured camera frames timed out/);
  assert.equal(s.models[0].closed, true);
  await s.begin(); await s.warm(); await s.frame();
  // A late result from the closed graph must not be attributed to the new graph.
  s.models[0].emit(); await flush(); s.advance(4000); await flush();
  assert.equal(s.created(), 2);
  assert.equal(s.completed[0].frames.length, 1);
});

test('closing cancels capture and rejects any subsequent start', async () => {
  const s = setup(); await s.begin(); s.capture.close(); s.advance(20000);
  assert.equal(s.models[0].closed, true);
  assert.equal(s.completed.length, 0);
  await assert.rejects(s.begin(), /closed/);
});

test('busy tracker buffers distinct real images and drains the complete recording', async () => {
  const s = setup(); await s.begin(); await s.warm();
  const warmupReleased=s.released();
  s.advance(100); s.video.currentTime = 1;
  s.capture.frame(s.owner, s.time(), s.video); await flush();
  s.advance(100); s.video.currentTime = 2;
  s.capture.frame(s.owner, s.time(), s.video); await flush();
  s.video.currentTime = 99; // A buffered image must not alias the changing video.
  s.advance(3800); await flush();
  assert.equal(s.completed.length, 0);
  s.models[0].emit(); await flush();
  assert.equal(s.models[0].sent.at(-1).time, 2);
  assert.equal(s.completed.length, 0);
  s.models[0].emit(); await flush();
  assert.equal(s.completed[0].frames.length, 2);
  assert.equal(s.completed[0].info.sampledFrames, 2);
  assert.equal(s.released()-warmupReleased, 2);
});

test('cancellation releases pending snapshots without counting their results', async () => {
  const s = setup(); await s.begin(); await s.warm();
  const warmupReleased=s.released();
  for (let i = 0; i < 3; i++) {
    s.advance(100); s.video.currentTime += .1;
    s.capture.frame(s.owner, s.time(), s.video); await flush();
  }
  s.capture.cancel(s.owner);
  assert.equal(s.released()-warmupReleased, 2);
  s.models[0].emit(); await flush();
  assert.equal(s.released()-warmupReleased, 3);
  assert.equal(s.completed.length, 0);
});

test('padding is restored before readiness, overlay and model coordinates are used',async()=>{
  const original=valid();original.leftHandLandmarks[0]={x:.25,y:.3,z:.1};
  let restorations=0,seen;
  const s=setup({restoreResult:result=>{
    restorations++;return {...result,leftHandLandmarks:result.leftHandLandmarks.map(p=>({...p,x:.2+p.x*.6,z:p.z*.6}))};
  }});
  await s.capture.begin({...s.options(s.owner),onTracking:value=>{seen=value;}});await flush();
  await s.frame(original);s.advance(1400);await flush();await s.frame(original);s.advance(4000);await flush();
  assert.equal(restorations,2);assert.equal(s.completed[0].info.paddingFrames,1);
  assert.equal(s.completed[0].frames[0].left[0][0],.35);
  assert.equal(s.completed[0].frames[0].left[0][2],.06);
  assert.equal(seen.landmarks[0][0].x,.35);
  assert.equal(original.leftHandLandmarks[0].x,.25);
});

test('capture buffering has a strict 80-image memory bound', async () => {
  const s = setup(); await s.begin(); await s.warm();
  for (let i = 0; i < 150; i++) {
    s.video.currentTime += .1;
    s.capture.frame(s.owner, s.time() + i * 25, s.video); await flush();
  }
  s.capture.cancel(s.owner);
  assert.ok(s.released() <= 79);
  s.models[0].emit(); await flush();
  assert.ok(s.released() <= 80);
});
