import { createFaceTracker } from './face-tracker.js?v=20261001-auto-cache-1';
import { createMotionStudio } from './motion-studio.js?v=20261001-auto-cache-1';
import { normalizeLandmarks, classifyFeatures, validSample, DEFAULT_PARAMETERS, validParameters, isUsableHand } from './gesture-model.js?v=20261001-auto-cache-1';

const $ = (selector) => document.querySelector(selector);
const video = $('#webcam');
const canvas = $('#overlay');
const ctx = canvas.getContext('2d');
const cameraButton = $('#cameraButton');
const cameraStatus = $('#cameraStatus');
const placeholder = $('#cameraPlaceholder');
const liveResult = $('#liveResult');
const liveLetter = $('#liveLetter');
const liveConfidence = $('#liveConfidence');
const messageText = $('#messageText');
const toast = $('#toast');

const SIGNS = [
  {letter:'A', icon:'✊', name:'A', hint:'Closed fist, thumb rests beside the fingers'},
  {letter:'B', icon:'🖐️', name:'B', hint:'Four fingers up together, thumb across palm'},
  {letter:'I', icon:'🤙', name:'I', hint:'Pinky raised, other fingers closed'},
  {letter:'L', icon:'☝️', name:'L', hint:'Index and thumb form an L shape'},
  {letter:'V', icon:'✌️', name:'V', hint:'Index and middle fingers spread'},
  {letter:'W', icon:'🖖', name:'W', hint:'Index, middle, and ring fingers raised'},
  {letter:'Y', icon:'🤙', name:'Y', hint:'Thumb and pinky extended'},
  {letter:'5', icon:'✋', name:'Five', hint:'All five fingers extended and spread'}
];

$('#signGrid').innerHTML = SIGNS.map(sign => `<article class="sign-card"><div class="sign-visual" aria-hidden="true">${sign.icon}<span>${sign.letter}</span></div><h3>${sign.name}</h3><p>${sign.hint}</p></article>`).join('');
$('#trainingLabel').innerHTML = SIGNS.map(sign=>`<option value="${sign.letter}">${sign.name} — ${sign.hint}</option>`).join('');

const faceTracker=createFaceTracker((state,detail)=>{
  $('#faceTrackingStatus').textContent=state;
  $('#trackingFace').textContent=state.toUpperCase();
  $('#faceRetry').hidden=state!=='Unavailable';
  $('#faceTrackingHelp').textContent=detail||(state==='No face'?'Face the camera with your whole face visible and light in front of you.':'Visible facial movements · not a measure of emotion');
},expression=>{
  $('#faceExpression').textContent=expression;
});
$('#faceTrackingToggle').addEventListener('change',event=>faceTracker.setEnabled(event.target.checked));
$('#faceRetry').addEventListener('click',()=>{void faceTracker.load();});

let recognitionMode = 'letters';
let handLandmarker;
let stream;
let running = false;
let animationId;
let message = '';
let candidate = '';
let candidateSince = 0;
let committed = '';
let missingFrames = 0;
let demoTimer;
let sessionStarted = Date.now();
let detectionLog = [];
let serverAvailable = false;
let trainingActive = false;
let trainingCaptured = 0;
let lastTrainingCapture = 0;
let trainingLabel = '';
let pendingSamples = [];
let lastVideoTime = -1;
let modelParameters = DEFAULT_PARAMETERS;
let aiSamples = loadAISamples();
let baseSamples = [];
let baseModelState = 'Loading pretrained letters…';
const HOLD_MS = 850;

function speakText(text){
  if(!('speechSynthesis' in window)){notify('Speech is unavailable in this browser');return;}
  window.speechSynthesis.cancel();
  const utterance=new SpeechSynthesisUtterance(text);
  $('#pipelineVoice').classList.add('active');
  utterance.onend=utterance.onerror=()=>$('#pipelineVoice').classList.remove('active');
  window.speechSynthesis.speak(utterance);
}

