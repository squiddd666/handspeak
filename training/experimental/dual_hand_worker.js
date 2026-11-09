// Independent VIDEO-mode graph, never the IMAGE-mode body recovery detector.
let hands,options,files,HandLandmarker,last=-Infinity;
self.onmessage=async({data})=>{
  try{
    if(data.type==='init'){
      const {MANUAL_OPTIONS}=await import('./dual_capture.mjs');
      const {preferredVisionDelegate}=await import('../../camera-performance.js?v=20261010-single-1');
      const vision=await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/+esm');
      HandLandmarker=vision.HandLandmarker;files=await vision.FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/wasm');
      const delegate=preferredVisionDelegate(()=>new OffscreenCanvas(1,1));
      options={...MANUAL_OPTIONS,baseOptions:{modelAssetPath:'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',delegate}};
      if(delegate==='GPU')options.canvas=new OffscreenCanvas(1,1);
      try{hands=await HandLandmarker.createFromOptions(files,options);}catch(error){
        if(delegate==='CPU')throw error;delete options.canvas;options.baseOptions.delegate='CPU';hands=await HandLandmarker.createFromOptions(files,options);
      }
    }else if(data.type==='reset'){
      hands.close();hands=await HandLandmarker.createFromOptions(files,options);last=-Infinity;
    }else if(data.type==='frame'){
      try{
        if(data.timestamp<=last)throw new Error('Non-increasing manual frame timestamp');last=data.timestamp;
        const {pixelDigest}=await import('./dual_capture.mjs');
        const canvas=new OffscreenCanvas(data.bitmap.width,data.bitmap.height),ctx=canvas.getContext('2d',{willReadFrequently:true});
        ctx.drawImage(data.bitmap,0,0);
        const digest=pixelDigest(ctx.getImageData(0,0,canvas.width,canvas.height).data);
        const result=hands.detectForVideo(data.bitmap,data.timestamp);
        self.postMessage({type:'frame',id:data.id,epoch:data.epoch,timestamp:data.timestamp,width:canvas.width,height:canvas.height,
          pixelDigest:digest,landmarks:result.landmarks,handedness:result.handedness});
        return;
      }finally{data.bitmap.close();}
    }
    self.postMessage({type:'ready',id:data.id,delegate:options.baseOptions.delegate});
  }catch(error){self.postMessage({type:'error',id:data.id,message:String(error.message||error)});}
};
