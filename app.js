import { normalizeLandmarks, classifyFeatures, validSample } from './gesture-model.js';

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
let aiSamples = loadAISamples();
let baseSamples = [];
let baseModelState = 'Loading pretrained letters…';
const HOLD_MS = 850;

function loadAISamples(){
  try{
    const saved=JSON.parse(localStorage.getItem('handspeak-ai-samples')||'[]');
    return Array.isArray(saved)?saved.filter(item=>validSample(item,SIGNS.map(sign=>sign.letter))):[];
  }catch{return []}
}

function classifyAI(points){
  return classifyFeatures(normalizeLandmarks(points),baseSamples.concat(aiSamples));
}

async function loadPretrainedModel(){
  try{
    const response=await fetch('./models/asl-knn.json');
    if(!response.ok)throw new Error('Pretrained model download failed');
    const model=await response.json();
    const labels=SIGNS.map(sign=>sign.letter);
    if(model.version!==1 || model.normalization!=='wrist-palm-rotation-v1'
      || !Array.isArray(model.samples) || !model.samples.length
      || !model.samples.every(sample=>validSample(sample,labels)))throw new Error('Invalid pretrained model');
    baseSamples=model.samples;
    baseModelState=`${new Set(baseSamples.map(sample=>sample.label)).size} pretrained letters · ${baseSamples.length} reference samples`;
  }catch(error){
    console.warn(error);
    baseModelState='Pretrained letters unavailable · using gesture rules and personal samples';
  }
  renderAIStatus();
}

