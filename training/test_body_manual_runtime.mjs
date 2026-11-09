import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {tensorizeBodyManual, mirrorBodyManual, bodyManualDistances, predictBodyManual, validBodyManualModel, FEATURE_VERSION} from './experimental/body_manual_runtime.mjs';

const row = (aspect = 1) => ({imageAspect: aspect, frames: Array.from({length: 6}, () => ({
  pose: [[.5,.2],[.48,.2],[.52,.2],[.3,.4],[.7,.4],[.3,.6],[.7,.6]],
  left: Array.from({length: 21}, (_, i) => [.5+i*.002,.3+i*.003,i*.001]),right: null,
}))});
const model = () => ({version:1,featureVersion:FEATURE_VERSION,labels:['ONE'],featureParameters:{},
  parameters:{maxDistance:.1,minRatio:1,minVotes:1,strongRatio:2,mirror:true},
  samples:[{label:'ONE',sequence:tensorizeBodyManual(row())},{label:'OTHER MOVEMENT',sequence:tensorizeBodyManual({...row(),imageAspect:2})}]});

test('offline features preserve body location, absence, and exact input arrays', () => {
  const input=row(),before=structuredClone(input),a=tensorizeBodyManual(input);
  assert.deepEqual(input,before);assert.equal(a.length,20);assert.equal(a[0].length,146);
  for(const f of a) {assert.equal(f[145],0);assert.ok(f.slice(16,18).every(v=>v===0));assert.ok(f.slice(81,144).every(v=>v===0));}
  const moved=row();for(const f of moved.frames)for(const p of f.left)p[1]+=.2;
  assert.ok(bodyManualDistances(a,[tensorizeBodyManual(moved)])[0]>.1);
  assert.equal(bodyManualDistances(a,[a])[0],0);
});
test('image aspect is height/width and anatomical mirroring is reversible', () => {
  const a=tensorizeBodyManual(row()),b=row(2);
  for(const f of b.frames)for(const p of [...f.pose,...f.left])p[1]/=2;
  assert.deepEqual(a,tensorizeBodyManual(b));assert.deepEqual(mirrorBodyManual(mirrorBodyManual(a)),a);
});
test('blank, too-short, nonfinite, malformed, and degenerate inputs are rejected', () => {
  for(const aspect of [null,NaN,0,true,'1',6])assert.equal(tensorizeBodyManual(row(aspect)),null);
  for(const mutate of [r=>r.frames.splice(0,2),r=>r.frames.forEach(f=>f.left=null),
    r=>r.frames[0].left.pop(),r=>r.frames[0].pose[0][0]=Infinity,r=>r.frames.forEach(f=>f.pose[4]=f.pose[3])]) {
    const r=row();mutate(r);assert.equal(tensorizeBodyManual(r),null);
  }
});
test('resampling cannot invent a hand across a missing-frame gap', () => {
  const r=row();r.frames.splice(3,0,{pose:structuredClone(r.frames[0].pose),left:null,right:null});
  const a=tensorizeBodyManual(r);assert.ok(a.some(f=>f[144]===0));
  for(const f of a.filter(f=>f[144]===0)){assert.ok(f.slice(14,16).every(v=>v===0));assert.ok(f.slice(18,81).every(v=>v===0));}
});
test('distance dimensions, weights, and feature masks are checked', () => {
  const a=tensorizeBodyManual(row());assert.throws(()=>bodyManualDistances(a,[a.slice(1)]));
  assert.throws(()=>bodyManualDistances(a,[a],{missing_cost:-1}));
  assert.throws(()=>bodyManualDistances(a,[a],{invented:1}));
  const bad=structuredClone(a);bad[0][144]=.5;assert.throws(()=>mirrorBodyManual(bad));
});
test('prediction uses only measured features, never an expected lesson label', () => {
  const m=model();assert.equal(validBodyManualModel(m),true);
  assert.equal(predictBodyManual(m,{...row(),label:'FORCED',expected:'FORCED',id:'forced'}).prediction,'ONE');
  const empty=row();empty.frames.forEach(f=>f.left=null);assert.equal(predictBodyManual(m,empty).prediction,null);
  m.parameters.maxDistance=-1;assert.throws(()=>predictBodyManual(m,row()));
});
test('the parity candidate has no production or camera entry point', () => {
  for(const name of ['index.html','app.js','landmark-capture.js','beginner-recognition.js','capstone-recognition.js'])
    assert.doesNotMatch(readFileSync(new URL('../'+name,import.meta.url),'utf8'),/experimental\/body_manual_runtime|predictBodyManual/);
  assert.doesNotMatch(readFileSync(new URL('./experimental/body_manual_runtime.mjs',import.meta.url),'utf8'),/getUserMedia|fetch\(|localStorage|sessionStorage|document\.|window\./);
});