const motionStudio=createMotionStudio({
  isRunning:()=>running && recognitionMode==='words',
  onWord:word=>{message=(message.trimEnd()+' '+word).trimStart();renderMessage();},
  onStatus:(word,detail)=>{liveResult.hidden=word==='—';liveLetter.textContent=word;liveConfidence.textContent=detail||'Review the match in Moving signs';},
  speak:speakText
});
function setRecognitionMode(mode){
  recognitionMode=mode;
  $('#recognitionMode').value=mode;
  $('#captureMode').textContent=recognitionMode==='words'?'WORDS IN MOTION':'STATIC LETTERS';
  $('#pipelineMatch').classList.toggle('active',recognitionMode==='words');
  candidate='';candidateSince=0;committed='';
  if(trainingActive)endTraining();
  motionStudio.cancel();liveResult.hidden=true;
  $('#captureSamplesButton').disabled=recognitionMode==='words';
  $('#demoButton').disabled=recognitionMode==='words';
  clearInterval(demoTimer);
  $('#cameraHelp').textContent=recognitionMode==='words'?'With Automatic words enabled, sign once and pause briefly. Manual recording is also available.':'Hold one supported letter steady.';
}
$('#recognitionMode').addEventListener('change',event=>setRecognitionMode(event.target.value));
$('#wordCaptureButton').addEventListener('click',async()=>{
  $('#wordCaptureButton').disabled=true;
  try{
    if(!running)await startCamera();
    if(!running)return;
    if(recognitionMode!=='words')setRecognitionMode('words');
    motionStudio.recognize();
  }finally{$('#wordCaptureButton').disabled=motionStudio.isRecording();}
});

function loadAISamples(){
  try{
    const saved=JSON.parse(localStorage.getItem('handspeak-ai-samples')||'[]');
    return Array.isArray(saved)?saved.filter(item=>validSample(item,SIGNS.map(sign=>sign.letter))):[];
  }catch{return []}
}

function classifyAI(points){
  return classifyFeatures(normalizeLandmarks(points),baseSamples.concat(aiSamples),modelParameters);
}

async function loadPretrainedModel(){
  try{
    const response=await fetch('./models/asl-knn.json?v=20261001-auto-cache-1');
    if(!response.ok)throw new Error('Pretrained model download failed');
    const model=await response.json();
    const labels=SIGNS.map(sign=>sign.letter);
    if(model.version!==2 || !validParameters(model.parameters) || model.normalization!=='wrist-palm-rotation-v1'
      || !Array.isArray(model.samples) || !model.samples.length
      || !model.samples.every(sample=>validSample(sample,labels)))throw new Error('Invalid pretrained model');
    baseSamples=model.samples;
    modelParameters=model.parameters;
    baseModelState=`${new Set(baseSamples.map(sample=>sample.label)).size} pretrained letters · ${baseSamples.length} reference samples`;
  }catch(error){
    console.warn(error);
    baseModelState='Pretrained letters unavailable · reload or teach at least two signs';
  }
  renderAIStatus();
}

function endTraining(){
  trainingActive=false;pendingSamples=[];
  $('#trainingLabel').disabled=false;
  $('#captureSamplesButton').disabled=false;
  $('#captureSamplesButton').textContent='Capture 30 samples';
}

function captureTrainingSample(points,now){
  if(!trainingActive||now-lastTrainingCapture<150||!isUsableHand(points))return;
  lastTrainingCapture=now;
  pendingSamples.push({label:trainingLabel,features:normalizeLandmarks(points)});
  trainingCaptured=pendingSamples.length;
  $('#trainingProgress').style.width=`${trainingCaptured/30*100}%`;
  $('#trainingHelp').textContent=`Captured ${trainingCaptured} of 30 samples. Slowly vary the hand angle.`;
  if(trainingCaptured>=30){
    const updated=aiSamples.concat(pendingSamples);
    try{
      localStorage.setItem('handspeak-ai-samples',JSON.stringify(updated));
      aiSamples=updated;
      $('#trainingHelp').textContent='Examples saved. Try the sign with a slightly different hand position.';
      notify(`${trainingLabel} training complete`);
    }catch{
      $('#trainingHelp').textContent='Could not save examples. Free browser storage and try again.';
    }
    endTraining();renderAIStatus();
  }
}

function renderAIStatus(){
  const counts=Object.fromEntries(SIGNS.map(sign=>[sign.letter,baseSamples.concat(aiSamples).filter(sample=>sample.label===sign.letter).length]));
  $('#aiModelStatus').textContent=`${baseModelState} · ${aiSamples.length} personal samples`;
  $('#sampleCounts').innerHTML=SIGNS.map(sign=>`<span><b>${sign.letter}</b> ${counts[sign.letter]}</span>`).join('');
}

function notify(text){
  toast.textContent = text;
  toast.classList.add('show');
  clearTimeout(notify.timer);
  notify.timer = setTimeout(() => toast.classList.remove('show'), 2200);
}

