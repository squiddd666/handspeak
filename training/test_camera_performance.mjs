import test from 'node:test';
import assert from 'node:assert/strict';
import {preferredVisionDelegate} from '../camera-performance.js';
function probe(renderer){
 let released=false;
 const gl={RENDERER:1,getParameter:()=>renderer,getExtension:name=>name==='WEBGL_debug_renderer_info'?{UNMASKED_RENDERER_WEBGL:2}:{loseContext(){released=true;}}};
 return {factory:()=>({getContext:()=>gl}),released:()=>released};
}
test('software renderers choose CPU and release the probe',()=>{
 for(const name of ['ANGLE SwiftShader','Mesa llvmpipe','softpipe','Software Rasterizer']){
  const p=probe(name);assert.equal(preferredVisionDelegate(p.factory),'CPU');assert.ok(p.released());
 }
});
test('hardware renderer keeps GPU',()=>{
 const p=probe('ANGLE NVIDIA RTX');assert.equal(preferredVisionDelegate(p.factory),'GPU');assert.ok(p.released());
});
test('missing WebGL and blocked canvas use CPU',()=>{
 assert.equal(preferredVisionDelegate(()=>({getContext:()=>null})),'CPU');
 assert.equal(preferredVisionDelegate(()=>{throw Error('blocked');}),'CPU');
});
