import test from 'node:test';
import assert from 'node:assert/strict';
import {createHandRecovery} from '../body-hand-recovery.js';

async function make(renderer, failDelegate) {
  const options=[];let lost=0;
  const createCanvas=()=>({getContext(kind){
    if(kind==='2d')return {drawImage(){}};
    return {RENDERER:1,getParameter:()=>renderer,getExtension:name=>name==='WEBGL_debug_renderer_info'
      ?{UNMASKED_RENDERER_WEBGL:2}:name==='WEBGL_lose_context'?{loseContext(){lost++;}}:null};
  }});
  const model=await createHandRecovery({createCanvas,files:{},vision:{HandLandmarker:{async createFromOptions(files,config){
    options.push(config);
    if(config.baseOptions.delegate===failDelegate)throw new Error('delegate unavailable');
    return {detect:()=>({landmarks:[]}),close(){}};
  }}}});
  model.close();return {options,lost};
}
test('software rendering selects CPU without changing model or confidence gates',async()=>{
  const {options,lost}=await make('ANGLE SwiftShader');assert.equal(options.length,1);
  assert.equal(options[0].baseOptions.delegate,'CPU');assert.equal(lost,1);
  assert.equal(options[0].runningMode,'IMAGE');assert.equal(options[0].numHands,2);
  assert.equal(options[0].minHandDetectionConfidence,.35);assert.equal(options[0].minHandPresenceConfidence,.35);
  assert.match(options[0].baseOptions.modelAssetPath,/float16\/1\/hand_landmarker.task$/);
});
test('real GPU stays preferred and a GPU initialization failure falls back to CPU',async()=>{
  assert.equal((await make('NVIDIA GeForce')).options[0].baseOptions.delegate,'GPU');
  assert.deepEqual((await make('NVIDIA GeForce','GPU')).options.map(o=>o.baseOptions.delegate),['GPU','CPU']);
});
test('CPU initialization failure does not silently retry on software GPU',async()=>{
  await assert.rejects(make('SwiftShader','CPU'),/delegate unavailable/);
});
