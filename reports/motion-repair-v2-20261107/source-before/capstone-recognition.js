import {sharedLandmarkCapture,recordingDurationMs} from './landmark-capture.js?v=20261107-capture-6';
const friendly=label=>label.replace(/[12]$/,'').replaceAll('-',' ').replaceAll('/',' / ');

export function createCapstoneRecognition({isRunning,startCamera,onWord,onStatus,prepare,onTracking,onDiagnostic,captureService=sharedLandmarkCapture()}){
  const $=selector=>document.querySelector(selector);
  const owner=Symbol('capstone');
  let available=false,pending='',request=null,vocabMode='core',starting=false,revision=0;
  const status=$('#capstoneStatus'),record=$('#capstoneRecord'),accept=$('#capstoneAccept');
  const TIERS={core:{name:'core',count:7},extended:{name:'extended',count:19},full:{name:'full',count:100}};
  function message(value){status.textContent=value;}
  const busy=()=>starting||Boolean(request)||captureService.active(owner);
  function controls(){record.disabled=!available||busy();accept.disabled=!pending;$('#capstoneVocabMode').disabled=busy();}
  async function refresh(){
    try{
      const response=await fetch('/api/capstone-asl/status',{cache:'no-store'}),data=await response.json();
      if(!response.ok||!data.available||!Array.isArray(data.labels)||data.labels.length!==100)throw Error();
      available=true;
      vocabMode=$('#capstoneVocabMode')?.value||'core';
      if(!TIERS[vocabMode])vocabMode='core';
      showVocabulary(data);
      const tier=TIERS[vocabMode];
      message(`${tier.count}-word ${tier.name} vocabulary ready${data.calibrationId?' · validation-calibrated rejection gates':''}. Choose a recording length and record one complete sign; review the top prediction. Live-camera accuracy is unverified.`);
    }catch{message('The 100-word model is unavailable. Reload the page to retry.');}
    controls();
  }
  function showVocabulary(data){
    const names=vocabMode==='core'?(data.coreLabels||data.labels)
      :vocabMode==='extended'?(data.extendedLabels||data.labels):data.labels;
    $('#capstoneVocabulary').textContent=names.map(friendly).join(' · ');
    const summary=$('#capstoneWords details.camera-tip summary');
    if(summary)summary.textContent=vocabMode==='full'?'See all 100 available signs':`See the ${names.length} available signs`;
  }
  function cancel(text='100-word recording canceled.'){
    revision++;starting=false;captureService.cancel(owner);request?.abort();request=null;pending='';controls();message(text);
  }
  async function begin(){
    if(busy())return;
    if(!$('#capstoneConsent').checked){message('Enable landmark processing for this model first. Camera video is not uploaded.');return;}
    prepare();
    const run=++revision,mode=vocabMode,durationMs=recordingDurationMs($('#serverCaptureSeconds')?.value);
    starting=true;pending='';controls();
    try{
      if(!isRunning())await startCamera();
      if(run!==revision||!isRunning())return;
      await captureService.begin({owner,isRunning,onTracking,durationMs,
        onPhase:phase=>{
          if(phase==='loading')message('Loading full-body and hand tracking…');
          if(phase==='countdown')message('Get ready… warming up tracking for at least 1.5 seconds. Keep your upper body and at least one hand visible.');
          if(phase==='recording'){message(`Recording for ${durationMs/1000} seconds… perform one complete sign.`);onStatus('—','Recording with the 100-word model…');}
          if(phase==='draining')message('Tracking the remaining captured frames… images stay in this tab only.');
          controls();
        },
        onComplete:(frames,metrics)=>{onDiagnostic?.({capture:'capstone',...metrics});void finish(frames,mode,run);},
        onError:error=>cancel(error.message),onCancel:()=>{starting=false;controls();},
      });
    }catch(error){if(run===revision)cancel(`Could not load upper-body tracking: ${error.message||'reload and try again.'}`);}
    finally{if(run===revision){starting=false;controls();}}
  }
  async function finish(frames,mode,run){
    if(run!==revision)return;
    starting=false;
    if(frames.length<5){cancel(`Not enough tracked frames (${frames.length}/5). Keep your upper body and at least one hand visible.`);return;}
    const controller=new AbortController();request=controller;controls();message('Analyzing the recorded landmarks on the server…');
    const timeout=setTimeout(()=>controller.abort(),20000);
    try{
      const response=await fetch('/api/capstone-asl',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({consent:true,frames,vocabulary:mode}),signal:controller.signal});
      const data=await response.json();if(!response.ok)throw Error(data.error||'Recognition failed');
      if(run!==revision)return;
      pending=data.predictions?.[0]?.label||'';
      const names=(data.predictions||[]).map((item,index)=>`${index+1}. ${friendly(item.label)}`).join(' · ');
      const scope=`${data.vocabularySize||TIERS[mode].count}-word ${data.vocabulary||mode}`;
      if(!pending){
        const reasons={'low-score':'low score',ambiguous:'similar competing scores','outside-vocabulary':'outside the selected vocabulary'};
        const suggestions=(data.suggestions||[]).map((item,index)=>`${index+1}. ${friendly(item.label)}`).join(' · ');
        message(data.lowConfidence
          ?`No reliable match in the ${TIERS[mode].count}-word ${mode} vocabulary${reasons[data.rejectionReason]?` (${reasons[data.rejectionReason]})`:''}. ${suggestions?`Unaccepted suggestions: ${suggestions}. `:''}Nothing added. Try again with the complete sign visible.`
          :'No prediction returned. Try recording again.');
        onStatus('No reliable match',data.lowConfidence
          ?`${TIERS[mode].count}-word model found no confident match — nothing added.`
          :'100-word model prediction — verify before adding. Scores are not calibrated confidence.');
        return;
      }
      message(`Possible match: ${friendly(pending)}. Top five (${scope}): ${names}. Verify before adding.`);
      onStatus(pending?friendly(pending):'No reliable match','100-word model prediction — verify before adding. Scores are not calibrated confidence.');
    }catch(error){if(run===revision){message(error.name==='AbortError'?'Recognition timed out. Try again.':error.message);pending='';}}
    finally{clearTimeout(timeout);if(request===controller){request=null;controls();}}
  }
  function frame(detection,now,video){
    captureService.frame(owner,now,video);
  }
  record.addEventListener('click',()=>void begin());
  $('#capstoneCancel').addEventListener('click',()=>cancel());
  $('#capstoneVocabMode')?.addEventListener('change',()=>void refresh());
  accept.addEventListener('click',()=>{if(pending&&onWord(friendly(pending))!==false){message(`Added ${friendly(pending)} to the draft. Review it before speaking.`);pending='';controls();}});
  window.addEventListener('pagehide',()=>cancel());
  void refresh();controls();
  return {frame,cancel,isCapturing:busy};
}