function captureTrainingSample(points,now){
  if(!trainingActive||now-lastTrainingCapture<80)return;
  lastTrainingCapture=now;
  aiSamples.push({label:$('#trainingLabel').value,features:normalizeLandmarks(points)});
  trainingCaptured++;
  $('#trainingProgress').style.width=`${trainingCaptured/30*100}%`;
  $('#trainingHelp').textContent=`Captured ${trainingCaptured} of 30 samples. Slowly vary the hand angle.`;
  if(trainingCaptured>=30){
    trainingActive=false;localStorage.setItem('handspeak-ai-samples',JSON.stringify(aiSamples));
    $('#captureSamplesButton').disabled=false;$('#captureSamplesButton').textContent='Capture 30 samples';
    $('#trainingHelp').textContent='Personal examples saved on this device and added to the recognizer.';
    renderAIStatus();notify(`${$('#trainingLabel').value} training complete`);
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
}

function appendCharacter(char){
  message += char;
  renderMessage();
}

function setLive(letter, confidence = 0){
  liveResult.hidden = false;
  liveLetter.textContent = letter || '—';
  liveConfidence.textContent = `${Math.round(confidence * 100)}% confidence`;
}

async function loadRecognizer(){
  if(handLandmarker) return;
  cameraButton.disabled = true;
  cameraButton.textContent = 'Loading recognizer…';
  try{
    const vision = await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/+esm');
    const fileset = await vision.FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/wasm');
    handLandmarker = await vision.HandLandmarker.createFromOptions(fileset, {
      baseOptions:{modelAssetPath:'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task', delegate:'GPU'},
      runningMode:'VIDEO', numHands:1, minHandDetectionConfidence:.65, minHandPresenceConfidence:.65, minTrackingConfidence:.6
    });
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
    placeholder.hidden = true;
    cameraStatus.classList.add('live');
    cameraStatus.innerHTML = '<i></i> Live';
    cameraButton.innerHTML = '<span aria-hidden="true">■</span> Stop camera';
    $('#cameraHelp').textContent = 'Hold a supported sign steady until it is added.';
    detect();
  }catch(error){
    notify(error.message || 'Camera permission was not granted.');
    $('#cameraHelp').textContent = 'Camera unavailable. You can still use Try demo.';
  }
}

function stopCamera(){
  running = false;
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

function isExtended(points, tip, pip){
  const wrist = points[0];
  const tipDistance = Math.hypot(points[tip].x-wrist.x, points[tip].y-wrist.y);
  const pipDistance = Math.hypot(points[pip].x-wrist.x, points[pip].y-wrist.y);
  return tipDistance > pipDistance * 1.13;
}

function classify(points){
  const index = isExtended(points,8,6), middle = isExtended(points,12,10), ring = isExtended(points,16,14), pinky = isExtended(points,20,18);
  const palmWidth = Math.hypot(points[5].x-points[17].x,points[5].y-points[17].y);
  const thumbDistance = Math.hypot(points[4].x-points[5].x,points[4].y-points[5].y);
  const thumb = thumbDistance > palmWidth * .62;
  const spreadIM = Math.hypot(points[8].x-points[12].x,points[8].y-points[12].y) > palmWidth * .42;
  const spreadMR = Math.hypot(points[12].x-points[16].x,points[12].y-points[16].y) > palmWidth * .32;
  const count = [index,middle,ring,pinky].filter(Boolean).length;
  if(!count && !thumb) return {letter:'A',confidence:.86};
  if(!count && thumb) return {letter:'A',confidence:.72};
  if(!index && !middle && !ring && pinky && thumb) return {letter:'Y',confidence:.91};
  if(!index && !middle && !ring && pinky) return {letter:'I',confidence:.9};
  if(index && !middle && !ring && !pinky && thumb) return {letter:'L',confidence:.92};
  if(index && middle && !ring && !pinky && spreadIM) return {letter:'V',confidence:.91};
  if(index && middle && ring && !pinky && (spreadIM || spreadMR)) return {letter:'W',confidence:.88};
  if(count===4 && thumb) return {letter:'5',confidence:.9};
  if(count===4 && !thumb) return {letter:'B',confidence:.88};
  return {letter:'',confidence:.35};
}

function drawHand(points){
  const links=[[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[5,9],[9,10],[10,11],[11,12],[9,13],[13,14],[14,15],[15,16],[13,17],[17,18],[18,19],[19,20],[0,17]];
  ctx.clearRect(0,0,canvas.width,canvas.height);
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
  if(video.readyState>=2){
    canvas.width=video.videoWidth;canvas.height=video.videoHeight;
    const now=performance.now();
    const detection=handLandmarker.detectForVideo(video,now);
    if(detection.landmarks?.length){
      missingFrames=0;
      const points=detection.landmarks[0];
      drawHand(points);
      captureTrainingSample(points,now);
      const ruleResult=classify(points);
      // The alphabet dataset has no digit 5. Preserve that rule until the user teaches it.
      const useFiveRule=ruleResult.letter==='5' && aiSamples.filter(sample=>sample.label==='5').length<10;
      const result=useFiveRule?ruleResult:(classifyAI(points)||ruleResult);
      setLive(result.letter,result.confidence);
      stabilize(result,now);
    }else{
      ctx.clearRect(0,0,canvas.width,canvas.height);
      liveResult.hidden=true;
      candidate='';candidateSince=0;
      if(++missingFrames>8) committed='';
    }
  }
  animationId=requestAnimationFrame(detect);
}

cameraButton.addEventListener('click',()=>running?stopCamera():startCamera());
$('#clearButton').addEventListener('click',()=>{message='';renderMessage();notify('Message cleared')});
$('#spaceButton').addEventListener('click',()=>appendCharacter(' '));
$('#backspaceButton').addEventListener('click',()=>{message=message.slice(0,-1);renderMessage()});
$('#copyButton').addEventListener('click',async()=>{if(!message)return notify('There is no message to copy');try{await navigator.clipboard.writeText(message);notify('Message copied')}catch{notify('Copy is unavailable in this browser')}});
$('#speakButton').addEventListener('click',()=>{if(!message)return notify('Add a message first');speechSynthesis.cancel();speechSynthesis.speak(new SpeechSynthesisUtterance(message))});
$('#contrastButton').addEventListener('click',()=>{document.body.classList.toggle('high-contrast');localStorage.setItem('handspeak-contrast',document.body.classList.contains('high-contrast'))});
if(localStorage.getItem('handspeak-contrast')==='true')document.body.classList.add('high-contrast');

$('#demoButton').addEventListener('click',()=>{
  if(running) stopCamera();
  clearInterval(demoTimer);
  const demo=['I','L','Y'];let index=0;
  placeholder.hidden=true;liveResult.hidden=false;cameraStatus.classList.add('live');cameraStatus.innerHTML='<i></i> Demo';
  $('#cameraStage').style.background='linear-gradient(135deg,#cce7df,#edf5ef)';
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
  trainingActive=true;trainingCaptured=0;lastTrainingCapture=0;
  $('#trainingProgress').style.width='0';
  $('#captureSamplesButton').disabled=true;$('#captureSamplesButton').textContent='Capturing…';
  $('#trainingHelp').textContent='Hold the selected gesture steady and slowly vary its angle.';
});

$('#resetModelButton').addEventListener('click',()=>{
  aiSamples=[];trainingActive=false;localStorage.removeItem('handspeak-ai-samples');
  $('#trainingProgress').style.width='0';$('#captureSamplesButton').disabled=false;$('#captureSamplesButton').textContent='Capture 30 samples';
  $('#trainingHelp').textContent='Personal examples cleared. Pretrained letters remain available.';
  renderAIStatus();notify('Personalized AI model reset');
});