function renderMessage(){
  messageText.innerHTML = message ? '' : '<span>Recognized words will appear here…</span>';
  if(message) messageText.textContent = message;
  $('#captureTranscript').textContent=message||'Your words will appear here.';
  $('#pipelineReview').classList.toggle('active',Boolean(message));
}

function appendCharacter(char){
  message += char;
  renderMessage();
}

function setLive(letter, confidence = 0){
  liveResult.hidden = false;
  liveLetter.textContent = letter || '—';
  liveConfidence.textContent = letter?`${Math.round(confidence * 100)}% match agreement`:'Uncertain — adjust your hand and hold steady';
}

async function loadRecognizer(){
  if(handLandmarker){void faceTracker.load();return;}
  cameraButton.disabled = true;
  cameraButton.textContent = 'Loading recognizer…';
  try{
    const vision = await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/+esm');
    const fileset = await vision.FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/wasm');
    const options={
      baseOptions:{modelAssetPath:'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task', delegate:'GPU'},
      runningMode:'VIDEO', numHands:2, minHandDetectionConfidence:.65, minHandPresenceConfidence:.65, minTrackingConfidence:.6
    };
    try{handLandmarker=await vision.HandLandmarker.createFromOptions(fileset,options);}
    catch{options.baseOptions.delegate='CPU';handLandmarker=await vision.HandLandmarker.createFromOptions(fileset,options);}
    void faceTracker.load(vision,fileset);
  }catch(error){
    console.error(error);
    throw new Error('The recognition model could not be loaded. Check your internet connection.');
  }finally{
    cameraButton.disabled = false;
    cameraButton.innerHTML = '<span aria-hidden="true">◉</span> Start camera';
  }
}

async function startCamera(){
  clearInterval(demoTimer);
  try{
    if(!navigator.mediaDevices?.getUserMedia) throw new Error('Camera access is not supported by this browser.');
    await loadRecognizer();
    stream = await navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:{ideal:960},height:{ideal:720}},audio:false});
    video.srcObject = stream;
    await video.play();
    running = true;
    $('#trackingState').textContent='LIVE';$('#captureFeed').textContent='LIVE';
    $('#pipelineTrack').classList.add('active');
    placeholder.hidden = true;
    cameraStatus.classList.add('live');
    cameraStatus.innerHTML = '<i></i> Live';
    cameraButton.innerHTML = '<span aria-hidden="true">■</span> Stop camera';
    $('#cameraHelp').textContent = recognitionMode==='words'?'With Automatic words enabled, sign once and pause briefly. Manual recording is also available.':'Hold a supported sign steady until it is added.';
    detect();
  }catch(error){
    stopCamera();
    notify(error.message || 'Camera permission was not granted.');
    $('#cameraHelp').textContent = 'Camera unavailable. You can still use Try demo.';
  }
}

function stopCamera(){
  running = false;
  faceTracker.reset();
  $('#trackingState').textContent='STANDBY';$('#trackingHands').textContent='0 / 2';$('#captureFeed').textContent='OFFLINE';
  $('#pipelineTrack').classList.remove('active');
  motionStudio.cancel();
  candidate='';candidateSince=0;committed='';lastVideoTime=-1;
  if(trainingActive){endTraining();$('#trainingHelp').textContent='Capture stopped. Start the camera to try again.';}
  cancelAnimationFrame(animationId);
  stream?.getTracks().forEach(track => track.stop());
  stream = null;
  video.srcObject = null;
  ctx.clearRect(0,0,canvas.width,canvas.height);
  placeholder.hidden = false;
  liveResult.hidden = true;
  cameraStatus.classList.remove('live');
  cameraStatus.innerHTML = '<i></i> Camera off';
  cameraButton.innerHTML = '<span aria-hidden="true">◉</span> Start camera';
}

