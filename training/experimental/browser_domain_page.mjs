import {prepareTrackerFactory} from './prepared_tracker_factory.mjs';
import {createLandmarkCapture,createHolisticBodyTracker} from '../../landmark-capture.js';
import {createDualTracker} from './dual_capture.mjs';
import {captureContract} from './domain_capture_contract.mjs';
const cfg=window.DOMAIN_CAPTURE_FIXTURE,$=id=>document.getElementById(id);
if(location.hostname!=='127.0.0.1'||!cfg)throw new Error('Development capture is loopback-only');
let hardware=0,microphone=0;
if(navigator.mediaDevices)Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:async constraints=>{
  hardware++;if(constraints?.audio)microphone++;throw new Error('Physical camera/microphone prohibited');
}});
const source=$('source'),video=$('virtualCamera'),canvas=$('virtualCanvas'),ctx=canvas.getContext('2d',{alpha:false});
let armed=null,active=null,finishing=false,pairs=[],start=Infinity,deadline=-Infinity,running=false,stream=null,animation,blank=true,completed=0;
let stopBatch=false;
// Graph infrastructure is initialized before ANY video images are loaded.
const factory=await prepareTrackerFactory(()=>createDualTracker({bodyFactory:()=>createHolisticBodyTracker(),onPair:p=>{if(active)pairs.push(p);}}));
const capture=createLandmarkCapture({createTracker:()=>factory.acquire()}),owner=Symbol('train-val-development');
function paint(){
  ctx.fillStyle='#101010';ctx.fillRect(0,0,960,720);
  if(!blank&&source.readyState>=2){const scale=Math.min(960/source.videoWidth,720/source.videoHeight);
    const w=source.videoWidth*scale,h=source.videoHeight*scale;ctx.drawImage(source,(960-w)/2,(720-h)/2,w,h);}
}
const timer=setInterval(paint,1000/30);source.onended=()=>{blank=true;paint();};paint();
function tick(){if(running){capture.frame(owner,performance.now(),video);animation=requestAnimationFrame(tick);}}
function release(){running=false;cancelAnimationFrame(animation);source.pause();blank=true;paint();
  stream?.getTracks().forEach(t=>t.stop());stream=null;video.srcObject=null;pairs=[];}
async function finish(status,error=null,frames=[],info={}){
  if(!active||finishing)return;finishing=true;
  const take=active,contract=captureContract(pairs,frames,info,start,deadline);
  const outcome={number:completed+1,id:take.id,sourceSha256:take.videoSha256,
    startedAt:take.startedAt,finishedAt:new Date().toISOString(),status,error,
    rate:1,durationMs:take.durationMs,sourceDuration:take.sourceDuration,
    playbackTruncated:take.sourceDuration>take.durationMs/1000,
    start:Number.isFinite(start)?start:null,deadline:Number.isFinite(deadline)?deadline:null,
    sampledFrames:info.sampledFrames??0,processedFrames:info.processedFrames??0,
    warmupFrames:info.warmupFrames??0,poseWarmupFrames:info.poseWarmupFrames??0,
    trackerExecutionContext:info.trackerExecutionContext??null,
    tracker:info.tracker??null,bodyTracker:factory.current.bodyKind,
    realCameraCalls:hardware,microphoneCalls:microphone,
    checks:contract.checks,contractPassed:status==='complete'&&contract.passed,
    samples:contract.samples};
  document.body.dataset.captureOutcome=JSON.stringify({id:take.id,status,error,checks:contract.checks,sampleCount:contract.samples.length});
  release();
  const response=await fetch('/__domain__/feature',{method:'POST',headers:{'Content-Type':'application/json','X-Domain-Capture':cfg.token},body:JSON.stringify(outcome)});
  if(!response.ok)throw new Error('Immutable feature save failed: '+await response.text());
  const receipt=await response.json();
  if(receipt.saved!==outcome.number||receipt.id!==take.id)throw new Error('Wrong durable receipt');
  completed=receipt.saved;active=null;finishing=false;
  delete document.body.dataset.activeCapture;
  $('saved').textContent=`Durably saved ${completed}/${cfg.items.length}`;
  $('summary').textContent=`${completed} measured TRAIN/VAL captures; no recognition predictions or hardware calls.`;
  $('status').textContent=outcome.contractPassed?`Saved ${take.id}: ${outcome.samples.length} paired frames`:`Saved ${take.id}: ${status}, contract failed; excluded from fitting`;
}
function finishSafely(...args){void finish(...args).catch(error=>{$('batchStatus').textContent='Needs attention: '+error.message;});}
async function arm(id){
  if(active)throw new Error('Capture active');armed=cfg.items.find(r=>r.id===id);
  if(!armed)throw new Error('Unknown source');source.pause();blank=true;source.src=armed.video;
  await new Promise((resolve,reject)=>{source.onloadeddata=resolve;source.onerror=()=>reject(new Error('Original video unavailable'));source.load();});
  source.currentTime=0;blank=false;paint();
}
async function record(){
  pairs=[];start=Infinity;deadline=-Infinity;finishing=false;
  const durationMs=source.duration<=3.8?4000:source.duration<=5.8?6000:8000;
  active={...armed,startedAt:new Date().toISOString(),sourceDuration:source.duration,durationMs};
  document.body.dataset.activeCapture=armed.id;
  stream=canvas.captureStream(30);video.srcObject=stream;await video.play();running=true;tick();
  await capture.begin({owner,isRunning:()=>running,durationMs,onPhase:phase=>{
    $('status').textContent=phase;
    if(phase==='recording'){start=performance.now();deadline=start+durationMs;source.currentTime=0;source.playbackRate=1;blank=false;
      void source.play().catch(e=>{capture.cancel(owner);});}
  },onComplete:(frames,info)=>finishSafely('complete',null,frames,info),
    onError:error=>finishSafely('failed',error.message),onCancel:()=>finishSafely('canceled')});
}
$('batch').onclick=async()=>{
  $('batch').disabled=true;stopBatch=false;
  try{
    if(completed||active)throw new Error('One-pass capture already started; no source reruns');
    for(const item of cfg.items){
      if(stopBatch)break;
      try{await arm(item.id);await record();}catch(error){
        if(!active)active={...item,startedAt:new Date().toISOString(),sourceDuration:null,durationMs:4000};
        await finish('failed',error.message);
      }
      await new Promise((resolve,reject)=>{const end=Date.now()+90000;const poll=()=>{
        if($('batchStatus').textContent.startsWith('Needs attention:'))return reject(new Error($('batchStatus').textContent));
        if(!active&&!finishing)return resolve();
        if(Date.now()>end)return reject(new Error('Capture/save timeout; partial evidence retained'));setTimeout(poll,100);};poll();});
    }
    $('batchStatus').textContent=`Batch finished: ${completed} outcomes, all retained.`;
  }catch(error){$('batchStatus').textContent='Needs attention: '+error.message;}
};
$('stop').onclick=()=>{stopBatch=true;if(active&&!finishing)capture.cancel(owner);};
window.addEventListener('pagehide',()=>{clearInterval(timer);capture.close();release();});
$('status').textContent='Ready: graphs initialized without images; no prediction endpoints.';
document.body.dataset.auditReady='true';
