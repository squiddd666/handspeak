import test from 'node:test';import assert from 'node:assert/strict';
import {serializePair,captureContract} from './experimental/domain_capture_contract.mjs';
const points=n=>Array.from({length:n},(_,i)=>({x:i/100,y:i/100,z:0}));
const pair=(timestamp=1000)=>({epoch:1,timestamp,width:640,height:480,pixelEquality:true,
  body:{poseLandmarks:points(33),leftHandLandmarks:points(21),rightHandLandmarks:null,image:{secret:'must not persist'}},
  manual:{landmarks:[points(21)],handedness:[[{categoryName:'Right'}]],image:{secret:'must not persist'}}});
function fixture(){const p=pair(),s=serializePair(p);return {p,frames:[s.body],info:{processedFrames:1,sampledFrames:1,trackerExecutionContext:'worker'}};}
test('persists only independently measured landmarks, not detector images',()=>{
  const s=serializePair(pair());assert.equal(s.body.pose.length,7);assert.equal(s.manual[0],null);assert.equal(s.manual[1].length,21);
  assert.ok(!JSON.stringify(s).includes('secret'));assert.ok(!JSON.stringify(s).includes('image'));assert.equal(s.body.left.length,21);
});
test('uses exact production body payload and excludes countdown samples',()=>{
  const {p,frames,info}=fixture(),r=captureContract([pair(999),p],frames,info,1000,5000);
  assert.equal(r.passed,true);assert.equal(r.samples.length,1);
});
test('rejects changed body output, missing pairs, geometry and timestamp contracts',()=>{
  const {p,frames,info}=fixture();assert.equal(captureContract([p],[],info,1000,5000).passed,false);
  assert.equal(captureContract([p],frames,{...info,processedFrames:2},1000,5000).passed,false);
  assert.equal(captureContract([{...p,width:960}],frames,info,1000,5000).passed,false);
  assert.equal(captureContract([p,p],frames,{...info,processedFrames:2,sampledFrames:2},1000,5000).checks.monotonicTimestamps,false);
  assert.equal(captureContract([{...p,pixelEquality:false}],frames,info,1000,5000).passed,false);
});
test('nonfinite coordinates become missing, never fabricated observations',()=>{
  const p=pair();p.body.leftHandLandmarks[0].x=NaN;const r=serializePair(p);assert.equal(r.body.left,null);
  assert.equal(r.manual[1].length,21);
});
test('both failed streams and empty captures retain explicit failing contracts',()=>{
  const r=captureContract([],[],{},Infinity,-Infinity);assert.equal(r.passed,false);assert.deepEqual(r.samples,[]);
  // Failed begin/warmup returns no metrics: transmitted zero counts must agree
  // with the receiver, while the overall missing-stream contract still fails.
  assert.equal(r.checks.pairedProcessing,true);assert.equal(r.checks.productionSampling,false);
});
