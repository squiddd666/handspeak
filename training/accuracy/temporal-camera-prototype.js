// Isolated research camera harness; never loaded by the production application.
import {FilesetResolver,HandLandmarker,PoseLandmarker} from 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/+esm';
import {isUsableHand} from './gesture-model.js';
import {motionFrame,encodeMotion} from './motion-model.js';
import {createAutomaticMotion} from './automatic-motion.js';
import {bodyTipFeatures,residualMotionLogits} from './residual-runtime.js';
import {alignTemporalWindow} from './temporal-window-browser.js';
const canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d',{willReadFrequently:Boolean(window.imageDataInput)});
const video=document.querySelector('video');
window.ready=(async()=>{
  const model=await (await fetch('./model.json')).json();
  const files=await FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/wasm');
  const hands=await HandLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:'./hand.task',delegate:model.handDelegate||'CPU'},runningMode:'VIDEO',numHands:2,minHandDetectionConfidence:.65,minHandPresenceConfidence:.65,minTrackingConfidence:.6});
  const poseTask=model.featureMode==='hands-only'?null:await PoseLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:'./pose-full.task',delegate:'CPU'},runningMode:'VIDEO',numPoses:1,minPoseDetectionConfidence:.5,minPosePresenceConfidence:.5,minTrackingConfidence:.5,outputSegmentationMasks:false});
  let body=null;
  const pose={async send({image}){if(!poseTask){body=null;return;}const result=poseTask.detectForVideo(image,performance.now());body=result.landmarks?.[0]?[0,11,12,13,14].map(i=>({...result.landmarks[0][i]})):null;}};
  ctx.fillRect(0,0,canvas.width,canvas.height);await pose.send({image:canvas});
  function classify(row){
    if(row.sequence===null)return null;
    const input=bodyTipFeatures(alignTemporalWindow(row));
    const probabilities=Array(model.outputLabels.length).fill(0);
    for(const weights of model.weights){
      const logits=residualMotionLogits(input,weights),max=Math.max(...logits),exp=logits.map(x=>Math.exp(x-max)),sum=exp.reduce((a,b)=>a+b,0);
      exp.forEach((x,i)=>probabilities[i]+=x/sum/model.weights.length);
    }
    const order=probabilities.map((_,i)=>i).sort((a,b)=>probabilities[b]-probabilities[a]);
    const label=model.outputLabels[order[0]];
    return model.labels.includes(label)&&probabilities[order[0]]>=model.threshold&&probabilities[order[0]]-probabilities[order[1]]>=model.margin?label:null;
  }
  window.runRecordedClip=async(url)=>{
    if(poseTask)throw Error('Recorded diagnostic currently requires hands-only candidate');
    const mediaBlob=URL.createObjectURL(await (await fetch(url)).blob());
    video.src=mediaBlob;await new Promise((resolve,reject)=>{video.onloadedmetadata=resolve;video.onerror=reject;});
    if(video.readyState<2)await new Promise(resolve=>video.onloadeddata=resolve);
    const scale=Math.min(1,640/Math.max(video.videoWidth,video.videoHeight));
    canvas.width=Math.round(video.videoWidth*scale);canvas.height=Math.round(video.videoHeight*scale);
    const frames=[],timings=[],timestamps=[],rawCounts=[],start=performance.now();
    for(let i=0;i<60;i++){
      const target=i*Math.max(0,video.duration-.001)/59;
      if(Math.abs(video.currentTime-target)>.00001){await new Promise(resolve=>{video.onseeked=resolve;video.currentTime=target;});}
      await new Promise(requestAnimationFrame);
      ctx.drawImage(video,0,0,canvas.width,canvas.height);
      if(i===30)window.recordedMidFrame=canvas.toDataURL('image/png');
      const before=performance.now(),detection=hands.detectForVideo(ctx.getImageData(0,0,canvas.width,canvas.height),before);
      timings.push(performance.now()-before);
      rawCounts.push(detection.landmarks.length);
      const ids=detection.landmarks.map((h,j)=>isUsableHand(h)?j:-1).filter(j=>j>=0);
      frames.push(motionFrame({landmarks:ids.map(j=>detection.landmarks[j]),handedness:ids.map(j=>detection.handedness[j])}));
      timestamps.push(video.currentTime*1000);
    }
    const aspect=canvas.height/canvas.width,row={rawFrames:frames,body:frames.map(()=>null),timestamps,imageAspect:aspect,sequence:encodeMotion(frames,aspect)};
    return {label:classify(row),validSequence:row.sequence!==null,frames:frames.length,tracked:frames.filter(f=>f.some(Boolean)).length,rawCounts,videoSize:[video.videoWidth,video.videoHeight],canvasSize:[canvas.width,canvas.height],processingMs:performance.now()-start,detectorMedianMs:timings.sort((a,b)=>a-b)[30],sourceDurationMs:video.duration*1000};
  };
  window.runBufferedClip=async(url,mirror=false)=>{
    const worker=new Worker('./temporal-camera-worker.js');
    await new Promise((resolve,reject)=>{worker.onmessage=({data})=>data.type==='ready'?resolve():reject(Error(data.message));worker.onerror=reject;worker.postMessage({type:'init'});});
    const mediaBlob=URL.createObjectURL(await (await fetch(url)).blob());
    video.src=mediaBlob;await new Promise(resolve=>video.onloadedmetadata=resolve);
    if(video.readyState<2)await new Promise(resolve=>video.onloadeddata=resolve);
    const automatic=createAutomaticMotion({sampleIntervalMs:30}),queue=[],events=[],tracking=[],metadata=new WeakMap();
    let busy=false,lastVideo=-1,lastCapture=-Infinity,ended=null,frames=0,tracked=0,maxQueue=0,maxLatencyMs=0,error=null;
    const start=performance.now();
    function drain(){if(busy||!queue.length)return;busy=true;const packet=queue.shift();worker.postMessage(packet,[packet.pixels]);}
    worker.onmessage=({data})=>{
      if(data.type==='error'){error=Error(data.message);busy=false;return;}
      busy=false;frames++;if(data.frame.some(Boolean))tracked++;
      maxLatencyMs=Math.max(maxLatencyMs,performance.now()-data.timestamp);
      tracking.push({timeMs:data.timestamp-start,raw:data.raw,usable:data.frame.filter(Boolean).length,processingMs:data.processingMs});
      metadata.set(data.frame,{time:data.timestamp});
      const clip=automatic.push(data.frame,data.timestamp,canvas.height/canvas.width);
      if(clip){const row={rawFrames:clip.frames,body:clip.frames.map(()=>null),timestamps:clip.frames.map(f=>metadata.get(f).time),imageAspect:clip.imageAspect,sequence:encodeMotion(clip.frames,clip.imageAspect)};events.push({label:classify(row),timeMs:performance.now()-start,captureTimeMs:data.timestamp-start,frames:clip.frames.length,usable:row.sequence!==null});}
      drain();
    };
    await video.play();
    while(ended===null||performance.now()-ended<2600){
      await new Promise(requestAnimationFrame);const now=performance.now();
      if(error)throw error;
      if(video.ended&&ended===null)ended=now;
      if(now-lastCapture<window.captureInterval||(!video.ended&&video.currentTime===lastVideo))continue;
      lastCapture=now;lastVideo=video.currentTime;
      ctx.setTransform(1,0,0,1,0,0);ctx.fillStyle='black';ctx.fillRect(0,0,canvas.width,canvas.height);
      if(!video.ended){const scale=Math.min(canvas.width/video.videoWidth,canvas.height/video.videoHeight),w=video.videoWidth*scale,h=video.videoHeight*scale;if(mirror)ctx.setTransform(-1,0,0,1,canvas.width,0);ctx.drawImage(video,(canvas.width-w)/2,(canvas.height-h)/2,w,h);ctx.setTransform(1,0,0,1,0,0);}
      queue.push({type:'frame',pixels:ctx.getImageData(0,0,canvas.width,canvas.height).data.buffer,width:canvas.width,height:canvas.height,timestamp:now});maxQueue=Math.max(maxQueue,queue.length);
      if(queue.length>150)throw Error('Diagnostic frame queue overflow');drain();
    }
    while(busy||queue.length){if(error)throw error;await new Promise(resolve=>setTimeout(resolve,20));}
    worker.terminate();URL.revokeObjectURL(mediaBlob);
    return {events,frames,tracked,maxQueue,maxLatencyMs,wallPlaybackMs:ended-start,sourceDurationMs:video.duration*1000,tracking,mirror};
  };
  window.runClip=async(url,mirror=false)=>{
    if(window.bufferedInput)return window.runBufferedClip(url,mirror);

    const automatic=createAutomaticMotion({sampleIntervalMs:30}),metadata=new WeakMap(),events=[],timings=[],videoTimings=[],handTimings=[],poseTimings=[],tracking=[];
    const mediaBlob=URL.createObjectURL(await (await fetch(url)).blob());
    video.src=mediaBlob;await new Promise((resolve,reject)=>{video.onloadedmetadata=resolve;video.onerror=reject;});
    if(video.readyState<2)await new Promise(resolve=>video.onloadeddata=resolve);
    if(window.nativeAspect){
      const scale=Math.min(1,640/Math.max(video.videoWidth,video.videoHeight));
      canvas.width=Math.round(video.videoWidth*scale);canvas.height=Math.round(video.videoHeight*scale);
    }
    const warmStart=performance.now();
    for(let i=0;i<3;i++){
      ctx.fillStyle='black';ctx.fillRect(0,0,canvas.width,canvas.height);
      const scale=Math.min(canvas.width/video.videoWidth,canvas.height/video.videoHeight);
      const w=video.videoWidth*scale,h=video.videoHeight*scale;
      ctx.drawImage(video,(canvas.width-w)/2,(canvas.height-h)/2,w,h);
      hands.detectForVideo(canvas,performance.now());await pose.send({image:canvas});
    }
    const warmupMs=performance.now()-warmStart;
    const start=performance.now();let ended=null,frames=0,tracked=0;
    await video.play();
    while(ended===null||performance.now()-ended<2600){
      await new Promise(requestAnimationFrame);
      const now=performance.now();
      const mediaTime=video.currentTime,sourceFrame=!video.ended;
      if(video.ended&&ended===null)ended=now;
      ctx.setTransform(1,0,0,1,0,0);ctx.fillStyle='black';ctx.fillRect(0,0,canvas.width,canvas.height);
      if(!video.ended){
        const scale=Math.min(canvas.width/video.videoWidth,canvas.height/video.videoHeight);
        const w=video.videoWidth*scale,h=video.videoHeight*scale;
        if(mirror)ctx.setTransform(-1,0,0,1,canvas.width,0);
        ctx.drawImage(video,(canvas.width-w)/2,(canvas.height-h)/2,w,h);ctx.setTransform(1,0,0,1,0,0);
      }
      // Match production's direct video input when no canvas transformation or
      // second detector is needed; blank tails still use the canvas.
      const detectionInput=window.imageDataInput?ctx.getImageData(0,0,canvas.width,canvas.height):canvas;
      const handStart=performance.now(),detection=hands.detectForVideo(detectionInput,now);
      handTimings.push(performance.now()-handStart);
      const poseStart=performance.now();
      await pose.send({image:canvas});
      poseTimings.push(performance.now()-poseStart);
      const indices=detection.landmarks.map((h,i)=>isUsableHand(h)?i:-1).filter(i=>i>=0);
      const frame=motionFrame({landmarks:indices.map(i=>detection.landmarks[i]),handedness:indices.map(i=>detection.handedness[i])});
      tracking.push({timeMs:now-start,mediaTime,sourceFrame,raw:detection.landmarks.length,usable:indices.length});
      metadata.set(frame,{body,time:now});frames++;if(frame.some(Boolean))tracked++;
      const clip=automatic.push(frame,now,canvas.height/canvas.width);
      if(clip){
        const row={rawFrames:clip.frames,body:clip.frames.map(f=>metadata.get(f).body),timestamps:clip.frames.map(f=>metadata.get(f).time),imageAspect:clip.imageAspect,sequence:encodeMotion(clip.frames,clip.imageAspect)};
        const label=classify(row);
        events.push({label,timeMs:performance.now()-start,frames:clip.frames.length,usable:row.sequence!==null});
      }
      timings.push(performance.now()-now);
      if(sourceFrame)videoTimings.push(performance.now()-now);
      if(performance.now()-start>90000)throw Error('Playback timeout');
    }
    return {events,frames,tracked,warmupMs,warmupFrames:3,wallPlaybackMs:ended-start,sourceDurationMs:video.duration*1000,processingMedianMs:timings.sort((a,b)=>a-b)[Math.floor(timings.length/2)],processingP95Ms:timings[Math.floor(timings.length*.95)],sourceFrameMedianMs:videoTimings.sort((a,b)=>a-b)[Math.floor(videoTimings.length/2)],sourceFrameP95Ms:videoTimings[Math.floor(videoTimings.length*.95)],handMedianMs:handTimings.sort((a,b)=>a-b)[Math.floor(handTimings.length/2)],poseMedianMs:poseTimings.sort((a,b)=>a-b)[Math.floor(poseTimings.length/2)],tracking,mirror};
  };
  return true;
})();
