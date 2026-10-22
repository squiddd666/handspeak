const POSE_INDICES=[0,2,5,11,12,13,14];

export function createBeginnerRecognition({isRunning,startCamera,onWord,onStatus,prepare}){
  const $=s=>document.querySelector(s);
  let available=false,pose=null,capture=null,pending='',lastPoseAt=-Infinity,request=null,holisticBusy=false,labels=[];
  const status=$('#beginnerStatus'),record=$('#beginnerRecord'),accept=$('#beginnerAccept');
  if(!status||!record||!accept)return {frame(){},cancel(){},isCapturing:()=>false};
  function message(value){status.textContent=value;}
  function controls(){record.disabled=!available||Boolean(capture||request);accept.disabled=!pending;}
  async function refresh(){
    try{
      const response=await fetch('/api/beginner-asl/status',{cache:'no-store'}),data=await response.json();
      available=Boolean(data.available&&Array.isArray(data.labels)&&data.labels.length);
      labels=data.labels||[];
      const count=$('#beginnerCount');if(count)count.textContent=available?`${labels.length} signs`:'Not trained';
      $('#beginnerVocabulary').textContent=labels.join(' · ')||'Model not trained yet';
      message(available
        ?`${labels.length}-word Beginner model ready (words not covered by other camera models). Record one complete sign for four seconds; review before adding. Live-camera accuracy is unverified.`
        :'Beginner model checkpoint not found yet. Train beginner100-v1.pt to enable this panel.');
    }catch{available=false;message('Beginner model status unavailable.');}
    controls();
  }
  async function loadPose(){
    if(pose)return;
    message('Loading full-body and hand tracking…');
    if(!window.Holistic)await new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='https://cdn.jsdelivr.net/npm/@mediapipe/holistic@0.5.1675471629/holistic.js';script.onload=resolve;script.onerror=()=>reject(Error('Holistic tracker download failed'));document.head.append(script);});
    pose=new window.Holistic({locateFile:file=>`https://cdn.jsdelivr.net/npm/@mediapipe/holistic@0.5.1675471629/${file}`});
    pose.setOptions({modelComplexity:1,smoothLandmarks:true,minDetectionConfidence:.5,minTrackingConfidence:.5});
    pose.onResults(result=>{
      holisticBusy=false;if(!capture)return;
      const points=value=>value?.length===21?value.map(p=>[p.x,p.y,p.z||0]):null;
      if(!result.poseLandmarks)return;
      if(!result.leftHandLandmarks&&!result.rightHandLandmarks)return;
      capture.frames.push({pose:POSE_INDICES.map(i=>{const p=result.poseLandmarks[i];return[p.x,p.y,p.z||0];}),left:points(result.leftHandLandmarks),right:points(result.rightHandLandmarks)});
    });
  }
  function cancel(text='Beginner recording canceled.'){capture=null;pending='';accept.disabled=true;record.disabled=!available;message(text);}
  async function begin(){
    if(!$('#beginnerConsent').checked){message('Enable landmark processing for this model first. Camera video is not uploaded.');return;}
    pending='';controls();
    try{
      prepare();
      if(!isRunning())await startCamera();
      if(!isRunning())return;
      await loadPose();
      message('Get ready… recording starts in 1.5 seconds.');
      record.disabled=true;
      setTimeout(()=>{if(!isRunning()){cancel('Start the camera and try again.');return;}capture={start:performance.now(),frames:[]};lastPoseAt=-Infinity;message('Recording for four seconds… perform one complete sign.');onStatus('—','Recording with the Beginner model…');},1500);
    }catch(error){cancel(`Could not load tracking: ${error.message||'reload and try again.'}`);}
  }
  async function finish(){
    const frames=capture?.frames||[];capture=null;
    if(frames.length<5){cancel(`Not enough tracked frames (${frames.length}/5).`);return;}
    request=new AbortController();controls();message('Analyzing landmarks on the server…');
    const timeout=setTimeout(()=>request?.abort(),20000);
    try{
      const response=await fetch('/api/beginner-asl',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({consent:true,frames}),signal:request.signal});
      const data=await response.json();if(!response.ok)throw Error(data.error||'Recognition failed');
      pending=data.predictions?.[0]?.label||'';
      const names=(data.predictions||[]).map((item,index)=>`${index+1}. ${item.label}`).join(' · ');
      if(!pending){
        message(data.lowConfidence?'No confident Beginner match. Sign again.':'No prediction returned.');
        onStatus('No reliable match','Beginner model — verify before adding.');
        return;
      }
      message(`Possible match: ${pending}. Top five: ${names}. Verify before adding.`);
      onStatus(pending,'Beginner model prediction — verify before adding. Scores are not calibrated confidence.');
    }catch(error){message(error.name==='AbortError'?'Recognition timed out. Try again.':error.message);pending='';}
    finally{clearTimeout(timeout);request=null;controls();}
  }
  function frame(detection,now,video){
    if(!capture||!pose||holisticBusy||now-lastPoseAt<65)return;
    lastPoseAt=now;holisticBusy=true;
    pose.send({image:video}).catch(error=>{holisticBusy=false;cancel(`Tracking stopped: ${error.message}`);});
    if(now-capture.start>=4000)void finish();
  }
  record.addEventListener('click',()=>void begin());
  $('#beginnerCancel')?.addEventListener('click',()=>cancel());
  accept.addEventListener('click',()=>{if(pending&&onWord(pending)!==false){message(`Added ${pending} to the draft.`);pending='';controls();}});
  window.addEventListener('pagehide',()=>{request?.abort();pose?.close?.();});
  void refresh();controls();
  return {frame,cancel,isCapturing:()=>Boolean(capture)};
}
