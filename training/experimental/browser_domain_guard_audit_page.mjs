import {predictBrowserDomainRecovery} from './browser_domain_recovery.mjs';
function applyManualOpenSetGuard(model,sequence,baseline){
  const out=predictBrowserDomainRecovery(model,sequence,baseline);
  return {predictions:out.predictions,diagnostics:Object.fromEntries(Object.entries(out.reasons).map(([mode,reason])=>[mode,{reason}]))};
}
import {prepareTrackerFactory} from './prepared_tracker_factory.mjs';
import {createLandmarkCapture,createHolisticBodyTracker} from '../../landmark-capture.js?v=20261108-capture-11';
import {createDualTracker} from './dual_capture.mjs';
import {predictBodyManual} from './body_manual_runtime.mjs';
import {motionFrame,encodeMotion} from '../../motion-model.js';
import {recognizeExpandedMotion} from '../../expanded-motion.js';
import {recognizeBinaryTemporal} from '../../hello-binary.js';
import {isUsableHand} from '../../gesture-model.js';
import {predictManualRoutes} from './online_manual_runtime.mjs';

const cfg=window.DUAL_CAPTURE_FIXTURE,$=id=>document.getElementById(id);
if(location.hostname!=='127.0.0.1'||!cfg)throw new Error('Dual fixture is loopback-only');
const report={schema:5,startedAt:new Date().toISOString(),fixtureSha256:cfg.fixtureSha256,
  scope:'Frozen unused-recording known-signer audit; no fitting or calibration. Same measured capture for baseline and candidate. Not unseen-signer, full-app or live-camera accuracy.',
  realCameraCalls:0,microphoneCalls:0,attempts:[]};
if(navigator.mediaDevices)Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:async constraints=>{report.realCameraCalls++;if(constraints?.audio)report.microphoneCalls++;throw new Error('Physical camera/microphone prohibited');}});
const source=$('source'),video=$('virtualCamera'),canvas=$('virtualCanvas'),ctx=canvas.getContext('2d',{alpha:false});
let armed=null,active=null,pairs=[],start=Infinity,deadline=-Infinity,running=false,stream=null,animation,blank=true,serial=0,stopBatch=false;
const poseIds=[0,2,5,11,12,13,14];
const points=(value,count)=>Array.isArray(value)&&value.length===count&&value.every(p=>[p.x,p.y,p.z??0].every(Number.isFinite))
  ?value.map(p=>[p.x,p.y,p.z??0]):null;
function bodyFrame(result){const pose=points(result.poseLandmarks,33),left=points(result.leftHandLandmarks,21),right=points(result.rightHandLandmarks,21);
  return pose&&(left||right)?{pose:poseIds.map(i=>pose[i]),left,right}:null;}
