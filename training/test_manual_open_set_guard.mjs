import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';
import {GUARD_VERSION,GUARD_MODES,validManualOpenSetGuard,manualGuardStatistics,applyManualOpenSetGuard} from './experimental/manual_open_set_guard.mjs';
const seq=(x=0)=>Array.from({length:20},()=>[1,...Array.from({length:63},(_,i)=>i%3===0?x:0),...Array(64).fill(0)]);
const model=()=>({version:1,featureVersion:GUARD_VERSION,encoding:'two-hand-motion-v3',samples:[{label:'A',sequence:seq()},{label:'OTHER',sequence:seq(2)}],
  modes:Object.fromEntries(GUARD_MODES.map(m=>[m,{enabled:true,labels:['A'],maxDistance:.5,minRatio:1}]))});
const baseline=label=>Object.fromEntries(GUARD_MODES.map(m=>[m,label]));
test('candidate never creates or changes an accepted baseline word',()=>{
  const m=model();assert.equal(validManualOpenSetGuard(m),true);
  assert.deepEqual(applyManualOpenSetGuard(m,seq(),baseline(null)).predictions,baseline(null));
  assert.deepEqual(applyManualOpenSetGuard(m,seq(),baseline('A')).predictions,baseline('A'));
  assert.deepEqual(applyManualOpenSetGuard(m,seq(2),baseline('A')).predictions,baseline(null));
  assert.deepEqual(applyManualOpenSetGuard(m,seq(),baseline('OTHER')).predictions,baseline(null));
});
test('blank, malformed, nonfinite and unsupported input is rejected',()=>{
  for(const bad of [null,[],seq().slice(1),Array.from({length:20},()=>Array(128).fill(0))]){
    assert.equal(manualGuardStatistics(model(),bad),null);
    assert.deepEqual(applyManualOpenSetGuard(model(),bad,baseline('A')).predictions,baseline(null));
  }
  const bad=seq();bad[0][1]=Infinity;assert.equal(manualGuardStatistics(model(),bad),null);
  const m=model();m.samples[0].sequence=bad;assert.equal(validManualOpenSetGuard(m),false);
  assert.throws(()=>applyManualOpenSetGuard(m,seq(),baseline('A')));
});
test('failed validation mode is explicitly disabled rather than forced to reject all',()=>{
  const m=model();m.modes.default.enabled=false;
  const result=applyManualOpenSetGuard(m,seq(2),baseline('A'));
  assert.equal(result.predictions.default,'A');assert.equal(result.diagnostics.default.reason,'guard-disabled');
  assert.equal(result.predictions.expanded,null);
});
test('input arrays and baseline modes are not mutated or oracle-controlled',()=>{
  const m=model(),s=seq(),b=baseline('A'),old=structuredClone({m,s,b});
  const r=applyManualOpenSetGuard(m,s,b);assert.deepEqual({m,s,b},old);
  assert.equal(r.predictions.default,'A');assert.throws(()=>applyManualOpenSetGuard(m,s,{expected:'A'}));
});
test('open-set candidate stays offline with no camera/network/storage entry point',()=>{
  for(const n of ['app.js','motion-studio.js','research_words.py','landmark-capture.js','beginner-recognition.js','capstone-recognition.js'])
    assert.doesNotMatch(readFileSync(new URL('../'+n,import.meta.url),'utf8'),/manual_open_set_guard|applyManualOpenSetGuard/);
  assert.doesNotMatch(readFileSync(new URL('./experimental/manual_open_set_guard.mjs',import.meta.url),'utf8'),/fetch\(|getUserMedia|localStorage|sessionStorage|document\.|window\./);
});
test('actual baseline rejects unusable sequences before specialist scores',async()=>{
  const {predictManualRoutes}=await import('./experimental/online_manual_runtime.mjs');
  assert.deepEqual(predictManualRoutes({},Array.from({length:32},()=>[null,null]),1),baseline(null));
});
