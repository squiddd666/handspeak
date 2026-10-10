// Classic worker: MediaPipe WASM loader requires importScripts.
let detector,isUsableHand,motionFrame;

self.onmessage=async({data})=>{
 try{
  if(data.type==='init'){
   const {FilesetResolver,HandLandmarker}=await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/+esm');
   ({isUsableHand}=await import('./gesture-model.js'));({motionFrame}=await import('./motion-model.js'));
   const files=await FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/wasm');
   detector=await HandLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:new URL('./hand.task',self.location.href).href,delegate:'CPU'},runningMode:'VIDEO',numHands:2,minHandDetectionConfidence:.65,minHandPresenceConfidence:.65,minTrackingConfidence:.6});
   self.postMessage({type:'ready'});return;
  }
  const start=performance.now();
  const result=detector.detectForVideo(new ImageData(new Uint8ClampedArray(data.pixels),data.width,data.height),data.timestamp);
  const ids=result.landmarks.map((h,i)=>isUsableHand(h)?i:-1).filter(i=>i>=0);
  self.postMessage({type:'frame',timestamp:data.timestamp,raw:result.landmarks.length,frame:motionFrame({landmarks:ids.map(i=>result.landmarks[i]),handedness:ids.map(i=>result.handedness[i])}),processingMs:performance.now()-start});
 }catch(error){self.postMessage({type:'error',message:error.message});}
};
