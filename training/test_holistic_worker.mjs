import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHolisticWorkerTracker} from '../holistic-worker-tracker.js';
import {BODY_TRACKING_OPTIONS,createHolisticBodyTracker,createLandmarkCapture} from '../landmark-capture.js';
import {bindLegacyWorkerContext,legacyCpuInference} from '../legacy-holistic-worker-context.js';

function fake({copyImage, timeoutMs = 5000} = {}) {
  const worker = {messages: [], terminated: false,
    postMessage(data, transfers) {this.messages.push({data, transfers});},
    terminate() {this.terminated = true;},
    reply(data) {this.onmessage({data});}};
  let copies = 0, released = 0;
  const promise = createHolisticWorkerTracker({makeWorker: () => worker, timeoutMs,
    copyImage: copyImage || (async image => {copies++;return {width: image.width, height: image.height, close() {released++;}};})});
  const init = worker.messages[0].data;
  worker.reply({type: 'ready', id: init.id, kind: 'Worker Holistic'});
  return {worker, promise, copies: () => copies, released: () => released};
}
const flush = async () => {for (let i = 0; i < 8; i++) await Promise.resolve();};
function replyFrame(s, overrides = {}) {
  const d = s.worker.messages.at(-1).data;
  s.worker.reply({type: 'result', id: d.id, epoch: d.epoch, width: d.bitmap.width, height: d.bitmap.height,
    kind: 'Worker Holistic', result: {poseLandmarks: []}, ...overrides});
}
test('worker uses unchanged body options and transfers a copy, not the source', async () => {
  const s = fake(), tracker = await s.promise, source = {width: 640, height: 480};let output;
  assert.deepEqual(s.worker.messages[0].data.options, BODY_TRACKING_OPTIONS);
  tracker.onResults(r => output = r);const pending = tracker.send({image: source});await flush();
  const sent = s.worker.messages.at(-1);assert.notEqual(sent.data.bitmap, source);
  assert.deepEqual(sent.transfers, [sent.data.bitmap]);replyFrame(s);await pending;
  assert.deepEqual(output, {poseLandmarks: []});assert.equal(s.copies(), 1);assert.equal(s.released(), 1);
  assert.equal(tracker.executionContext, 'worker');tracker.close();assert.equal(s.worker.terminated, true);
});
test('reset and another send cannot race an image copy', async () => {
  let finish;const s = fake({copyImage: () => new Promise(r => finish = r)}), t = await s.promise;
  const send = t.send({image: {}});
  await assert.rejects(t.reset(), /active/);await assert.rejects(t.send({image: {}}), /Concurrent/);
  finish({width: 2, height: 3, close() {}});await flush();replyFrame(s);await send;t.close();
});
test('closing during copy releases the image without posting or delivering a result', async () => {
  let finish, closed = 0, results = 0;const s = fake({copyImage: () => new Promise(r => finish = r)}), t = await s.promise;
  t.onResults(() => results++);const send = t.send({image: {}});t.close();
  finish({width: 2, height: 3, close() {closed++;}});await assert.rejects(send, /closed/);
  assert.equal(closed, 1);assert.equal(s.worker.messages.length, 1);assert.equal(results, 0);
});
test('reset advances epoch only after the worker has acknowledged it', async () => {
  const s = fake(), t = await s.promise;const reset = t.reset();
  const d = s.worker.messages.at(-1).data;assert.equal(d.epoch, 1);
  await assert.rejects(t.send({image: {}}), /Concurrent/);
  s.worker.reply({type: 'ready', id: d.id});await reset;
  const send = t.send({image: {width: 5, height: 4}});await flush();assert.equal(s.worker.messages.at(-1).data.epoch, 1);
  replyFrame(s);await send;t.close();
});
test('wrong epoch or dimensions never delivers body landmarks', async () => {
  for (const overrides of [{epoch: 4}, {width: 9}]) {
    const s = fake(), t = await s.promise;let results = 0;t.onResults(() => results++);
    const send = t.send({image: {width: 5, height: 4}});await flush();replyFrame(s, overrides);
    await assert.rejects(send, /identity/);assert.equal(results, 0);t.close();
  }
});
test('worker errors permanently terminate the failed graph', async () => {
  const s = fake(), t = await s.promise;const send = t.send({image: {width: 5, height: 4}});await flush();
  s.worker.onerror({message: 'Graph failed'});await assert.rejects(send, /Graph failed/);
  assert.equal(s.worker.terminated, true);await assert.rejects(t.reset(), /active/);
});
test('a timed-out worker is terminated and late results cannot reach a new take', async () => {
  const s = fake({timeoutMs: 10}), t = await s.promise;let outputs = 0;t.onResults(() => outputs++);
  const send = t.send({image: {width: 5, height: 4}});await assert.rejects(send, /timed out/);
  replyFrame(s);assert.equal(outputs, 0);assert.equal(s.worker.terminated, true);
});
test('legacy SDK adapter binds only its already-initialized isolated context', () => {
  const canvas = {}, context = {canvas}, graph = {m: canvas, i: {GL: {currentContext: {GLctx: context}}}};
  bindLegacyWorkerContext({h: graph}, '0.5.1675471629');assert.equal(graph.K, context);
  assert.throws(() => bindLegacyWorkerContext({h: graph}, 'other'), /Unsupported/);
  assert.throws(() => bindLegacyWorkerContext({h: {...graph, m: {}}}, '0.5.1675471629'), /Missing/);
  assert.throws(() => bindLegacyWorkerContext({h: {...graph, K: {}}}, '0.5.1675471629'), /differs/);
});
test('supported capture selects the worker; worker failures cannot silently reintroduce UI inference',async()=>{
  let fallback=0;const worker={executionContext:'worker'};
  assert.equal(await createHolisticBodyTracker({supportsWorker:()=>true,workerFactory:async()=>worker,mainThreadFactory:()=>fallback++}),worker);
  await assert.rejects(createHolisticBodyTracker({supportsWorker:()=>true,workerFactory:async()=>{throw new Error('bad graph');},mainThreadFactory:()=>fallback++}),/bad graph/);
  assert.equal(fallback,0);
});
test('browsers without worker canvas support retain the legacy compatibility path',async()=>{
  let workers=0;const legacy={executionContext:'main-thread'};
  assert.equal(await createHolisticBodyTracker({supportsWorker:()=>false,workerFactory:()=>workers++,mainThreadFactory:async()=>legacy}),legacy);
  assert.equal(workers,0);
});
test('closing during tracker initialization closes the eventually-created worker',async()=>{
  let finish,closes=0,delivered=0;const model={close(){closes++;},onResults(){delivered++;}};
  const capture=createLandmarkCapture({createTracker:()=>new Promise(r=>finish=r)});
  const begin=capture.begin({owner:Symbol(),isRunning:()=>true,onPhase(){},onError(){},onComplete(){}});
  await flush();capture.close();finish(model);await begin;assert.equal(closes,1);assert.equal(delivered,0);
});
test('legacy CPU execution preference preserves iOS and software-renderer behavior',()=>{
  assert.equal(legacyCpuInference('CPU',{platform:'Win32'}),true);
  assert.equal(legacyCpuInference('GPU',{platform:'iPhone'}),true);
  assert.equal(legacyCpuInference('GPU',{platform:'MacIntel',maxTouchPoints:5}),true);
  assert.equal(legacyCpuInference('GPU',{platform:'MacIntel',maxTouchPoints:0}),false);
  assert.equal(legacyCpuInference('GPU',{platform:'Win32'}),false);
});
test('application and both body vocabularies use one cache-versioned capture module',()=>{
  const read=p=>readFileSync(new URL('../'+p,import.meta.url),'utf8');
  for(const p of ['app.js','beginner-recognition.js','capstone-recognition.js'])
    assert.match(read(p),/from '\.\/landmark-capture\.js\?v=20261108-capture-11'/);
  assert.match(read('index.html'),/app\.js\?v=20261108-capture-worker-8/);
});
