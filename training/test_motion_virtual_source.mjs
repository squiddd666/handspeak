import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source = readFileSync(new URL('./ux/motion_virtual_source.js', import.meta.url), 'utf8');
function runtime(host = '127.0.0.1') {
  let realCameraCalls = 0, serverCalls = 0;
  const window = {HANDSPEAK_VIRTUAL_FIXTURE: {width: 960, height: 720, items: []},
    fetch: async () => {serverCalls++; return {ok: true};}, addEventListener() {}};
  const navigator = {mediaDevices: {getUserMedia: async () => {realCameraCalls++;}}};
  const document = {createElement: tag => tag === 'canvas'
    ? {getContext: () => ({fillRect() {}}), captureStream: () => ({virtual: true})}
    : {addEventListener() {}, readyState: 0, currentTime: 0},
    addEventListener() {}, getElementById: () => null};
  const scope = {window, navigator, document, location: {hostname: host, href: `http://${host}:8000/test.html`, origin: `http://${host}:8000`},
    URL, setInterval: () => 1, clearInterval() {}, setTimeout: () => 1, clearTimeout() {}, performance: {now: () => 0}};
  const context = vm.createContext(scope);
  return {scope, run: () => vm.runInContext(source, context), cameraCalls: () => realCameraCalls, serverCalls: () => serverCalls};
}

test('virtual source fails closed off the isolated loopback host', async () => {
  const r = runtime('example.test');
  assert.throws(r.run, /refused a non-isolated host/);
  await assert.rejects(r.scope.navigator.mediaDevices.getUserMedia({video: true}), /isolated loopback host/);
  assert.equal(r.cameraCalls(), 0);
});
test('camera cannot start before the visible virtual-only marker exists', async () => {
  const r = runtime(); r.run();
  await assert.rejects(r.scope.navigator.mediaDevices.getUserMedia({video: true}), /marker not ready/);
  assert.equal(r.cameraCalls(), 0);
});
test('microphone requests never fall back to a real device', async () => {
  const r = runtime(); r.run();
  await assert.rejects(r.scope.navigator.mediaDevices.getUserMedia({video: true, audio: true}), /prohibited/);
  assert.equal(r.cameraCalls(), 0);
});
test('local test storage is in-memory and separate from personal storage', () => {
  const r = runtime(); r.run();
  r.scope.window.localStorage.setItem('test', '123');
  assert.equal(r.scope.window.localStorage.getItem('test'), '123');
  assert.equal(r.scope.window.sessionStorage.getItem('test'), null);
  assert.equal(r.scope.window.localStorage.length, 1);
});
test('unrelated same-origin server writes are blocked', async () => {
  const r = runtime(); r.run();
  await assert.rejects(r.scope.window.fetch('/api/session', {method: 'POST', body: '{}'}), /blocks unrelated server writes/);
  assert.equal(r.serverCalls(), 0);
});
test('recognition calls pass through without substituting results', async () => {
  const r = runtime(); r.run();
  assert.deepEqual(await r.scope.window.fetch('/api/capstone-asl', {method: 'POST', body: '{}'}), {ok: true});
  assert.equal(r.serverCalls(), 1);
});

test('only an opted-in authorized local scalar checkpoint may be written',async()=>{
  const r=runtime();
  r.scope.window.HANDSPEAK_VIRTUAL_FIXTURE.auditCheckpoint={endpoint:'/__motion_audit__/checkpoint',token:'fixture-token'};
  r.run();
  await assert.rejects(r.scope.window.fetch('/__motion_audit__/checkpoint',{method:'POST',body:'{}'}),/blocks unrelated/);
  await assert.rejects(r.scope.window.fetch('/__motion_audit__/checkpoint',{method:'POST',headers:{'X-Motion-Audit':'wrong'},body:'{}'}),/blocks unrelated/);
  await r.scope.window.fetch('/__motion_audit__/checkpoint',{method:'POST',headers:{'X-Motion-Audit':'fixture-token'},body:'{}'});
  assert.equal(r.serverCalls(),1);assert.equal(r.cameraCalls(),0);
  await assert.rejects(r.scope.window.fetch('/api/session',{method:'POST',headers:{'X-Motion-Audit':'fixture-token'},body:'{}'}),/blocks unrelated/);
});
test('fixture has no app-click automation and exports no raw coordinate arrays', () => {
  assert.doesNotMatch(source, /\.click\(/);
  assert.doesNotMatch(source, /(?:take|report)\.(?:frames|sequence|pose|landmarks)\s*=/);
  assert.match(source, /canvas\.captureStream\(30\)/);
});
