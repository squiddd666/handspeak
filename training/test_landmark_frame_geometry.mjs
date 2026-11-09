import test from 'node:test';
import assert from 'node:assert/strict';
import {uniformPaddingRect,restoreTrackingCoordinates,trackingSnapshot} from '../landmark-frame-geometry.js';

function pixels({width=64,height=48,left=0,right=0,top=0,bottom=0,blank=false}={}){
  const data=new Uint8ClampedArray(width*height*4);
  for(let y=0;y<height;y++)for(let x=0;x<width;x++){
    const pad=blank||x<left||x>=width-right||y<top||y>=height-bottom;
    data.set(pad?[16,16,16,255]:[50+x,90+y,190,255],(y*width+x)*4);
  }
  return {width,height,data};
}
test('exact symmetric pillarboxing retains a conservative border',()=>{
  assert.deepEqual(uniformPaddingRect(pixels({left:14,right:14})),{x:13/64,y:0,width:38/64,height:1});
});
test('exact symmetric letterboxing preserves the full source width',()=>{
  assert.deepEqual(uniformPaddingRect(pixels({top:5,bottom:5})),{x:0,y:4/48,width:1,height:40/48});
});
test('blank, unpadded, asymmetric, tiny, and excessive borders are not cropped',()=>{
  for(const options of [{blank:true},{},{left:14,right:8},{left:1,right:1},{left:20,right:20}]){
    assert.equal(uniformPaddingRect(pixels(options)),null);
  }
});
test('texture/noise in a border is not treated as exact video padding',()=>{
  const p=pixels({left:14,right:14});
  for(let x=0;x<14;x++)p.data[(11*64+x)*4]++;
  assert.equal(uniformPaddingRect(p),null);
});
test('coordinate restoration preserves image-width physical units and handedness',()=>{
  const input={poseLandmarks:[{x:.5,y:.25,z:-.2,visibility:.9}],
    leftHandLandmarks:[{x:.1,y:.3,z:.02}],rightHandLandmarks:null,usedHandFallback:true};
  const crop={x:200,y:0,width:560,height:720};
  const result=restoreTrackingCoordinates(input,crop,960,720);
  assert.equal(result.poseLandmarks[0].x,.5);
  assert.equal(result.poseLandmarks[0].y,.25);
  assert.equal(result.poseLandmarks[0].visibility,.9);
  assert.equal(result.poseLandmarks[0].z,-.2*560/960);
  assert.equal(result.leftHandLandmarks[0].x,256/960);
  assert.equal(result.leftHandLandmarks[0].z,.02*560/960);
  assert.equal(result.rightHandLandmarks,null);
  assert.equal(result.usedHandFallback,true);
  assert.equal(input.leftHandLandmarks[0].x,.1);
});
test('an uncropped frame retains its exact original landmark objects',()=>{
  const input={leftHandLandmarks:[]};assert.equal(restoreTrackingCoordinates(input,null,640,480),input);
});

function canvases(p, {readError=false, noPixels=false, noSnapshot=false, drawError=false}={}) {
  const created=[],draws=[];
  const make=()=>{
    const index=created.length;
    const canvas={width:0,height:0,getContext(){
      if(index===0&&noPixels || index===1&&noSnapshot)return null;
      return {drawImage(...args){if(index===1&&drawError)throw Error('draw failed');draws.push({index,args});},
        getImageData(){if(readError)throw Error('pixel read unavailable');return p;}};
    }};
    created.push(canvas);return canvas;
  };
  return {make,created,draws};
}
test('cropped snapshot retains physical source coordinates and releases both canvases',()=>{
  const c=canvases(pixels({left:14,right:14}));
  const video={videoWidth:960,videoHeight:720};
  const snap=trackingSnapshot(video,c.make);
  assert.equal(snap.cropped,true);assert.deepEqual(snap.sourceDimensions,[960,720]);
  assert.deepEqual(snap.dimensions,[507,640]);
  assert.deepEqual(c.draws.at(-1).args.slice(1,5),[195,0,570,720]);
  const result=snap.restore({leftHandLandmarks:[{x:.5,y:.5,z:.1}]});
  assert.equal(result.leftHandLandmarks[0].x,.5);
  assert.equal(result.leftHandLandmarks[0].y,.5);
  assert.equal(result.leftHandLandmarks[0].z,.1*570/960);
  assert.equal(c.created[0].width,0);assert.equal(c.created[0].height,0);
  snap.dispose();assert.equal(c.created[1].width,0);assert.equal(c.created[1].height,0);
});
test('no padding or unavailable pixel inspection uses full-frame tracking unchanged',()=>{
  for(const options of [{},{readError:true},{noPixels:true}]){
    const c=canvases(pixels(),options),snap=trackingSnapshot({videoWidth:960,videoHeight:720},c.make);
    assert.equal(snap.cropped,false);assert.deepEqual(snap.dimensions,[640,480]);
    assert.deepEqual(c.draws.at(-1).args.slice(1,5),[0,0,960,720]);
    const input={poseLandmarks:[]};assert.equal(snap.restore(input),input);
    snap.dispose();assert.equal(c.created[0].width,0);assert.equal(c.created[1].width,0);
  }
});
test('failed buffering releases allocated images and missing dimensions fail early',()=>{
  for(const options of [{noSnapshot:true},{drawError:true}]){
    const c=canvases(pixels(),options);
    assert.throws(()=>trackingSnapshot({videoWidth:960,videoHeight:720},c.make));
    assert.ok(c.created.every(canvas=>canvas.width===0&&canvas.height===0));
  }
  const c=canvases(pixels());assert.throws(()=>trackingSnapshot({videoWidth:0,videoHeight:720},c.make),/dimensions/);
  assert.equal(c.created.length,0);
});
