// Development-only landmark serialization. No image, label or prediction enters
// a detector. The two detector outputs remain independent measured streams.
import {motionFrame} from '../../motion-model.js';
const POSE_IDS=[0,2,5,11,12,13,14];
function points(value,count){
  if(!Array.isArray(value)||value.length!==count)return null;
  const out=value.map(p=>[p.x,p.y,p.z??0]);
  return out.every(p=>p.every(Number.isFinite))?out:null;
}
export function serializePair(pair){
  const pose=points(pair.body.poseLandmarks,33);
  const manual=motionFrame(pair.manual).map(hand=>hand?.map(p=>({x:p.x,y:p.y,z:p.z}))??null);
  return {epoch:pair.epoch,timestamp:pair.timestamp,width:pair.width,height:pair.height,
    pixelEquality:pair.pixelEquality,
    body:{pose:pose?POSE_IDS.map(i=>pose[i]):null,left:points(pair.body.leftHandLandmarks,21),right:points(pair.body.rightHandLandmarks,21)},
    usedHandFallback:Boolean(pair.body.usedHandFallback),manual};
}
export function captureContract(pairs,frames,info,start,deadline){
  const samples=pairs.filter(p=>p.timestamp>=start&&p.timestamp<=deadline).map(serializePair);
  const body=samples.map(p=>p.body).filter(p=>p.pose&&(p.left||p.right));
  const first=samples[0];
  const checks={bodyOutputPreserved:JSON.stringify(body)===JSON.stringify(frames),
    sameEpoch:!!first&&samples.every(s=>s.epoch===first.epoch),
    monotonicTimestamps:samples.every((s,i)=>!i||s.timestamp>samples[i-1].timestamp),
    sameDimensions:!!first&&samples.every(s=>s.width===first.width&&s.height===first.height),
    pixelEquality:!!first&&samples.every(s=>s.pixelEquality===true),
    pairedProcessing:samples.length===(info.processedFrames??0),
    productionSampling:samples.length>0&&samples.length<=80&&samples.length===(info.sampledFrames??0),
    recordingGeometry:!!first&&first.width===640&&first.height===480,
    workerExecution:info.trackerExecutionContext==='worker'};
  return {samples,checks,passed:Object.values(checks).every(Boolean)};
}
