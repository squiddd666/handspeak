import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createDualTracker,MANUAL_OPTIONS,pixelDigest} from './experimental/dual_capture.mjs';
const flush=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
async function setup({mismatch=false,fail=false}={}){
  let emit,bodyImage,manualImage,dispose=0,bodyDone,manualDone,bodyReset=0,manualReset=0;
  const bodyResult={leftHandLandmarks:[{x:.1}],poseLandmarks:[{x:.4}]};
  const manualResult={landmarks:[[{x:.9}]],timestamp:10,epoch:1,width:640,height:480,pixelDigest:'same'};
  const body={onResults(fn){emit=fn;},send({image}){bodyImage=image;return new Promise(resolve=>{bodyDone=()=>{emit(bodyResult);resolve();};});},
    reset(){bodyReset++;},close(){}};
  const manual={detect(frame,timestamp,epoch){manualImage=frame.image;return new Promise((resolve,reject)=>{manualDone=()=>fail?reject(new Error('manual failed')):
    resolve({...manualResult,timestamp:mismatch?timestamp+1:timestamp,epoch});});},reset(){manualReset++;},close(){}};
  const pairs=[],outputs=[];
  const tracker=await createDualTracker({bodyFactory:async()=>body,manualFactory:async()=>manual,
    freeze:async()=>({image:{frozen:true},width:640,height:480,pixelDigest:'same',dispose(){dispose++;}}),onPair:p=>pairs.push(p)});
  tracker.onResults(result=>outputs.push(result));await tracker.reset();
  return {tracker,pairs,outputs,bodyResult,bodyDone:()=>bodyDone(),manualDone:()=>manualDone(),dispose:()=>dispose,
    images:()=>[bodyImage,manualImage],resets:()=>[bodyReset,manualReset]};
}
test('paired detectors share the immutable source but never share hand outputs',async()=>{
  const s=await setup(),send=s.tracker.send({image:{},timestamp:10});await flush();
  assert.equal(s.images()[0],s.images()[1]);s.bodyDone();await flush();assert.equal(s.outputs.length,0);assert.equal(s.dispose(),0);
  s.manualDone();await send;assert.equal(s.outputs[0],s.bodyResult);assert.notEqual(s.pairs[0].manual.landmarks,s.bodyResult.leftHandLandmarks);
  assert.equal(s.dispose(),1);assert.deepEqual(s.resets(),[1,1]);
});
test('a manual failure cannot substitute body hands and cannot release an active bitmap',async()=>{
  const s=await setup({fail:true}),send=s.tracker.send({image:{},timestamp:10});await flush();
  s.manualDone();await flush();assert.equal(s.dispose(),0);s.bodyDone();await assert.rejects(send,/manual failed/);
  assert.equal(s.outputs.length,0);assert.equal(s.dispose(),1);
});
test('cross-stream timestamp mismatch rejects the whole frame',async()=>{
  const s=await setup({mismatch:true}),send=s.tracker.send({image:{},timestamp:10});await flush();
  s.manualDone();s.bodyDone();await assert.rejects(send,/timestamp/);assert.equal(s.outputs.length,0);
});
test('reset and a second send cannot race a pending pair',async()=>{
  const s=await setup(),send=s.tracker.send({image:{},timestamp:10});await flush();
  await assert.rejects(s.tracker.reset(),/active/);await assert.rejects(s.tracker.send({image:{},timestamp:11}),/concurrent/);
  s.bodyDone();s.manualDone();await send;await assert.rejects(s.tracker.send({image:{},timestamp:10}),/timestamp/);
});
test('closing rejects a late result without attributing it to another take',async()=>{
  const s=await setup(),send=s.tracker.send({image:{},timestamp:10});await flush();s.tracker.close();
  s.bodyDone();s.manualDone();await assert.rejects(send,/closed/);assert.equal(s.outputs.length,0);assert.equal(s.dispose(),1);
});
test('manual detector options preserve the original VIDEO-mode capture contract',()=>{
  assert.deepEqual(MANUAL_OPTIONS,{runningMode:'VIDEO',numHands:2,minHandDetectionConfidence:.5,minHandPresenceConfidence:.5,minTrackingConfidence:.5});
  const source=readFileSync(new URL('../hand-detection-worker.js',import.meta.url),'utf8');
  for(const [key,value] of Object.entries(MANUAL_OPTIONS))assert.ok(source.includes(`${key}:${typeof value==='string'?`'${value}'`:value===.5?'.5':value}`));
  assert.equal(pixelDigest(new Uint8Array([1,2,3])),pixelDigest(new Uint8Array([1,2,3])));
  for(const file of ['app.js','index.html','landmark-capture.js'])assert.doesNotMatch(readFileSync(new URL('../'+file,import.meta.url),'utf8'),/dual_capture|dual_hand_worker/);
});
