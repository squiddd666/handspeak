// Classic worker: the pinned MediaPipe WASM loader uses importScripts.
let hands,model,capture,motionFrame,isUsableHand,classify,delegate;
self.onmessage=async({data})=>{
 try{
  if(data.type==='init'){
   model=data.model;
   const {FilesetResolver,HandLandmarker}=await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/+esm');
   ({motionFrame}=await import('./motion-model.js'));({isUsableHand}=await import('./gesture-model.js'));({classify}=await import('./classifier.js'));
   const {createAutomaticMotion}=await import('./capture.js');capture=createAutomaticMotion({sampleIntervalMs:30});
   const files=await FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/wasm');
   delegate='CPU';let canvas;
   try{const probe=new OffscreenCanvas(1,1),gl=probe.getContext('webgl2'),extension=gl?.getExtension('WEBGL_debug_renderer_info'),renderer=extension?gl.getParameter(extension.UNMASKED_RENDERER_WEBGL):'';if(gl&&!/swiftshader|llvmpipe|software/i.test(renderer)){delegate='GPU';canvas=new OffscreenCanvas(1,1);}gl?.getExtension('WEBGL_lose_context')?.loseContext();}catch{}
   const options={baseOptions:{modelAssetPath:'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',delegate},runningMode:'VIDEO',numHands:2,minHandDetectionConfidence:.65,minHandPresenceConfidence:.65,minTrackingConfidence:.6};
   if(canvas)options.canvas=canvas;
   try{hands=await HandLandmarker.createFromOptions(files,options);}catch(error){if(delegate==='CPU')throw error;delete options.canvas;options.baseOptions.delegate='CPU';delegate='CPU';hands=await HandLandmarker.createFromOptions(files,options);}
   self.postMessage({type:'ready',delegate});return;
  }
  if(data.type==='reset'){capture.reset();return;}
  if(data.type!=='frame')throw Error('Unsupported worker message');
  const before=performance.now(),detection=hands.detectForVideo(new ImageData(new Uint8ClampedArray(data.pixels),data.width,data.height),data.timestamp);
  const indices=detection.landmarks.map((hand,i)=>isUsableHand(hand)?i:-1).filter(i=>i>=0);
  const landmarks=indices.map(i=>detection.landmarks[i]);
  const clip=capture.push(motionFrame({landmarks,handedness:indices.map(i=>detection.handedness[i])}),data.timestamp,data.height/data.width);
  let result=null;
  if(clip){const started=performance.now();result={frames:clip.frames.length,trackedFrames:clip.frames.filter(f=>f.some(Boolean)).length,durationMs:Math.round(data.timestamp-clip.start),...classify(model,clip.frames,clip.imageAspect),classifierMs:Math.round(performance.now()-started)};}
  self.postMessage({type:'frame',generation:data.generation,timestamp:data.timestamp,rawHands:detection.landmarks.length,usableHands:indices.length,landmarks,active:capture.isActive(),result,processingMs:performance.now()-before});
 }catch(error){self.postMessage({type:'error',message:error.message});}
};
