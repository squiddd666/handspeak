import {createHolisticWorkerTracker} from '../../holistic-worker-tracker.js';
import {createDualTracker} from './dual_capture.mjs';
import {motionFrame,encodeMotion} from '../../motion-model.js';
import {isUsableHand} from '../../gesture-model.js';
const cfg=window.CAPTURE_DEV;
window.devState={done:false,error:null,results:[],hardwareCalls:0};
if(navigator.mediaDevices)Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:async()=>{window.devState.hardwareCalls++;throw new Error('Hardware prohibited');}});
const video=document.getElementById('source'),canvas=document.getElementById('canvas'),ctx=canvas.getContext('2d');
const show=()=>document.getElementById('report').textContent=JSON.stringify(window.devState,null,2);
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function seek(time){
  if(Math.abs(video.currentTime-time)<.0001)return;
  await new Promise((resolve,reject)=>{video.onseeked=resolve;video.onerror=reject;video.currentTime=time;});
  if(Math.abs(video.currentTime-time)>.01)throw new Error('Development source seek did not reach the requested timestamp');
}
async function load(item){
  video.src=item.url;await new Promise((resolve,reject)=>{video.onloadeddata=resolve;video.onerror=reject;video.load();});
  if(!Number.isFinite(video.duration)||video.duration<=0)throw new Error('Invalid development source duration');
  const scale=Math.min(1,640/Math.max(video.videoWidth,video.videoHeight));
  canvas.width=Math.round(video.videoWidth*scale);canvas.height=Math.round(video.videoHeight*scale);
}
async function serialProbe(mode,item,count){
  await load(item);
  const module=await import(mode==='baseline'?'/baseline/landmark-capture.js':'/landmark-capture.js');
  const start=performance.now();
  const tracker=mode==='baseline'?await module.createHolisticBodyTracker():await createHolisticWorkerTracker();
  const initMs=performance.now()-start,samples=[];let body,beats=0,last=performance.now(),maxLagMs=0;
  const timer=setInterval(()=>{const now=performance.now();maxLagMs=Math.max(maxLagMs,now-last-10);last=now;beats++;},10);
  tracker.onResults(r=>body=r);
  try{
    await tracker.reset();
    for(let i=0;i<count;i++){
      await seek(video.duration*(i+.5)/count);ctx.drawImage(video,0,0,canvas.width,canvas.height);
      const at=performance.now();body=null;await tracker.send({image:canvas});
      if(!body)throw new Error('Missing body result');
      samples.push({index:i,sourceTime:video.currentTime,sendMs:performance.now()-at,
        pose:Boolean(body.poseLandmarks?.length===33),left:Boolean(body.leftHandLandmarks?.length===21),right:Boolean(body.rightHandLandmarks?.length===21),fallback:Boolean(body.usedHandFallback)});
      await wait(0);
    }
  }finally{clearInterval(timer);tracker.close();}
  return {type:'serial',mode,developmentId:item.id,initMs,samples,beats,maxLagMs,kind:tracker.kind};
}
async function captureProbe(c,item){
  await load(item);canvas.width=960;canvas.height=720;
  const virtual=document.createElement('video');virtual.muted=true;virtual.playsInline=true;document.body.append(virtual);
  const module=await import(c.mode==='baseline'?'/baseline/landmark-capture.js':'/landmark-capture.js');
  let pairs=[],phase='loading',recordStart=Infinity,recordEnd=-Infinity,recordTimes=[],frames=[],info={},error=null,status;
  const bodyFactory=c.mode==='baseline'||c.mode==='default'?()=>module.createHolisticBodyTracker():()=>createHolisticWorkerTracker();
  const tracker=await createDualTracker({bodyFactory,onPair:p=>pairs.push(p)});
  const capture=module.createLandmarkCapture({createTracker:async()=>tracker}),owner=Symbol('dev');
  let running=true,animation,blank=c.blank===true,last=performance.now(),beats=0,maxLagMs=0,recordingMaxLagMs=0;
  const beat=setInterval(()=>{const now=performance.now(),lag=now-last-10;maxLagMs=Math.max(maxLagMs,lag);if(phase==='recording')recordingMaxLagMs=Math.max(recordingMaxLagMs,lag);last=now;beats++;},10);
  function paint(){ctx.fillStyle='#101010';ctx.fillRect(0,0,960,720);
    if(!blank&&video.readyState>=2){const s=Math.min(960/video.videoWidth,720/video.videoHeight),w=video.videoWidth*s,h=video.videoHeight*s;ctx.drawImage(video,(960-w)/2,(720-h)/2,w,h);}}
  const paintTimer=setInterval(paint,1000/30);video.onended=()=>{blank=true;paint();};await seek(0);paint();
  const stream=canvas.captureStream(30);virtual.srcObject=stream;await virtual.play();
  function tick(){if(running){if(phase==='recording')recordTimes.push(video.currentTime);capture.frame(owner,performance.now(),virtual);animation=requestAnimationFrame(tick);}}tick();
  const durationMs=video.duration<=3.8?4000:video.duration<=5.8?6000:8000;
  let cancelTimer,watchdog;
  const finished=new Promise(resolve=>{
    const finish=(s,e,f=[],i={})=>{status=s;error=e;frames=f;info=i;resolve();};
    watchdog=setTimeout(()=>{capture.cancel(owner);finish('failed','Development watchdog');},70000);
    void capture.begin({owner,isRunning:()=>running,durationMs,
      onPhase:p=>{phase=p;if(p==='recording'){recordStart=performance.now();recordEnd=recordStart+durationMs;video.currentTime=0;
        if(!c.blank){blank=false;void video.play().catch(e=>finish('failed',e.message));}
        if(c.cancelAfterMs)cancelTimer=setTimeout(()=>capture.cancel(owner),c.cancelAfterMs);}},
      onComplete:(f,i)=>finish('complete',null,f,i),onError:e=>finish('failed',e.message),onCancel:()=>finish('canceled',null)}).catch(e=>finish('failed',e.message));
  });
  try{await finished;}
  finally{running=false;cancelAnimationFrame(animation);clearInterval(beat);clearInterval(paintTimer);clearTimeout(cancelTimer);clearTimeout(watchdog);capture.close();video.pause();video.onended=null;stream.getTracks().forEach(t=>t.stop());virtual.srcObject=null;virtual.remove();}
  pairs=pairs.filter(p=>p.timestamp>=recordStart&&p.timestamp<=recordEnd);
  const pts=(v,n)=>Array.isArray(v)&&v.length===n?v.map(p=>[p.x,p.y,p.z??0]):null;
  const body=pairs.map(p=>{const pose=pts(p.body.poseLandmarks,33),left=pts(p.body.leftHandLandmarks,21),right=pts(p.body.rightHandLandmarks,21);
    return pose&&(left||right)?{pose:[0,2,5,11,12,13,14].map(i=>pose[i]),left,right}:null;}).filter(Boolean);
  const manual=pairs.map(p=>motionFrame({...p.manual,landmarks:p.manual.landmarks.map(h=>isUsableHand(h)?h:[])}));
  const sameBody=JSON.stringify(body)===JSON.stringify(frames),times=pairs.map(p=>p.timestamp);
  const contractPassed=status==='complete'&&pairs.length>0&&pairs.length===info.processedFrames&&sameBody&&
    pairs.every(p=>p.pixelEquality&&p.epoch===pairs[0].epoch&&p.width===pairs[0].width&&p.height===pairs[0].height)&&times.every((t,i)=>!i||t>times[i-1]);
  return {type:'capture',mode:c.mode,developmentId:item.id,blank:Boolean(c.blank),cancelAfterMs:c.cancelAfterMs||null,status,error,durationMs,
    sampledFrames:info.sampledFrames??0,processedFrames:info.processedFrames??0,bodyFrames:frames.length,
    manualTrackedFrames:manual.filter(f=>f.some(Boolean)).length,manualEncodingUsable:status==='complete'&&Boolean(encodeMotion(manual,480/640)),
    bodyOutputPreserved:sameBody,pairCount:pairs.length,contractPassed,beats,maxLagMs,recordingMaxLagMs,
    sourcePlaybackAdvanced:recordTimes.some(t=>t>.1),pairedTimes:times,kind:tracker.kind,
    bodyKind:tracker.bodyKind,executionContext:tracker.executionContext};
}
window.runDev=async()=>{
  try{
    for(const c of cfg.cases){
      const item=cfg.items.find(i=>i.id===c.developmentId);
      const r=c.type==='capture'?await captureProbe(c,item):await serialProbe(c.mode,item,c.count);window.devState.results.push(r);show();
    }
  }catch(error){window.devState.error=String(error.stack||error);}
  finally{window.devState.done=true;show();}
};
window.devReady=true;show();
