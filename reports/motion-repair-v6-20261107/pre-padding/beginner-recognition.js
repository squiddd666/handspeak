import {sharedLandmarkCapture,recordingDurationMs} from './landmark-capture.js?v=20261107-capture-10';

export function createBeginnerRecognition({isRunning,startCamera,onWord,onStatus,prepare,onTracking,onDiagnostic,captureService=sharedLandmarkCapture()}){
  const $=s=>document.querySelector(s);
  const owner=Symbol('beginner');
  let available=false,pending='',request=null,labels=[],starting=false,revision=0;
  const status=$('#beginnerStatus'),record=$('#beginnerRecord'),accept=$('#beginnerAccept');
  if(!status||!record||!accept)return {frame(){},cancel(){},isCapturing:()=>false};
  function message(value){status.textContent=value;}
  const busy=()=>starting||Boolean(request)||captureService.active(owner);
  function controls(){record.disabled=!available||busy();accept.disabled=!pending;}
  async function refresh(){
    try{
      const response=await fetch('/api/beginner-asl/status',{cache:'no-store'}),data=await response.json();
      available=Boolean(data.available&&Array.isArray(data.labels)&&data.labels.length);
      labels=data.labels||[];
      const count=$('#beginnerCount');if(count)count.textContent=available?`${labels.length} signs`:'Not trained';
      $('#beginnerVocabulary').textContent=labels.join(' · ')||'Model not trained yet';
      message(available
        ?`${labels.length}-word Beginner model ready${data.calibrationId?' · validation-calibrated rejection gates':''} (words not covered by other camera models). Choose a recording length and record one complete sign; review before adding. Live-camera accuracy is unverified.`
        :'Beginner model checkpoint not found yet. Train beginner100-v1.pt to enable this panel.');
    }catch{available=false;message('Beginner model status unavailable.');}
    controls();
  }
  function cancel(text='Beginner recording canceled.'){
    revision++;starting=false;captureService.cancel(owner);request?.abort();request=null;pending='';controls();message(text);
  }
  async function begin(){
    if(busy())return;
    if(!$('#beginnerConsent').checked){message('Enable landmark processing for this model first. Camera video is not uploaded.');return;}
    prepare();
    const run=++revision,durationMs=recordingDurationMs($('#serverCaptureSeconds')?.value);
    starting=true;pending='';controls();
    try{
      if(!isRunning())await startCamera();
      if(run!==revision||!isRunning())return;
      await captureService.begin({owner,isRunning,onTracking,durationMs,
        onPhase:phase=>{
          if(phase==='loading')message('Loading full-body and hand tracking…');
          if(phase==='countdown')message('Get ready… warming up tracking for at least 1.5 seconds.');
          if(phase==='recording'){message(`Recording for ${durationMs/1000} seconds… perform one complete sign.`);onStatus('—','Recording with the Beginner model…');}
          if(phase==='draining')message('Tracking the remaining captured frames… images stay in this tab only.');
          controls();
        },
        onComplete:(frames,metrics)=>{onDiagnostic?.({capture:'beginner',...metrics});void finish(frames,run);},
        onError:error=>cancel(error.message),onCancel:()=>{starting=false;controls();},
      });
    }catch(error){if(run===revision)cancel(`Could not load tracking: ${error.message||'reload and try again.'}`);}
    finally{if(run===revision){starting=false;controls();}}
  }
  async function finish(frames,run){
    if(run!==revision)return;
    starting=false;
    if(frames.length<5){cancel(`Not enough tracked frames (${frames.length}/5).`);return;}
    const controller=new AbortController();request=controller;controls();message('Analyzing landmarks on the server…');
    const timeout=setTimeout(()=>controller.abort(),20000);
    try{
      const response=await fetch('/api/beginner-asl',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({consent:true,frames}),signal:controller.signal});
      const data=await response.json();if(!response.ok)throw Error(data.error||'Recognition failed');
      if(run!==revision)return;
      pending=data.predictions?.[0]?.label||'';
      const names=(data.predictions||[]).map((item,index)=>`${index+1}. ${item.label}`).join(' · ');
      if(!pending){
        const reasons={'low-score':'low score',ambiguous:'similar competing scores','outside-vocabulary':'outside the selected vocabulary'};
        const suggestions=(data.suggestions||[]).map((item,index)=>`${index+1}. ${item.label}`).join(' · ');
        message(data.lowConfidence?`No reliable match in the Beginner vocabulary${reasons[data.rejectionReason]?` (${reasons[data.rejectionReason]})`:''}. ${suggestions?`Unaccepted suggestions: ${suggestions}. `:''}Nothing added. Sign again.`:'No prediction returned.');
        onStatus('No reliable match','Beginner model — verify before adding.');
        return;
      }
      message(`Possible match: ${pending}. Top five: ${names}. Verify before adding.`);
      onStatus(pending,'Beginner model prediction — verify before adding. Scores are not calibrated confidence.');
    }catch(error){if(run===revision){message(error.name==='AbortError'?'Recognition timed out. Try again.':error.message);pending='';}}
    finally{clearTimeout(timeout);if(request===controller){request=null;controls();}}
  }
  function frame(detection,now,video){
    captureService.frame(owner,now,video);
  }
  record.addEventListener('click',()=>void begin());
  $('#beginnerCancel')?.addEventListener('click',()=>cancel());
  accept.addEventListener('click',()=>{if(pending&&onWord(pending)!==false){message(`Added ${pending} to the draft.`);pending='';controls();}});
  window.addEventListener('pagehide',()=>cancel());
  void refresh();controls();
  return {frame,cancel,isCapturing:busy};
}