function manualFrame(result){return motionFrame({...result,landmarks:(result.landmarks||[]).map(h=>isUsableHand(h)?h:[])});}
// Infrastructure initialization receives no images or evaluation labels.
const trackerFactory=await prepareTrackerFactory(()=>createDualTracker({bodyFactory:()=>createHolisticBodyTracker(),onPair:pair=>{if(active)pairs.push(pair);}}));
const capture=createLandmarkCapture({createTracker:()=>trackerFactory.acquire()});
const owner=Symbol('isolated-dual-capture');
const load=async path=>{const response=await fetch(path);if(!response.ok)throw new Error('Frozen model unavailable');return response.json();};
const productionModes=['beginner','capstone-core','capstone-extended','capstone-full'];
const unusableProduction=()=>({accepted:null,rejectionReason:'capture-unusable',error:null,httpStatus:null,checkpointSha256:null,auxiliarySha256:null});
async function productionPredict(mode,frames,id){
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),20000);
  const payload=mode==='beginner'?{consent:true,frames}:{consent:true,frames,vocabulary:mode.split('-')[1]};
  // No expected word, practice label, score hint, or route oracle reaches APIs.
  try{
    const r=await fetch(mode==='beginner'?'/api/beginner-asl':'/api/capstone-asl',{method:'POST',
      headers:{'Content-Type':'application/json','X-Motion-Audit':cfg.token,'X-Audit-Clip':id,'X-Audit-Mode':mode},
      body:JSON.stringify(payload),signal:controller.signal});
    const data=await r.json();return {accepted:r.ok?data.predictions?.[0]?.label??null:null,
      rejectionReason:data.rejectionReason??null,error:data.error??null,httpStatus:r.status,
      checkpointSha256:data.checkpointSha256??null,auxiliarySha256:data.auxiliarySha256??null};
  }catch(e){return {accepted:null,rejectionReason:null,error:e.name==='AbortError'?'Production request timed out':String(e.message),httpStatus:null,checkpointSha256:null,auxiliarySha256:null};}
  finally{clearTimeout(timeout);}
}
const guardModel=await load(cfg.guardModel);
const models=await Promise.all([cfg.candidate,'models/asl-words.json','models/asl-extra-words.json','models/hello-binary.json','models/baby-binary.json','models/water-binary.json','models/research-words.json','models/motion-categories/pack-dtw.json'].map(load));
const manualModels={base:models[1],extra:models[2],hello:models[3],baby:models[4],water:models[5],daily:models[6],pack:models[7]};
function paint(){
  ctx.fillStyle='#101010';ctx.fillRect(0,0,canvas.width,canvas.height);
  if(!blank&&source.readyState>=2){const scale=Math.min(canvas.width/source.videoWidth,canvas.height/source.videoHeight);
    const w=source.videoWidth*scale,h=source.videoHeight*scale;ctx.drawImage(source,(canvas.width-w)/2,(canvas.height-h)/2,w,h);}
}
const paintTimer=setInterval(paint,1000/30);source.onended=()=>{blank=true;paint();};paint();
function tick(){if(running){capture.frame(owner,performance.now(),video);animation=requestAnimationFrame(tick);}}
function display(){
  $('ledger').textContent=JSON.stringify(report,null,2);
  const complete=report.attempts.filter(a=>a.status==='complete');
  $('summary').textContent=`${report.attempts.length} outcomes saved in this tab Â· ${complete.filter(a=>a.contractPassed).length}/${complete.length} completed captures passed stream contracts Â· 0 physical camera calls`;
}
async function save(){
  display();const response=await fetch('/__worker_audit__/checkpoint',{method:'POST',headers:{'Content-Type':'application/json','X-Motion-Audit':cfg.token},body:JSON.stringify(report)});
  if(!response.ok)throw new Error('Scalar checkpoint failed: '+await response.text());
  $('saved').textContent=`Durably saved ${report.attempts.length} outcomes.`;
}
function release(){running=false;cancelAnimationFrame(animation);source.pause();blank=true;paint();pairs=[];active=null;
  stream?.getTracks().forEach(t=>t.stop());stream=null;video.srcObject=null;$('record').disabled=false;$('cancel').disabled=true;}
