import {createAutomaticMotion} from './automatic-motion.js?v=20261001-auto-cache-1';
import {motionFrame,encodeMotion,validMotion,recognizeMotion,validMotionParameters} from './motion-model.js?v=20261001-auto-cache-1';

export function createMotionStudio({isRunning,onWord,onStatus,speak}){
  const $=s=>document.querySelector(s), key='handspeak-motion-v3';
  let examples=[],baseExamples=[],parameters,baseState='Loading pretrained words…',capture=null,pending=null,lastSample=-Infinity,legacyExamples=false;
  const automatic=createAutomaticMotion();
  let autoWasActive=false;
  const allExamples=()=>baseExamples.concat(examples);
  function setHelp(message){$('#motionHelp').textContent=message;$('#motionCaptureStatus').textContent=message;}
  const labelOK=label=>typeof label==='string'&&/^[a-zA-Z][a-zA-Z '-]{0,29}$/.test(label);
  try{
    const saved=JSON.parse(localStorage.getItem(key)||'[]');
    if(Array.isArray(saved))examples=saved.slice(0,96).filter(e=>labelOK(e.label)&&validMotion(e.sequence));
    const legacy=JSON.parse(localStorage.getItem('handspeak-motion-v2')||localStorage.getItem('handspeak-motion-v1')||'[]');
    legacyExamples=Array.isArray(legacy)&&legacy.length>0;
  }catch{}
  async function loadPretrained(){
    try{
      const response=await fetch('./models/asl-words.json?v=20261001-auto-cache-1');
      if(!response.ok)throw new Error('Word model download failed');
      const model=await response.json();
      if(model.version!==1||model.encoding!=='two-hand-motion-v3'||!validMotionParameters(model.parameters)
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
  function finish(force=false){
    const active=capture;if(!active)return;
    clearTimeout(active.timer);
    // Give slow streams a bounded chance to reach the existing sample minimum.
    if(!force&&active.frames.length<12&&performance.now()<active.deadline){
      setHelp(`Camera is slow — collecting more frames (${active.frames.length}/12). Keep your hands in view.`);
      active.timer=setTimeout(()=>finish(true),Math.max(0,active.deadline-performance.now()));
      return;
    }
    capture=null;
    $('#motionTeach').disabled=false;$('#motionRecognize').disabled=false;$('#motionLabel').disabled=false;
    $('#motionCancel').disabled=true;$('#wordCaptureButton').disabled=false;
    const tracked=active.frames.filter(frame=>frame.some(Boolean)).length;
    if(active.frames.length<12){onStatus('Not enough frames','The recording was too slow. See the details below the camera.');setHelp(`Not enough camera frames: ${active.frames.length}/12 minimum. Try again with fewer apps open or a faster device.`);return;}
    const sequence=encodeMotion(active.frames,active.imageAspect||1);
    if(!sequence){onStatus('Hands not tracked','Keep both hands fully visible. See the details below the camera.');setHelp(`Not enough clear hand tracking: hands visible in ${tracked}/${active.frames.length} frames. Keep your hands fully in view and use front lighting.`);return;}
    if(active.label){
      const updated=examples.concat({label:active.label,sequence});
      try{localStorage.setItem(key,JSON.stringify(updated));examples=updated;
        setHelp(`Saved an example of “${active.label}”. Record it again with a slightly different speed.`);
      }catch{setHelp('Could not save this recording. Browser storage may be full.');}
    }else{
      pending=recognizeMotion(sequence,allExamples(),parameters);
      setHelp(pending?`Possible match: “${pending.label}”. Check it before adding it to your message.`:`Captured ${active.frames.length} frames, but the model found no clear match. This experimental model may not recognize your signing reliably.`);
      onStatus(pending?.label||'No match',pending?'Possible match — review it in Moving signs':'The model did not recognize this recording. Your sign may still be correct.');
    }
    render();
  }
  function start(teach){
    if(!isRunning()){setHelp('Select Words in motion above the camera, then start the camera.');return;}
    if(capture)return;
    const label=$('#motionLabel').value.trim().replace(/\s+/g,' ').toUpperCase();
    if(teach && !labelOK(label)){setHelp('Enter a word or short phrase using letters (up to 30 characters).');return;}
    if(teach && (examples.length>=96 || examples.filter(e=>e.label===label).length>=8)){
      setHelp('Library limit reached (8 recordings per word, 96 total). Remove a word to record more.');return;
    }
    const counts={};allExamples().forEach(e=>counts[e.label]=(counts[e.label]||0)+1);
    if(!teach && Object.values(counts).filter(n=>n>=3).length<2){setHelp('The word model is not ready. Wait for it to load, or reload the page.');return;}
    automatic.reset();autoWasActive=false;
    pending=null;render();onStatus('—');lastSample=-Infinity;
    const now=performance.now();
    capture={label:teach?label:null,start:now+1500,end:now+4000,deadline:now+6000,frames:[],timer:setTimeout(()=>finish(),4050)};
    $('#motionTeach').disabled=true;$('#motionRecognize').disabled=true;$('#motionLabel').disabled=true;
    $('#motionCancel').disabled=false;$('#wordCaptureButton').disabled=true;
    setHelp('Get ready… recording starts in 1.5 seconds. Perform the sign once over 2.5 seconds.');
  }
  function cancel(){
    automatic.reset();autoWasActive=false;
    if(capture){clearTimeout(capture.timer);capture=null;setHelp('Recording canceled. Nothing was saved.');}
    pending=null;$('#motionAccept').disabled=true;
    $('#motionTeach').disabled=false;$('#motionRecognize').disabled=false;$('#motionLabel').disabled=false;$('#motionCancel').disabled=true;$('#wordCaptureButton').disabled=false;
  }
  $('#automaticWords').addEventListener('change',()=>{
    cancel();onStatus('—');
    setHelp($('#automaticWords').checked?'Automatic words enabled. Sign once, then pause briefly.':'Automatic words off. Select Record a word to capture a sign.');
  });
  function automaticFrame(detection,now){
    if(!$('#automaticWords').checked||!isRunning()||!baseExamples.length)return;
    const clip=automatic.push(motionFrame(detection),now,detection.imageAspect||1);
    const active=automatic.isActive();
    if(active&&!autoWasActive){pending=null;render();onStatus('—');setHelp('Watching your sign… pause briefly when finished.');}
    autoWasActive=active;
    if(!clip)return;
    const sequence=encodeMotion(clip.frames,clip.imageAspect);
    pending=sequence?recognizeMotion(sequence,allExamples(),parameters):null;
    const detail=pending?'Possible match — review it in Moving signs':'No clear match. Pause, then try another sign.';
    onStatus(pending?.label||(clip.frames.length<12?'Not enough frames':'No match'),detail);
    setHelp(pending?`Possible match: “${pending.label}”. Pause before your next sign. Review it before adding it.`:detail);
    render();
  }
  $('#motionTeach').addEventListener('click',()=>start(true));
  $('#motionRecognize').addEventListener('click',()=>start(false));
  $('#motionCancel').addEventListener('click',cancel);
  $('#motionAccept').addEventListener('click',()=>{
    if(!pending)return;
    const word=pending.label;pending=null;onWord(word);
    if($('#motionAutoSpeak').checked)speak(word);
    setHelp(`Added “${word}” to your message.`);render();
  });
  $('#motionRemove').addEventListener('click',()=>{
    if(capture)return;
    const label=$('#motionLabel').value.trim().replace(/\s+/g,' ').toUpperCase();
    const updated=examples.filter(e=>e.label!==label);
    if(updated.length===examples.length){setHelp('Enter the name of a recorded word to remove it.');return;}
    try{localStorage.setItem(key,JSON.stringify(updated));examples=updated;pending=null;render();setHelp(`Removed “${label}”.`);}
    catch{setHelp('Could not update browser storage.');}
  });
  render();
  void loadPretrained();
  return {
    cancel,
    isCapturing:()=>Boolean(capture)||automatic.isActive(),
    isRecording:()=>Boolean(capture),
    recognize:()=>start(false),
    frame(detection,now){
      if(!capture){automaticFrame(detection,now);return;}
      if(now<capture.start){setHelp(`Get ready… ${Math.ceil((capture.start-now)/1000)}. Keep your hands in view.`);return;}
      if(now>=capture.deadline){finish(true);return;}
      if(now>=capture.end&&capture.frames.length>=12){finish(true);return;}
      setHelp(now>=capture.end?`Camera is slow — collecting more frames (${capture.frames.length}/12). Keep your hands in view.`:`Recording… ${((capture.end-now)/1000).toFixed(1)} seconds left`);
      if(now-lastSample>=80){
        const aspect=detection.imageAspect||1;
        if(capture.imageAspect&&Math.abs(capture.imageAspect-aspect)>.01){cancel();setHelp('Camera orientation changed. Record the sign again.');return;}
        capture.imageAspect=aspect;capture.frames.push(motionFrame(detection));lastSample=now;
        if(now>=capture.end&&capture.frames.length>=12)finish(true);
      }
    }
  };
}
