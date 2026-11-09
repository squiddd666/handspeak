import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const page=readFileSync(new URL('./experimental/online_worker_audit_page.mjs',import.meta.url),'utf8');
const runner=readFileSync(new URL('./ux/run_online_worker_audit.mjs',import.meta.url),'utf8');
test('worker audit explicitly uses integrated default capture version',()=>{
  assert.match(page,/landmark-capture\.js\?v=20261108-capture-11/);
  assert.match(page,/bodyFactory:\(\)=>createHolisticBodyTracker\(\)/);
  assert.match(page,/info\.trackerExecutionContext==='worker'/);
});
test('API payloads contain only actual body frames and consent/vocabulary',()=>{
  assert.match(page,/\{consent:true,frames\}:\{consent:true,frames,vocabulary:mode\.split/);
  assert.doesNotMatch(page,/minScore\s*:/);
  assert.match(page,/frames\.length>=5/);
  assert.match(page,/for\(const mode of productionModes\)/);
  assert.match(page,/data\.predictions\?\.\[0\]\?\.label/);
});
test('owned browser has no user profile and audits cannot replay',()=>{
  assert.match(runner,/Profile already used/);assert.match(runner,/--disable-quic/);
  assert.match(runner,/scripts\.serve_online_worker_audit/);assert.match(runner,/verifyAll\(\)/);
  assert.match(page,/One-pass audit already started/);assert.match(runner,/cleanup-receipt\.json/);
});