async function terminate(status,error=null,frames=[],info={}){
  if(!active)return;
  const take=active,recorded=pairs.filter(p=>p.timestamp>=start&&p.timestamp<=deadline);
  const derived=recorded.map(p=>bodyFrame(p.body)).filter(Boolean),manual=recorded.map(p=>manualFrame(p.manual));
  const scalarPairs=recorded.map(p=>({epoch:p.epoch,timestamp:p.timestamp,width:p.width,height:p.height,pixelEquality:p.pixelEquality,
    bodyHands:Number(Boolean(points(p.body.leftHandLandmarks,21)))+Number(Boolean(points(p.body.rightHandLandmarks,21))),
    manualHands:manualFrame(p.manual).filter(Boolean).length,bodyPose:Boolean(points(p.body.poseLandmarks,33))}));
  const timestamps=scalarPairs.map(p=>p.timestamp),bodyEquality=JSON.stringify(derived)===JSON.stringify(frames);
  const monotonic=timestamps.every((t,i)=>!i||t>timestamps[i-1]),sameEpoch=new Set(scalarPairs.map(p=>p.epoch)).size<=1;
  const sameDimensions=scalarPairs.every(p=>p.width===scalarPairs[0].width&&p.height===scalarPairs[0].height);
  take.status=status;take.error=error;take.finishedAt=new Date().toISOString();take.pairCount=recorded.length;
  take.bodyFrames=frames.length;take.bodyOutputPreserved=bodyEquality;take.manualFrames=manual.length;
  take.manualTrackedFrames=manual.filter(f=>f.some(Boolean)).length;
  take.manualEncodingUsable=recorded.length>0&&Boolean(encodeMotion(manual,recorded[0].height/recorded[0].width));
  take.sameEpoch=sameEpoch;take.monotonicTimestamps=monotonic;
  take.sameDimensions=sameDimensions;take.pixelEquality=scalarPairs.every(p=>p.pixelEquality);
  take.trackerExecutionContext=info.trackerExecutionContext??null;take.bodyTracker=trackerFactory.current.bodyKind??null;
  take.productionPredictions=Object.fromEntries(productionModes.map(mode=>[mode,unusableProduction()]));
  take.sampledFrames=info.sampledFrames??null;take.processedFrames=info.processedFrames??null;take.tracker=info.tracker??null;
  take.contractPassed=status==='complete'&&recorded.length>0&&bodyEquality&&monotonic&&sameEpoch&&sameDimensions&&take.pixelEquality&&recorded.length===info.processedFrames&&info.trackerExecutionContext==='worker';
  take.samples=scalarPairs;take.manualPredictions={default:null,expanded:null,daily:null,pack:null};
  take.manualGuardPredictions={default:null,expanded:null,daily:null,pack:null};
  take.manualGuardReasons={default:'capture-unusable',expanded:'capture-unusable',daily:'capture-unusable',pack:'capture-unusable'};
  take.experimentalBodyPrediction=null;take.candidateTracked=false;take.candidateDistance=null;take.candidateSeparation=null;take.candidateVotes=0;
  take.playbackTruncated=Number.isFinite(take.sourceDuration)&&take.sourceDuration>take.durationMs/1000;
  if(status==='complete'&&take.contractPassed){
    const aspect=recorded[0].height/recorded[0].width;
    try {const candidate=predictBodyManual(models[0],{frames,imageAspect:aspect});
    take.experimentalBodyPrediction=candidate.prediction;take.candidateTracked=candidate.tracked;
    take.candidateDistance=Number.isFinite(candidate.distance)?candidate.distance:null;
    take.candidateSeparation=Number.isFinite(candidate.separation)?candidate.separation:null;take.candidateVotes=candidate.votes;
    take.manualPredictions=predictManualRoutes(manualModels,manual,aspect);
    const guarded=applyManualOpenSetGuard(guardModel,encodeMotion(manual,aspect),take.manualPredictions);
    take.manualGuardPredictions=guarded.predictions;take.manualGuardReasons=Object.fromEntries(Object.entries(guarded.diagnostics).map(([m,d])=>[m,d.reason]));
    }catch(error){take.status='failed';take.error='Classifier execution failed: '+error.message;take.contractPassed=false;take.experimentalBodyPrediction=null;take.manualPredictions={default:null,expanded:null,daily:null,pack:null};take.manualGuardPredictions={default:null,expanded:null,daily:null,pack:null};}
  }
  if(take.contractPassed&&frames.length>=5){
    for(const mode of productionModes)take.productionPredictions[mode]=await productionPredict(mode,frames,take.id);
  }
  report.attempts.push(take);release();await save();
  $('status').textContent=status==='complete'?`Completed ${take.label}: ${take.contractPassed?'stream contracts passed':'CONTRACT FAILURE'} Â· body candidate ${take.experimentalBodyPrediction||'no match'} Â· manual ${JSON.stringify(take.manualPredictions)}. No word was added.`:
    `${status}: ${error||'Canceled through the public fixture control'}. Outcome preserved.`;
}
async function arm(){
  if(active)throw new Error('A capture is already active');
  armed=cfg.items.find(i=>i.id===$('reference').value);source.pause();source.src=armed.video;blank=true;
  await new Promise((resolve,reject)=>{source.onloadeddata=resolve;source.onerror=()=>reject(new Error('Reference failed to load'));source.load();});
  source.currentTime=0;blank=false;paint();$('record').disabled=false;
  $('status').textContent=`Armed ${armed.label}: ${source.videoWidth}Ã—${source.videoHeight}, ${source.duration.toFixed(2)}s. No camera/microphone permission needed.`;
}
async function record(){
  if(!armed||active)return;
  $('record').disabled=true;$('cancel').disabled=false;pairs=[];start=Infinity;deadline=-Infinity;
  const durationMs=source.duration<=3.8?4000:source.duration<=5.8?6000:8000;
  active={number:++serial,id:armed.id,label:armed.label,clipSha256:armed.videoSha256,startedAt:new Date().toISOString(),durationMs,
    rate:1,sourceDuration:source.duration,manualMode:'all-four-frozen-modes'};
  stream=canvas.captureStream(30);video.srcObject=stream;await video.play();running=true;tick();
  await capture.begin({owner,isRunning:()=>running,durationMs,
    onPhase:phase=>{
      $('status').textContent=phase;
      if(phase==='recording'){start=performance.now();deadline=start+durationMs;source.currentTime=0;source.playbackRate=1;blank=false;void source.play().catch(e=>capture.cancel(owner));}
    },onComplete:(frames,info)=>void terminate('complete',null,frames,info).catch(error=>{$('status').textContent=error.message;}),
    onError:error=>void terminate('failed',error.message).catch(e=>{$('status').textContent=e.message;}),
    onCancel:()=>void terminate('canceled').catch(e=>{$('status').textContent=e.message;})});
}
for(const item of cfg.items){const option=document.createElement('option');option.value=item.id;option.textContent=item.label;$('reference').append(option);}
$('arm').onclick=()=>void arm().catch(e=>{$('status').textContent=e.message;});
$('record').onclick=()=>void record().catch(e=>void terminate('failed',e.message));
$('cancel').onclick=()=>capture.cancel(owner);
$('blank').onclick=()=>{source.pause();blank=true;paint();};
$('batch').onclick=async()=>{
  $('batch').disabled=true;stopBatch=false;
  try {
    if(report.attempts.length)throw new Error('One-pass audit already started; no reruns');
    const ids=cfg.items.map(item=>item.id);
    if(ids.some(id=>!cfg.items.some(i=>i.id===id)))throw new Error('Unknown reference ID');
    for(const id of ids){
      if(stopBatch)break;
      $('reference').value=id;
      try{await arm();await record();}catch(error){
        if(!active){armed=cfg.items.find(item=>item.id===id);active={number:++serial,id,label:armed.label,clipSha256:armed.videoSha256,startedAt:new Date().toISOString(),durationMs:4000,rate:1,sourceDuration:null,manualMode:'all-four-frozen-modes'};}
        await terminate('failed',error.message);
      }
      await new Promise((resolve,reject)=>{const end=performance.now()+70000;const poll=()=>{
        if(!active&&$('saved').textContent===`Durably saved ${report.attempts.length} outcomes.`)return resolve();
        if(performance.now()>end)return reject(new Error('Capture or checkpoint did not finish'));setTimeout(poll,100);};poll();});
    }
    $('batchStatus').textContent=`Batch finished: ${report.attempts.length} outcomes. All results retained; no best-of retries.`;
  }catch(error){$('batchStatus').textContent='Needs attention: '+error.message;}
  finally{$('batch').disabled=false;}
};
$('stop').onclick=()=>{stopBatch=true;if(active)capture.cancel(owner);};
window.addEventListener('pagehide',()=>{clearInterval(paintTimer);capture.close();release();});display();
$('status').textContent=`Ready. Infrastructure loaded without images. Run the frozen ${cfg.items.length}-clip, one-pass audit.`;document.body.dataset.auditReady='true';
