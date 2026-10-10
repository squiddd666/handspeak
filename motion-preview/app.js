const $=id=>document.getElementById(id),video=document.querySelector('video'),canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d',{willReadFrequently:true});
let model,worker,stream,revision=0,generation=0,raf=0,lastVideo=-1,lastCaptureAt=-Infinity,delegate='',cameraInput='',times=[],events=[],lastCapture=null,rawHands=0,usableHands=0;
let queue=[],busy=false,captureActive=false,landmarks=[],landmarksAt=-Infinity,lagMs=0,processingMs=0,overloads=0,initReject=null;
function fps(){return times.length>1?Math.round((times.length-1)*10000/(times.at(-1)-times[0]))/10:0;}
function report(){return {build:'20261004-framing-preview-3',scope:'Experimental preview; main recognizer unchanged',checkpoint:model?.checkpointSha256,cameraActive:Boolean(stream),expected:$('expected').value,input:cameraInput,delegate,processedFps:fps(),queueFrames:queue.length,lagMs,processingMs,overloads,rawHands,usableHands,lastCapture,events};}
function resetCapture(){generation++;queue=[];worker?.postMessage({type:'reset'});landmarks=[];captureActive=false;lastCapture=null;}
function stop(){revision++;cancelAnimationFrame(raf);stream?.getTracks().forEach(t=>t.stop());stream=null;video.srcObject=null;worker?.terminate();worker=null;initReject?.(Error('Camera stopped'));initReject=null;queue=[];busy=false;ctx.clearRect(0,0,canvas.width,canvas.height);$('start').disabled=false;$('stop').disabled=true;$('status').textContent='Camera stopped.';$('metrics').textContent=`Last measured rate: ${fps()} processed frames/sec`;}
async function loadModel(){
 if(model)return;
 const [response,integrityResponse]=await Promise.all([fetch('./model.json'),fetch('./integrity.json')]);
 if(!response.ok||!integrityResponse.ok)throw Error('Model download failed.');
 const bytes=await response.arrayBuffer(),integrity=await integrityResponse.json();
 const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),n=>n.toString(16).padStart(2,'0')).join('');
 if(hash!==integrity.modelSha256)throw Error('Model verification failed. Reload the page.');
 const candidate=JSON.parse(new TextDecoder().decode(bytes));
 if(candidate.featureMode!=='hands-only'||candidate.checkpointSha256!==integrity.checkpointSha256)throw Error('Model metadata mismatch.');
 model=candidate;
}
function overload(){overloads++;resetCapture();$('result').textContent='Processing is falling behind — pause, then try again.';}
function drain(){
 if(busy||!worker||!queue.length)return;
 if(performance.now()-queue[0].timestamp>2500){overload();return;}
 busy=true;const packet=queue.shift();worker.postMessage(packet,[packet.pixels]);
}
async function loadWorker(version){
 await loadModel();if(version!==revision)return;
 worker=new Worker('./recognizer-worker.js');
 await new Promise((resolve,reject)=>{
  initReject=reject;
  worker.onerror=error=>{if(version!==revision)return;reject(Error(error.message||'Recognition worker failed'));stop();$('status').textContent='Recognition stopped. Reload and try again.';};
  worker.onmessage=({data})=>{
   if(version!==revision)return;
   if(data.type==='ready'){delegate=data.delegate;initReject=null;resolve();return;}
   if(data.type==='error'){reject(Error(data.message));stop();$('status').textContent='Recognition stopped: '+data.message;return;}
   busy=false;
   if(data.generation===generation){
    lagMs=Math.round(performance.now()-data.timestamp);processingMs=Math.round(data.processingMs);
    if(lagMs>2500){overload();drain();return;}
    captureActive=data.active;rawHands=data.rawHands;usableHands=data.usableHands;landmarks=data.landmarks;landmarksAt=data.timestamp;
    const now=performance.now();times.push(now);times=times.filter(t=>now-t<2000);
    $('status').textContent=data.active?'Analyzing movement… finish the sign, then pause.':usableHands?'Hand detected — sign once, then pause.':'No hand detected — keep your hands in view.';
    if(data.result){lastCapture={...data.result,lagMs};events.push({...lastCapture,expected:$('expected').value});events=events.slice(-20);$('result').textContent=lastCapture.label?'Possible match: '+lastCapture.label:lastCapture.validSequence?'No reliable match':'Not enough clear hand frames';}
    $('metrics').textContent=`${fps()} processed frames/sec · ${usableHands} usable hand(s) · ${Math.round(lagMs/100)/10}s delay · ${delegate} delegate`;
   }
   drain();
  };
  worker.postMessage({type:'init',model});
 });
}
function frame(version){
 if(version!==revision||!stream)return;
 try{
  const now=performance.now(),interval=delegate==='GPU'?30:captureActive?60:lagMs>500?120:80;
  if(video.readyState>=2&&video.currentTime!==lastVideo&&now-lastCaptureAt>=interval){
   lastVideo=video.currentTime;lastCaptureAt=now;
   const scale=Math.min(1,640/Math.max(video.videoWidth,video.videoHeight)),width=Math.round(video.videoWidth*scale),height=Math.round(video.videoHeight*scale);
   if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;resetCapture();}
   ctx.drawImage(video,0,0,width,height);
   if(queue.length>=36)overload();
   const pixels=ctx.getImageData(0,0,width,height).data.buffer;
   queue.push({type:'frame',generation,timestamp:now,width,height,pixels});drain();
   if(now-landmarksAt<200){ctx.fillStyle='#a2f7d2';for(const hand of landmarks)for(const point of hand){ctx.beginPath();ctx.arc(point.x*width,point.y*height,3,0,Math.PI*2);ctx.fill();}}
  }
  raf=requestAnimationFrame(()=>frame(version));
 }catch(error){stop();$('status').textContent='Recognition stopped: '+error.message;}
}
$('start').addEventListener('click',async()=>{
 const version=++revision;$('start').disabled=true;$('stop').disabled=false;$('status').textContent='Opening camera and loading recognizer…';
 try{
  const incoming=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:640},height:{ideal:480},frameRate:{ideal:30}},audio:false});
  if(version!==revision){incoming.getTracks().forEach(t=>t.stop());return;}
  stream=incoming;video.srcObject=stream;await video.play();cameraInput=video.videoWidth+'x'+video.videoHeight;await loadWorker(version);
  if(version!==revision)return;
  resetCapture();times=[];events=[];overloads=0;lagMs=0;lastVideo=-1;lastCaptureAt=-Infinity;rawHands=0;usableHands=0;$('result').textContent='Ready — sign once';frame(version);
 }catch(error){if(version===revision){stop();$('status').textContent=error.name==='NotAllowedError'?'Camera permission was denied. Allow camera access and try again.':'Unable to start: '+error.message;}}
});
$('stop').addEventListener('click',stop);
$('mirror').addEventListener('change',()=>canvas.classList.toggle('mirrored',$('mirror').checked));canvas.classList.add('mirrored');
$('expected').addEventListener('change',()=>{resetCapture();events=[];$('result').textContent='Ready — sign once';});
$('copy').addEventListener('click',async()=>{const text=JSON.stringify(report(),null,2);$('report').value=text;$('report').hidden=false;try{await navigator.clipboard.writeText(text);$('copyStatus').textContent='Report copied. Paste it into the project chat.';}catch{$('copyStatus').textContent='Select and copy the report below.';$('report').focus();$('report').select();}});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});window.addEventListener('pagehide',stop);
$('start').disabled=false;$('status').textContent='Select your camera or OBS Virtual Camera when your browser asks.';
