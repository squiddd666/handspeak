// Experimental only. Both detectors see copies of ONE immutable frame. Their
// outputs remain separate; Holistic results are forwarded without hand fusion.
export const MANUAL_OPTIONS = Object.freeze({runningMode:'VIDEO',numHands:2,
  minHandDetectionConfidence:.5,minHandPresenceConfidence:.5,minTrackingConfidence:.5});
export function pixelDigest(bytes) {
  let hash=2166136261;
  for(const byte of bytes)hash=Math.imul(hash^byte,16777619);
  return (hash>>>0).toString(16).padStart(8,'0');
}
export async function freezeFrame(image) {
  const bitmap=await createImageBitmap(image),canvas=new OffscreenCanvas(bitmap.width,bitmap.height);
  const ctx=canvas.getContext('2d',{willReadFrequently:true});
  try {ctx.drawImage(bitmap,0,0);return {image:bitmap,width:bitmap.width,height:bitmap.height,
    pixelDigest:pixelDigest(ctx.getImageData(0,0,bitmap.width,bitmap.height).data),dispose:()=>bitmap.close()};}
  catch(error){bitmap.close();throw error;}
}

export async function createIndependentManualTracker({makeWorker=()=>new Worker(new URL('./dual_hand_worker.js',import.meta.url)),
  copyImage=image=>createImageBitmap(image),timeoutMs=20000}={}) {
  const worker=makeWorker();let closed=false,serial=0,pending=null,delegate;
  function request(type,payload={},transfers=[]) {
    if(closed||pending)return Promise.reject(new Error('Independent hand tracker is unavailable'));
    const id=++serial;
    return new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{pending=null;reject(new Error('Independent hand tracker timed out'));},timeoutMs);
      pending={id,resolve,reject,timer};
      try{worker.postMessage({type,id,...payload},transfers);}catch(error){clearTimeout(timer);pending=null;reject(error);}
    });
  }
  worker.onmessage=({data})=>{
    if(data.id!==pending?.id)return;
    const p=pending;pending=null;clearTimeout(p.timer);
    if(data.type==='error')p.reject(new Error(data.message));else p.resolve(data);
  };
  worker.onerror=event=>{if(pending){clearTimeout(pending.timer);pending.reject(new Error(event.message||'Independent worker failed'));pending=null;}};
  function close(){closed=true;if(pending){clearTimeout(pending.timer);pending.reject(new Error('Independent hand tracker closed'));pending=null;}worker.terminate();}
  try{delegate=(await request('init')).delegate;}catch(error){close();throw error;}
  return {get delegate(){return delegate;},
    async detect(frame,timestamp,epoch){
      if(closed)throw new Error('Independent hand tracker closed');
      const bitmap=await copyImage(frame.image);
      if(closed){bitmap.close();throw new Error('Independent hand tracker closed');}
      try{return await request('frame',{bitmap,timestamp,epoch},[bitmap]);}
      catch(error){try{bitmap.close();}catch{}throw error;}
    },
    async reset(){delegate=(await request('reset')).delegate;},close};
}

export async function createDualTracker({bodyFactory,manualFactory=createIndependentManualTracker,
  freeze=freezeFrame,onPair=()=>{}}={}) {
  bodyFactory ||= async()=>{
    const {createHolisticBodyTracker}=await import('../../landmark-capture.js?v=20261107-capture-10');
    return createHolisticBodyTracker();
  };
  const body=await bodyFactory();let manual;
  try{manual=await manualFactory();}catch(error){body.close();throw error;}
  let callback=()=>{},flight=null,epoch=0,last=-Infinity,closed=false;
  body.onResults(result=>{if(flight&&!flight.bodyResult)flight.bodyResult=result;});
  return {kind:'Experimental independent Holistic + Tasks VIDEO streams',complexity:body.complexity,usesTimestamp:true,
    executionContext:body.executionContext||'main-thread',get bodyKind(){return body.kind;},
    onResults(fn){callback=fn;},
    async reset(){
      if(closed||flight)throw new Error('Cannot reset an active dual frame');
      await Promise.all([body.reset?.(),manual.reset()]);epoch++;last=-Infinity;
    },
    async send({image,timestamp}){
      if(closed||flight||!Number.isFinite(timestamp)||timestamp<=last)throw new Error('Invalid dual capture timestamp or concurrent send');
      last=timestamp;
      const packet={epoch,timestamp,bodyResult:null};flight=packet;let frozen;
      try {
        frozen=await freeze(image);
        if(closed)throw new Error('Dual tracker closed');
        // allSettled keeps the shared bitmap alive until BOTH readers finish,
        // even when one detector fails. No result from the other is substituted.
        const results=await Promise.allSettled([body.send({image:frozen.image}),manual.detect(frozen,timestamp,epoch)]);
        if(results.some(r=>r.status==='rejected'))throw results.find(r=>r.status==='rejected').reason;
        const hands=results[1].value;
        if(closed)throw new Error('Dual tracker closed');
        if(!packet.bodyResult)throw new Error('Missing real body result');
        if(hands.timestamp!==timestamp||hands.epoch!==epoch||hands.width!==frozen.width||hands.height!==frozen.height||
          hands.pixelDigest!==frozen.pixelDigest)throw new Error('Detector source, timestamp, or frame pixels differ');
        onPair({epoch,timestamp,width:frozen.width,height:frozen.height,pixelEquality:true,
          body:packet.bodyResult,manual:hands,bodyTracker:body.kind,manualDelegate:manual.delegate});
        callback(packet.bodyResult); // The ORIGINAL body object, not hand-merged output.
      } finally {frozen?.dispose();if(flight===packet)flight=null;}
    },
    close(){closed=true;try{manual.close();}finally{return body.close();}}
  };
}