function drawHand(points){
  const links=[[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[5,9],[9,10],[10,11],[11,12],[9,13],[13,14],[14,15],[15,16],[13,17],[17,18],[18,19],[19,20],[0,17]];
  ctx.strokeStyle='#7fe0ca';ctx.lineWidth=3;ctx.lineCap='round';
  links.forEach(([a,b])=>{ctx.beginPath();ctx.moveTo(points[a].x*canvas.width,points[a].y*canvas.height);ctx.lineTo(points[b].x*canvas.width,points[b].y*canvas.height);ctx.stroke()});
  ctx.fillStyle='#fff';points.forEach(p=>{ctx.beginPath();ctx.arc(p.x*canvas.width,p.y*canvas.height,4,0,Math.PI*2);ctx.fill()});
}

function stabilize(result, now){
  if(!result.letter){candidate='';candidateSince=0;return}
  if(result.letter!==candidate){candidate=result.letter;candidateSince=now;return}
  if(now-candidateSince>=HOLD_MS && committed!==candidate){
    appendCharacter(candidate);
    detectionLog.push({symbol:candidate,confidence:result.confidence,latencyMs:Math.round(now-candidateSince)});
    committed=candidate;notify(`${candidate} added`)
  }
}

function detect(){
  if(!running) return;
  if(video.readyState>=2 && video.currentTime!==lastVideoTime){
    lastVideoTime=video.currentTime;
    canvas.width=video.videoWidth;canvas.height=video.videoHeight;
    const now=performance.now();
    let detection={landmarks:[]};
    if(handLandmarker){
      try{detection=handLandmarker.detectForVideo(video,now);}
      catch(error){
        console.warn('Hand tracking stopped',error);
        try{handLandmarker.close?.();}catch{}
        handLandmarker=null;
        $('#cameraHelp').textContent='Hand tracking stopped. Restart the camera to retry; face tracking can continue.';
      }
    }
    ctx.clearRect(0,0,canvas.width,canvas.height);
    faceTracker.draw(video,now,ctx,canvas.width,canvas.height,motionStudio.isCapturing());
    const hands=(detection.landmarks||[]).filter(isUsableHand);
    hands.forEach(drawHand);
    $('#trackingHands').textContent=`${hands.length} / 2`;
    if(recognitionMode==='words'){
      // Keep original handedness indices when rejecting clipped/small hands.
      const indices=(detection.landmarks||[]).map((p,i)=>isUsableHand(p)?i:-1).filter(i=>i>=0);
      motionStudio.frame({landmarks:indices.map(i=>detection.landmarks[i]),handedness:indices.map(i=>detection.handedness?.[i]),imageAspect:video.videoHeight/video.videoWidth},now);
    }else if(hands.length===1){
      missingFrames=0;
      const points=hands[0];
      const wasTraining=trainingActive;
      captureTrainingSample(points,now);
      const result=classifyAI(points)||{letter:'',confidence:0};
      setLive(result.letter,result.confidence);
      if(!wasTraining)stabilize(result,now);
      else {candidate='';candidateSince=0;}
    }else{
      liveResult.hidden=true;
      candidate='';candidateSince=0;
      if(++missingFrames>8) committed='';
      if(hands.length>1)$('#cameraHelp').textContent='Use one hand for static letters, or switch to Words in motion.';
    }
  }
  animationId=requestAnimationFrame(detect);
}

$('#pipelineVoice').addEventListener('click',()=>{if(message)speakText(message);else notify('Add a message first');});

cameraButton.addEventListener('click',()=>running?stopCamera():startCamera());
$('#clearButton').addEventListener('click',()=>{message='';renderMessage();notify('Message cleared')});
$('#spaceButton').addEventListener('click',()=>appendCharacter(' '));
$('#backspaceButton').addEventListener('click',()=>{message=message.slice(0,-1);renderMessage()});
$('#copyButton').addEventListener('click',async()=>{if(!message)return notify('There is no message to copy');try{await navigator.clipboard.writeText(message);notify('Message copied')}catch{notify('Copy is unavailable in this browser')}});
$('#speakButton').addEventListener('click',()=>{if(!message)return notify('Add a message first');speakText(message)});
$('#contrastButton').addEventListener('click',()=>{document.body.classList.toggle('high-contrast');localStorage.setItem('handspeak-contrast',document.body.classList.contains('high-contrast'))});
if(localStorage.getItem('handspeak-contrast')==='true')document.body.classList.add('high-contrast');

$('#demoButton').addEventListener('click',()=>{
  if(running) stopCamera();
  clearInterval(demoTimer);
  const demo=['I','L','Y'];let index=0;
  placeholder.hidden=true;liveResult.hidden=false;cameraStatus.classList.add('live');cameraStatus.innerHTML='<i></i> Demo';
  $('#captureFeed').textContent='DEMO';$('#trackingState').textContent='DEMO';
  const tick=()=>{if(index>=demo.length){clearInterval(demoTimer);notify('Demo complete');return}const letter=demo[index++];setLive(letter,.94);appendCharacter(letter)};
  tick();demoTimer=setInterval(tick,700);
});

window.addEventListener('beforeunload',stopCamera);

async function api(path, options){
  const response = await fetch(path, options);
  const data = await response.json();
  if(!response.ok) throw new Error(data.error || 'Request failed');
  return data;
}

async function saveSession(){
  if(!message.trim()) return notify('There is no message to save');
  try{
    await api('/api/sessions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,detections:detectionLog,durationMs:Date.now()-sessionStarted})});
    notify('Translation saved');
    detectionLog=[];sessionStarted=Date.now();
    await loadSystemData();
  }catch(error){notify(serverAvailable?error.message:'Run server.py to enable saving')}
}

function renderHistory(sessions){
  const list=$('#historyList');list.innerHTML='';
  if(!sessions.length){list.innerHTML='<p class="empty-state">No saved sessions yet.</p>';return}
  sessions.forEach(session=>{
    const item=document.createElement('article');item.className='history-item';
    const text=document.createElement('strong');text.textContent=session.message;
    const date=document.createElement('time');date.dateTime=session.created_at;date.textContent=new Date(session.created_at).toLocaleString();
    const meta=document.createElement('small');meta.textContent=`${session.character_count} characters · ${(session.duration_ms/1000).toFixed(1)} seconds`;
    item.append(text,date,meta);list.append(item);
  });
}

function renderMetrics(metrics){
  $('#metricSessions').textContent=metrics.sessions;
  $('#metricDetections').textContent=metrics.detections;
  $('#metricConfidence').textContent=`${Math.round(metrics.averageConfidence*100)}%`;
  $('#metricLatency').textContent=`${metrics.averageLatencyMs} ms`;
  $('#evaluationCount').textContent=metrics.evaluations;
  const hasRatings=metrics.evaluations>0;
  $('#ratingAccuracy').textContent=hasRatings?`${metrics.ratings.accuracy}/5`:'—';
  $('#ratingUsability').textContent=hasRatings?`${metrics.ratings.usability}/5`:'—';
  $('#ratingPerformance').textContent=hasRatings?`${metrics.ratings.performance}/5`:'—';
}

async function loadSystemData(){
  try{
    const [health,sessions,metrics,gestures]=await Promise.all([api('/api/health'),api('/api/sessions?limit=20'),api('/api/metrics'),api('/api/gestures')]);
    serverAvailable=health.status==='ok';renderHistory(sessions.sessions);renderMetrics(metrics);
    if(gestures.gestures.length!==SIGNS.length) console.warn('Gesture database and client classifier differ.');
  }catch{serverAvailable=false}
}

$('#saveButton').addEventListener('click',saveSession);
$('#refreshHistory').addEventListener('click',async()=>{await loadSystemData();notify(serverAvailable?'History refreshed':'Server is unavailable')});
['accuracy','usability','performance'].forEach(name=>{$(`#${name}`).addEventListener('input',event=>$(`#${name}Value`).textContent=event.target.value)});
$('#evaluationForm').addEventListener('submit',async event=>{
  event.preventDefault();
  const form=new FormData(event.currentTarget);
  const payload=Object.fromEntries(form.entries());
  try{
    await api('/api/evaluations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    event.currentTarget.reset();['accuracy','usability','performance'].forEach(name=>$(`#${name}Value`).textContent='5');
    notify('Thank you—evaluation submitted');await loadSystemData();
  }catch(error){notify(serverAvailable?error.message:'Run server.py to submit evaluations')}
});

loadSystemData();
renderAIStatus();
loadPretrainedModel();

$('#captureSamplesButton').addEventListener('click',()=>{
  if(!running)return notify('Start the camera before training');
  if(recognitionMode!=='letters')return notify('Switch to Static letters to capture letter samples');
  trainingActive=true;trainingCaptured=0;lastTrainingCapture=0;
  trainingLabel=$('#trainingLabel').value;pendingSamples=[];
  $('#trainingLabel').disabled=true;
  candidate='';candidateSince=0;
  $('#trainingProgress').style.width='0';
  $('#captureSamplesButton').disabled=true;$('#captureSamplesButton').textContent='Capturing…';
  $('#trainingHelp').textContent='Hold the selected gesture steady and slowly vary its angle.';
});

$('#resetModelButton').addEventListener('click',()=>{
  aiSamples=[];endTraining();localStorage.removeItem('handspeak-ai-samples');
  $('#trainingProgress').style.width='0';$('#captureSamplesButton').disabled=false;$('#captureSamplesButton').textContent='Capture 30 samples';
  $('#trainingHelp').textContent='Personal examples cleared. Pretrained letters remain available.';
  renderAIStatus();notify('Personalized AI model reset');
});
