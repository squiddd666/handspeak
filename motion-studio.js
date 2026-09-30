import {motionFrame,encodeMotion,validMotion,recognizeMotion,validMotionParameters} from './motion-model.js';

export function createMotionStudio({isRunning,onWord,onStatus,speak}){
  const $=s=>document.querySelector(s), key='handspeak-motion-v2';
  let examples=[],baseExamples=[],parameters,baseState='Loading pretrained words…',capture=null,pending=null,lastSample=-Infinity,legacyExamples=false;
  const allExamples=()=>baseExamples.concat(examples);
  const labelOK=label=>typeof label==='string'&&/^[a-zA-Z][a-zA-Z '-]{0,29}$/.test(label);
  try{
    const saved=JSON.parse(localStorage.getItem(key)||'[]');
    if(Array.isArray(saved))examples=saved.slice(0,96).filter(e=>labelOK(e.label)&&validMotion(e.sequence));
    const legacy=JSON.parse(localStorage.getItem('handspeak-motion-v1')||'[]');
    legacyExamples=Array.isArray(legacy)&&legacy.length>0;
  }catch{}
  async function loadPretrained(){
    try{
      const response=await fetch('./models/asl-words.json');
      if(!response.ok)throw new Error('Word model download failed');
      const model=await response.json();
      if(model.version!==1||model.encoding!=='two-hand-motion-v2'||!validMotionParameters(model.parameters)
        ||!Array.isArray(model.samples)||model.samples.length<6||model.samples.length>600
        ||!model.samples.every(e=>labelOK(e.label)&&validMotion(e.sequence)))throw new Error('Invalid word model');
      const counts={};model.samples.forEach(e=>counts[e.label]=(counts[e.label]||0)+1);
      if(Object.keys(counts).length<2||Object.values(counts).some(n=>n<3))throw new Error('Insufficient word references');
      baseExamples=model.samples;parameters=model.parameters;
      baseState=`${new Set(baseExamples.map(e=>e.label)).size} pretrained words loaded`;
    }catch(error){console.warn(error);baseState='Pretrained words unavailable — reload to retry';}
    render();
  }
  function render(){
    const counts={};allExamples().forEach(e=>counts[e.label]=(counts[e.label]||0)+1);
    $('#motionLibrary').textContent=Object.keys(counts).join(' · ')||'No word examples loaded yet.';
    $('#motionModelStatus').textContent=`${baseState} · ${examples.length} personal examples${legacyExamples?' · Older personal recordings use a previous format; re-record those words if you want to use them.':''}`;
    $('#motionReady').textContent=Object.values(counts).filter(n=>n>=3).length>=2
      ?(baseExamples.length?'Ready — no personal training required':'Personal vocabulary ready')
      :'Waiting for pretrained words (or teach two words, three examples each).';
    $('#motionAccept').disabled=!pending;
  }
  function finish(){
    const active=capture;if(!active)return;
    clearTimeout(active.timer);capture=null;
    $('#motionTeach').disabled=false;$('#motionRecognize').disabled=false;$('#motionLabel').disabled=false;
    $('#motionCancel').disabled=true;
    const sequence=encodeMotion(active.frames,active.imageAspect||1);
    if(!sequence){$('#motionHelp').textContent='Not enough clear hand tracking. Keep your hands in frame and record again.';return;}
    if(active.label){
      const updated=examples.concat({label:active.label,sequence});
      try{localStorage.setItem(key,JSON.stringify(updated));examples=updated;
        $('#motionHelp').textContent=`Saved an example of “${active.label}”. Record it again with a slightly different speed.`;
      }catch{$('#motionHelp').textContent='Could not save this recording. Browser storage may be full.';}
    }else{
      pending=recognizeMotion(sequence,allExamples(),parameters);
      $('#motionHelp').textContent=pending?`Possible match: “${pending.label}”. Check it before adding it to your message.`:'No clear match. Try a supported word again with your hands fully in frame.';
      onStatus(pending?.label||'—');
    }
    render();
  }
  function start(teach){
    if(!isRunning()){$('#motionHelp').textContent='Select Words in motion above the camera, then start the camera.';return;}
    if(capture)return;
    const label=$('#motionLabel').value.trim().replace(/\s+/g,' ').toUpperCase();
    if(teach && !labelOK(label)){$('#motionHelp').textContent='Enter a word or short phrase using letters (up to 30 characters).';return;}
    if(teach && (examples.length>=96 || examples.filter(e=>e.label===label).length>=8)){
      $('#motionHelp').textContent='Library limit reached (8 recordings per word, 96 total). Remove a word to record more.';return;
    }
    const counts={};allExamples().forEach(e=>counts[e.label]=(counts[e.label]||0)+1);
    if(!teach && Object.values(counts).filter(n=>n>=3).length<2){$('#motionHelp').textContent='The word model is not ready. Wait for it to load, or reload the page.';return;}
    pending=null;render();lastSample=-Infinity;
    const now=performance.now();
    capture={label:teach?label:null,start:now+1500,end:now+4000,frames:[],timer:setTimeout(finish,4050)};
    $('#motionTeach').disabled=true;$('#motionRecognize').disabled=true;$('#motionLabel').disabled=true;
    $('#motionCancel').disabled=false;
    $('#motionHelp').textContent='Get ready… recording starts in 1.5 seconds. Perform the sign once over 2.5 seconds.';
  }
  function cancel(){
    if(capture){clearTimeout(capture.timer);capture=null;$('#motionHelp').textContent='Recording canceled. Nothing was saved.';}
    pending=null;$('#motionAccept').disabled=true;
    $('#motionTeach').disabled=false;$('#motionRecognize').disabled=false;$('#motionLabel').disabled=false;$('#motionCancel').disabled=true;
  }
  $('#motionTeach').addEventListener('click',()=>start(true));
  $('#motionRecognize').addEventListener('click',()=>start(false));
  $('#motionCancel').addEventListener('click',cancel);
  $('#motionAccept').addEventListener('click',()=>{
    if(!pending)return;
    const word=pending.label;pending=null;onWord(word);
    if($('#motionAutoSpeak').checked)speak(word);
    $('#motionHelp').textContent=`Added “${word}” to your message.`;render();
  });
  $('#motionRemove').addEventListener('click',()=>{
    if(capture)return;
    const label=$('#motionLabel').value.trim().replace(/\s+/g,' ').toUpperCase();
    const updated=examples.filter(e=>e.label!==label);
    if(updated.length===examples.length){$('#motionHelp').textContent='Enter the name of a recorded word to remove it.';return;}
    try{localStorage.setItem(key,JSON.stringify(updated));examples=updated;pending=null;render();$('#motionHelp').textContent=`Removed “${label}”.`;}
    catch{$('#motionHelp').textContent='Could not update browser storage.';}
  });
  render();
  void loadPretrained();
  return {
    cancel,
    frame(detection,now){
      if(!capture)return;
      if(now<capture.start)return;
      if(now>=capture.end){finish();return;}
      $('#motionHelp').textContent=`Recording… ${((capture.end-now)/1000).toFixed(1)} seconds left`;
      if(now-lastSample>=80){
        const aspect=detection.imageAspect||1;
        if(capture.imageAspect&&Math.abs(capture.imageAspect-aspect)>.01){cancel();$('#motionHelp').textContent='Camera orientation changed. Record the sign again.';return;}
        capture.imageAspect=aspect;capture.frames.push(motionFrame(detection));lastSample=now;
      }
    }
  };
}
