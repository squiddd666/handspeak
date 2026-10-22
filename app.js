import {createExperienceUI} from './experience-ui.js?v=20261020-simple-view-1';
import {loadVocabularySettings} from './vocabulary-settings.js?v=20261011-features-1';
import {createTemporalCamera} from './temporal-camera.js?v=20261020-tracking-1';
import {preferredVisionDelegate} from './camera-performance.js?v=20261010-single-1';
import {createResearchWords} from './research-words.js?v=20261020-short-runs-1';
import {createVocabularyLibrary} from './vocabulary-library.js?v=20261022-nomodel-1';
import {createInterpreter} from './interpretation.js?v=20261011-features-1';
import {appendWord,finishSentence,removeLastWord} from './sentence-builder.js?v=20261002-sentences-1';
import { createFaceTracker } from './face-tracker.js?v=20261010-single-1';
import { createMotionStudio } from './motion-studio.js?v=20261022-category-manual-1';
import {createCapstoneRecognition} from './capstone-recognition.js?v=20261021-stgcn-1';
import {createBeginnerRecognition} from './beginner-recognition.js?v=20261023-beginner-1';
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
let vocabularyLibrary;
function setWordCameraResult(word,detail,daily=false){
  liveResult.hidden=word==='—';liveLetter.textContent=word;
  liveConfidence.textContent=detail||'Possible match — verify before adding';
  vocabularyLibrary?.showCameraAccuracy(word,{daily,personal:!daily&&motionStudio.hasPersonalWord(word)});
  document.dispatchEvent(new CustomEvent('handspeak:camera-match',{detail:{word,model:$('#activeVocabulary').textContent}}));
}
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

$('#signGrid').innerHTML = SIGNS.map(sign => `<article class="sign-card"><div class="sign-visual" aria-hidden="true">${sign.letter}</div><h3>${sign.name}</h3><small>${sign.letter==='5'?'Personal · teach first':'Supported & tested'}</small><p>${sign.hint}</p><a target="_blank" rel="noopener noreferrer" href="https://www.lifeprint.com/asl101/fingerspelling/abc.htm">View ASL alphabet reference</a></article>`).join('');
$('#trainingLabel').innerHTML = SIGNS.map(sign=>`<option value="${sign.letter}">${sign.name} — ${sign.hint}</option>`).join('');

const faceTracker=createFaceTracker((state,detail)=>{
  $('#faceTrackingStatus').textContent=state;
  $('#trackingFace').textContent=state.toUpperCase();
  $('#faceRetry').hidden=state!=='Unavailable';
  $('#faceTrackingHelp').textContent=detail||(state==='No face'?'Face the camera with your whole face visible and light in front of you.':'Visible facial movements · not a measure of emotion');
},expression=>{
  $('#faceExpression').textContent=expression;
},{preferredDelegate:preferredVisionDelegate()});
$('#faceTrackingToggle').addEventListener('change',event=>faceTracker.setEnabled(event.target.checked));
$('#faceRetry').addEventListener('click',()=>{void prepareFaceTracker();});

let recognitionMode = 'letters';
const cameraDiagnostic={lastCapture:null,times:[],lastRender:0,rawHands:0,usableHands:0};
function renderCameraDiagnostic(){
 const times=cameraDiagnostic.times,span=times.length>1?times[times.length-1]-times[0]:0;
 $('#cameraDiagnostics').textContent=JSON.stringify({build:'20261020-motion-fixes-1',trackerState:cameraDiagnostic.trackerState||'idle',trackerError:cameraDiagnostic.trackerError||null,delegate:handDelegate,processingLagMs:Math.round(temporalLagMs),input:video.videoWidth+'x'+video.videoHeight,processedFps:span?Math.round((times.length-1)*10000/span)/10:0,rawHands:cameraDiagnostic.rawHands,usableHands:cameraDiagnostic.usableHands,mode:recognitionMode,vocabulary:$('#activeVocabulary').textContent,model:$('#motionModelStatus').textContent,extraWords:$('#expandedWords').checked,serverPreview:$('#researchWordsToggle').checked,automaticWords:$('#automaticWords').checked,faceTracking:$('#faceTrackingToggle').checked,lastCapture:cameraDiagnostic.lastCapture},null,2);
}
$('#copyCameraDiagnostics').addEventListener('click',async()=>{renderCameraDiagnostic();try{await navigator.clipboard.writeText($('#cameraDiagnostics').textContent);notify('Diagnostics copied. Paste them into this chat.');}catch{notify('Select and copy the text in Camera diagnostics.');}});
let handVision,handFiles,handRecovery=null;
let handLandmarker,handDelegate='',temporalCamera=null,temporalHands=[],temporalFrameAt=-Infinity,temporalLagMs=0;
let stream;
let running = false;
let cameraStarting = false;
let cameraAttempt = 0;
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
let systemLoadVersion = 0;
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

let speechRevision=0;
function sentenceState(state,text){document.dispatchEvent(new CustomEvent('handspeak:sentence-state',{detail:{state,text}}));}
function stopSpeech(){speechRevision++;window.speechSynthesis?.cancel();$('#pipelineVoice').classList.remove('active');sentenceState('stopped','Speech stopped · Your draft is unchanged.');}
function speakText(text){
  if(!('speechSynthesis' in window)){notify('Speech is unavailable in this browser');return;}
  const currentSpeech=++speechRevision;window.speechSynthesis.cancel();
  const utterance=new SpeechSynthesisUtterance(text);
  utterance.rate=Number($('#speechRate')?.value||1);
  $('#pipelineVoice').classList.add('active');sentenceState('speaking','Speaking… Use Stop speech to cancel.');
  utterance.onend=()=>{if(currentSpeech!==speechRevision)return;$('#pipelineVoice').classList.remove('active');sentenceState('complete','Speech complete · Ready for your next sentence.');};
  utterance.onerror=()=>{if(currentSpeech!==speechRevision)return;$('#pipelineVoice').classList.remove('active');sentenceState('error','Speech could not play. Try Speak message or check browser audio.');};
  window.speechSynthesis.speak(utterance);
}

const interpreter=createInterpreter({speak:speakText,getMessage:()=>message,setMessage:text=>{message=text;renderMessage();}});

const researchWords=createResearchWords({onWord:addWord,
 onStatus:(word,detail)=>{setWordCameraResult(word,detail,true);setRecognitionFeedback(detail||word);},
 onChange:enabled=>{motionStudio.cancel();liveResult.hidden=true;if(enabled)setRecognitionMode('words',true);}
});
const motionStudio=createMotionStudio({
  isRunning:()=>running && recognitionMode==='words',
  onWord:addWord,
  onStatus:(word,detail)=>{setWordCameraResult(word,detail);setRecognitionFeedback(word==='—'?(detail||'Ready — sign once, then pause.'):`${word} — ${detail||'Possible match; verify before adding.'}`);},
  speak:speakText,
  onDiagnostic:data=>{
    const {sequence,...summary}=data;
    if(new URLSearchParams(location.search).has('motionAudit'))globalThis.__lastMotionSequence=sequence||null;
    cameraDiagnostic.lastCapture=summary;renderCameraDiagnostic();
  },
  onFinish:()=>interpreter.finish()
});
vocabularyLibrary=createVocabularyLibrary({onWord:addWord,setVocabulary:(model,name)=>{researchWords.disable();const prior=motionStudio.usesTemporalModel(),accepted=motionStudio.setVocabulary(model,name);if(accepted){temporalCamera?.reset();if((running||cameraStarting)&&prior!==motionStudio.usesTemporalModel())stopCamera();}return accepted;}});
const capstoneRecognition=createCapstoneRecognition({
  isRunning:()=>running&&recognitionMode==='words',startCamera,onWord:addWord,
  onStatus:(word,detail)=>{setWordCameraResult(word,detail);setRecognitionFeedback(`${word} — ${detail}`);},
  prepare:()=>{researchWords.disable();if(motionStudio.usesTemporalModel()){motionStudio.setVocabulary(null);if(running||cameraStarting)stopCamera();}setRecognitionMode('words');motionStudio.cancel();}
});
const beginnerRecognition=createBeginnerRecognition({
  isRunning:()=>running&&recognitionMode==='words',startCamera,onWord:addWord,
  onStatus:(word,detail)=>{setWordCameraResult(word,detail);setRecognitionFeedback(`${word} — ${detail}`);},
  prepare:()=>{researchWords.disable();if(motionStudio.usesTemporalModel()){motionStudio.setVocabulary(null);if(running||cameraStarting)stopCamera();}setRecognitionMode('words');motionStudio.cancel();}
});
$('#motionTeach').addEventListener('click',()=>researchWords.disable(),true);

function setRecognitionMode(mode,keepResearch=false){
  researchWords.cancel();if(!keepResearch)researchWords.disable();
  if(temporalCamera&&mode!=='words')stopCamera();
  recognitionMode=mode;
  $('#wordRecognitionControls').hidden=mode!=='words';
  $('#recognitionMode').value=mode;
  $('#captureMode').textContent=recognitionMode==='words'?'WORDS IN MOTION':'STATIC LETTERS';
  $('#pipelineMatch').classList.toggle('active',recognitionMode==='words');
  candidate='';candidateSince=0;committed='';
  if(trainingActive)endTraining();
  motionStudio.cancel();liveResult.hidden=true;
  setRecognitionFeedback(running?'Ready — bring your hand into view.':'Camera off — select Start Signing to begin.');
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
    if(researchWords.active())researchWords.recognize();else motionStudio.recognize();
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
  document.dispatchEvent(new CustomEvent('handspeak:draft-changed'));
}

function updateSentence(next){
  if(next===null){notify('Message limit reached (1000 characters)');return false;}
  message=next;renderMessage();return true;
}
function addWord(word){return updateSentence(appendWord(message,word));}
document.querySelectorAll('[data-typed-word]').forEach(button=>button.addEventListener('click',()=>{addWord(button.dataset.typedWord);}));
document.querySelectorAll('[data-punctuation]').forEach(button=>button.addEventListener('click',()=>{updateSentence(finishSentence(message,button.dataset.punctuation));}));
$('#removeWordButton').addEventListener('click',()=>{updateSentence(removeLastWord(message));});

function appendCharacter(char){
  if(message.length>=1000){notify('Message limit reached (1000 characters)');return;}
  message += char;
  renderMessage();
}

function setRecognitionFeedback(text){
  const node=$('#recognitionFeedback');
  if(node && node.textContent!==text)node.textContent=text;
}
function setLive(letter){
  vocabularyLibrary?.showCameraAccuracy(null);
  liveResult.hidden = false;
  liveLetter.textContent = letter || 'No reliable match';
  liveConfidence.textContent = letter?'Possible match — hold steady, then verify the text':'Adjust your hand and try a supported sign';
  setRecognitionFeedback(letter&&committed===letter?`${letter} — recognized. Verify the draft before speaking.`:letter?`Hand detected · ${letter} — possible match. Hold steady.`:'Hand detected · No reliable match. Try a supported sign.');
}

async function prepareFaceTracker(){
  try{
    const vision=await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/+esm');
    const files=await vision.FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/wasm');
    await faceTracker.load(vision,files);
  }catch{ $('#faceTrackingStatus').textContent='Unavailable';$('#faceRetry').hidden=false; }
}
function createHandRecognizer(delegate){
  return handVision.HandLandmarker.createFromOptions(handFiles,{
    baseOptions:{modelAssetPath:'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',delegate},
    runningMode:'VIDEO',numHands:2,minHandDetectionConfidence:.5,minHandPresenceConfidence:.5,minTrackingConfidence:.5
  });
}
function handTrackerFailed(error){
  console.warn('Hand tracking stopped',error);
  try{handLandmarker?.close?.();}catch{}
  handLandmarker=null;motionStudio.cancel();researchWords.cancel();
  cameraDiagnostic.trackerError=String(error?.message||error).slice(0,500);
  const failed=()=>{cameraDiagnostic.trackerState='failed';$('#cameraHelp').textContent='Hand tracking stopped. Stop and restart the camera to retry. Open Camera diagnostics for the error.';renderCameraDiagnostic();};
  if(handDelegate!=='GPU'||!handVision||handRecovery){failed();return;}
  const attempt=cameraAttempt;
  cameraDiagnostic.trackerState='recovering';
  $('#cameraHelp').textContent='Hand tracking is switching to CPU compatibility mode…';renderCameraDiagnostic();
  const recovery=createHandRecognizer('CPU').then(model=>{
    if(attempt!==cameraAttempt||!running){model.close?.();return;}
    handLandmarker=model;handDelegate='CPU';cameraDiagnostic.trackerState='ready';lastVideoTime=-1;
    $('#cameraHelp').textContent='Hand tracking restored in CPU compatibility mode. Bring your full hand into view, sign once, then pause.';renderCameraDiagnostic();
  }).catch(fallbackError=>{if(attempt===cameraAttempt&&running){cameraDiagnostic.trackerError=String(fallbackError?.message||fallbackError).slice(0,500);failed();}}).finally(()=>{if(handRecovery===recovery)handRecovery=null;});
  handRecovery=recovery;
}
async function loadRecognizer(){
  if(handLandmarker){void faceTracker.load();return;}
  cameraButton.disabled=true;cameraButton.textContent='Loading recognizer…';cameraDiagnostic.trackerState='loading';cameraDiagnostic.trackerError=null;
  try{
    handVision=await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/+esm');
    handFiles=await handVision.FilesetResolver.forVisionTasks('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/wasm');
    handDelegate=preferredVisionDelegate();
    try{handLandmarker=await createHandRecognizer(handDelegate);}
    catch(error){if(handDelegate==='CPU')throw error;handDelegate='CPU';handLandmarker=await createHandRecognizer(handDelegate);}
    cameraDiagnostic.trackerState='ready';void faceTracker.load(handVision,handFiles);
  }catch(error){
    console.error(error);cameraDiagnostic.trackerState='failed';cameraDiagnostic.trackerError=String(error?.message||error).slice(0,500);
    throw new Error('The recognition model could not be loaded. Check your internet connection.');
  }finally{
    cameraButton.disabled=false;cameraButton.innerHTML='<span aria-hidden="true">◉</span> Start camera';
  }
}

async function startCamera(){
  if(cameraStarting||running)return;
  setRecognitionFeedback('Starting camera… allow camera access when prompted.');
  cameraStarting=true;cameraButton.disabled=true;const attempt=++cameraAttempt;
  clearInterval(demoTimer);
  try{
    await loadVocabularySettings();if(attempt!==cameraAttempt)return;
    if(!navigator.mediaDevices?.getUserMedia) throw new Error('Camera access is not supported by this browser.');
    if(recognitionMode==='words'&&motionStudio.usesTemporalModel()){
      temporalCamera=createTemporalCamera({
        onDetection:(data,lag)=>{if(!running)return;handDelegate=temporalCamera?.getDelegate?.()||handDelegate;temporalLagMs=lag;temporalHands=(data.landmarks||[]).filter(isUsableHand);temporalFrameAt=data.timestamp;consumeDetection(data,data.timestamp,data.imageAspect);},
        onGap:()=>{motionStudio.cancel();temporalHands=[];setRecognitionFeedback('Camera timing changed or processing fell behind. Pause, then sign again.');},
        onError:message=>{cameraDiagnostic.trackerState='failed';cameraDiagnostic.trackerError=String(message).slice(0,500);if(running){stopCamera();$('#cameraHelp').textContent=message;renderCameraDiagnostic();notify(message);}}
      });
      handDelegate=await temporalCamera.ready;cameraDiagnostic.trackerState='ready';cameraDiagnostic.trackerError=null;void prepareFaceTracker();
    }else await loadRecognizer();
    if(attempt!==cameraAttempt)return;
    const acquired = await navigator.mediaDevices.getUserMedia({video:{facingMode:'user',width:{ideal:960},height:{ideal:720}},audio:false});
    if(attempt!==cameraAttempt){acquired.getTracks().forEach(t=>t.stop());return;}
    stream=acquired;
    video.muted=true;video.playsInline=true;video.srcObject = stream;
    await video.play();
    if(attempt!==cameraAttempt){acquired.getTracks().forEach(t=>t.stop());return;}
    running = true;
    $('#trackingState').textContent='LIVE';$('#captureFeed').textContent='LIVE';
    $('#pipelineTrack').classList.add('active');
    placeholder.hidden = true;
    cameraStatus.classList.add('live');
    cameraStatus.innerHTML = '<i></i> Live';
    cameraButton.innerHTML = '<span aria-hidden="true">■</span> Stop camera';
    $('#cameraHelp').textContent = recognitionMode==='words'?'With Automatic words enabled, sign once and pause briefly. Manual recording is also available.':'Hold a supported sign steady until it is added.';
    setRecognitionFeedback('Camera ready — bring your hand into view.');
    detect();
  }catch(error){
    if(attempt!==cameraAttempt)return;
    stopCamera();
    setRecognitionFeedback('Camera unavailable — check permission and try again.');
    notify(error.message || 'Camera permission was not granted.');
    $('#cameraHelp').textContent = 'Camera unavailable. Check camera permission and close other camera apps, or use the demonstration videos.';
  }finally{if(attempt===cameraAttempt){cameraStarting=false;cameraButton.disabled=false;}}
}

function stopCamera(){
  temporalCamera?.close();temporalCamera=null;temporalHands=[];temporalLagMs=0;
  researchWords.cancel();
  setRecognitionFeedback('Camera off — select Start Signing to begin.');
  cameraAttempt++;
  cameraStarting=false;
  cameraButton.disabled=false;
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
    if(handLandmarker&&!temporalCamera){
      try{detection=handLandmarker.detectForVideo(video,now);}
      catch(error){
        handTrackerFailed(error);
      }
    }
    ctx.clearRect(0,0,canvas.width,canvas.height);
    faceTracker.draw(video,now,ctx,canvas.width,canvas.height,motionStudio.isCapturing()||researchWords.isCapturing()||capstoneRecognition.isCapturing()||beginnerRecognition.isCapturing());
    if(temporalCamera){
      temporalCamera.push(video,now,motionStudio.isCapturing());
      if(now-temporalFrameAt<200)temporalHands.forEach(drawHand);
    }else if(handLandmarker)consumeDetection(detection,now,video.videoHeight/video.videoWidth);
    else setRecognitionFeedback(cameraDiagnostic.trackerState==='recovering'?'Restoring hand tracking in CPU compatibility mode…':'Hand tracking unavailable — stop and restart the camera.');
  }
  animationId=requestAnimationFrame(detect);
}

function consumeDetection(detection,now,imageAspect){
    const hands=(detection.landmarks||[]).filter(isUsableHand);
    const processedAt=performance.now();cameraDiagnostic.times.push(processedAt);cameraDiagnostic.times=cameraDiagnostic.times.filter(t=>processedAt-t<=2000);cameraDiagnostic.rawHands=(detection.landmarks||[]).length;cameraDiagnostic.usableHands=hands.length;
    if(processedAt-cameraDiagnostic.lastRender>=1000){cameraDiagnostic.lastRender=processedAt;renderCameraDiagnostic();}
    if(!temporalCamera)hands.forEach(drawHand);
    $('#trackingHands').textContent=`${hands.length} / 2`;
    if(recognitionMode==='words'){
      if(liveResult.hidden&&!motionStudio.isCapturing()&&!researchWords.active())setRecognitionFeedback(hands.length?($('#automaticWords').checked?'Hand detected — sign once, then pause.':'Hand detected — select Record a word to analyze.'):'No hand detected — bring your hands into view.');
      // Keep original handedness indices when rejecting clipped/small hands.
      const indices=(detection.landmarks||[]).map((p,i)=>isUsableHand(p)?i:-1).filter(i=>i>=0);
      const filtered={landmarks:indices.map(i=>detection.landmarks[i]),handedness:indices.map(i=>detection.handedness?.[i]),imageAspect:imageAspect};
      capstoneRecognition.frame(filtered,now,video);
      beginnerRecognition.frame(filtered,now,video);
      if(!capstoneRecognition.isCapturing()&&!beginnerRecognition.isCapturing())(researchWords.active()?researchWords:motionStudio).frame(filtered,now);
    }else if(hands.length===1){
      missingFrames=0;
      const points=hands[0];
      const wasTraining=trainingActive;
      captureTrainingSample(points,now);
      const result=classifyAI(points)||{letter:'',confidence:0};
      setLive(result.letter,result.confidence);
      if(!wasTraining)stabilize(result,now);
      else {candidate='';candidateSince=0;}
      if(wasTraining)setRecognitionFeedback('Hand detected — collecting personal training examples.');
      else if(committed===result.letter && result.letter)setRecognitionFeedback(`${result.letter} — recognized. Verify the draft before speaking.`);
    }else{
      liveResult.hidden=true;
      setRecognitionFeedback(hands.length?'Use one hand for static letters.':'No hand detected — bring your hand into view.');
      candidate='';candidateSince=0;
      if(++missingFrames>8) committed='';
      if(hands.length>1)$('#cameraHelp').textContent='Use one hand for static letters, or switch to Words in motion.';
    }
}

$('#pipelineVoice').addEventListener('click',()=>{if(message)speakText(message);else notify('Add a message first');});

$('#startSigning').addEventListener('click',()=>{$('#workspace').scrollIntoView({behavior:'smooth'});void startCamera();});
cameraButton.addEventListener('click',()=>running?stopCamera():startCamera());
$('#clearButton').addEventListener('click',()=>{clearInterval(demoTimer);message='';detectionLog=[];sessionStarted=Date.now();renderMessage();notify('Message cleared')});
$('#spaceButton').addEventListener('click',()=>appendCharacter(' '));
$('#backspaceButton').addEventListener('click',()=>{message=message.slice(0,-1);renderMessage()});
$('#copyButton').addEventListener('click',async()=>{if(!message)return notify('There is no message to copy');try{await navigator.clipboard.writeText(message);notify('Message copied')}catch{notify('Copy is unavailable in this browser')}});
$('#speakButton').addEventListener('click',()=>{if(!message)return notify('Add a message first');speakText(message)});
$('#contrastButton').addEventListener('click',()=>{const enabled=document.body.classList.toggle('high-contrast');$('#contrastButton').setAttribute('aria-pressed',String(enabled));try{localStorage.setItem('handspeak-contrast',enabled)}catch{}});
try{if(localStorage.getItem('handspeak-contrast')==='true'){document.body.classList.add('high-contrast');$('#contrastButton').setAttribute('aria-pressed','true');}}catch{}

$('#demoButton').addEventListener('click',()=>{
  if(running) stopCamera();
  clearInterval(demoTimer);
  const demo=['I','L','Y'];let index=0;
  placeholder.hidden=true;liveResult.hidden=false;cameraStatus.classList.add('live');cameraStatus.innerHTML='<i></i> Demo';
  $('#captureFeed').textContent='DEMO';$('#trackingState').textContent='DEMO';
  const tick=()=>{if(index>=demo.length){clearInterval(demoTimer);notify('Demo complete');return}const letter=demo[index++];setLive(letter);liveConfidence.textContent='Simulated example · not camera recognition';setRecognitionFeedback('Demo — simulated letters, not camera recognition.');appendCharacter(letter)};
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
  $('#saveButton').disabled=true;
  try{
    await api('/api/sessions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,detections:detectionLog,durationMs:Date.now()-sessionStarted})});
    notify('Translation saved');
    detectionLog=[];sessionStarted=Date.now();
    await loadSystemData();
  }catch(error){notify(error.message||'Saving is temporarily unavailable. Your message is still here.')}finally{$('#saveButton').disabled=false;}
}

function renderHistory(sessions){
  const list=$('#historyList');list.innerHTML='';
  if(!sessions.length){list.innerHTML='<p class="empty-state">No saved sessions yet.</p>';return}
  sessions.forEach(session=>{
    const item=document.createElement('article');item.className='history-item';
    const text=document.createElement('strong');text.textContent=session.message;
    const date=document.createElement('time');date.dateTime=session.created_at;date.textContent=new Date(session.created_at).toLocaleString();
    const meta=document.createElement('small');meta.textContent=`${session.character_count} characters · ${(session.duration_ms/1000).toFixed(1)} seconds`;
    const actions=document.createElement('div');actions.className='history-buttons';
    const restore=document.createElement('button');restore.type='button';restore.className='text-button';restore.textContent='Use message';restore.onclick=()=>{message=session.message;detectionLog=[];sessionStarted=Date.now();renderMessage();document.dispatchEvent(new CustomEvent('handspeak:navigate',{detail:{target:'#messageBox'}}));$('#messageBox').scrollIntoView({block:'center'});notify('Message loaded for review');};
    const remove=document.createElement('button');remove.type='button';remove.className='text-button';remove.textContent='Delete';remove.setAttribute('aria-label','Delete saved message');remove.onclick=async()=>{remove.disabled=true;try{await api('/api/sessions/'+session.id,{method:'DELETE'});await loadSystemData();notify('Saved message deleted');}catch(e){remove.disabled=false;notify(e.message);}};
    actions.append(restore,remove);item.append(text,date,meta,actions);list.append(item);
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
  const version=++systemLoadVersion;
  try{
    const health=await api('/api/health');
    const [sessions,metrics,gestures]=await Promise.all([api('/api/sessions?limit=20'),api('/api/metrics'),api('/api/gestures')]);
    if(version!==systemLoadVersion)return;
    serverAvailable=health.status==='ok';renderHistory(sessions.sessions);renderMetrics(metrics);$('#systemStatus').textContent='Connected · Showing your latest 20 saved messages';
    if(gestures.gestures.length!==SIGNS.length) console.warn('Gesture database and client classifier differ.');
  }catch{if(version!==systemLoadVersion)return;serverAvailable=false;$('#systemStatus').textContent='Saved messages are unavailable. Your current message is still on this page. Try Refresh.';}
}

$('#saveButton').addEventListener('click',saveSession);
$('#refreshHistory').addEventListener('click',async()=>{await loadSystemData();notify(serverAvailable?'History refreshed':'Server is unavailable')});
['accuracy','usability','performance'].forEach(name=>{$(`#${name}`).addEventListener('input',event=>$(`#${name}Value`).textContent=event.target.value)});
$('#evaluationForm').addEventListener('submit',async event=>{
  event.preventDefault();
  const formElement=event.currentTarget;const submit=formElement.querySelector('button[type=submit]');submit.disabled=true;
  const form=new FormData(formElement);
  const payload=Object.fromEntries(form.entries());
  try{
    await api('/api/evaluations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    formElement.reset();['accuracy','usability','performance'].forEach(name=>$(`#${name}Value`).textContent='5');
    notify('Thank you—evaluation submitted');await loadSystemData();
  }catch(error){notify(error.message||'Feedback could not be submitted. Please try again.')}finally{submit.disabled=false;}
});

window.addEventListener('handspeak-auth-changed',()=>{renderHistory([]);$('#systemStatus').textContent='Loading your saved messages…';void loadSystemData();});
$('#editMessageButton').addEventListener('click',()=>{$('#messageEditForm').hidden=false;$('#messageEditor').value=message;$('#messageEditor').focus();});
$('#cancelMessageEdit').addEventListener('click',()=>{$('#messageEditForm').hidden=true;$('#editMessageButton').focus();});
$('#messageEditForm').addEventListener('submit',event=>{event.preventDefault();message=$('#messageEditor').value.slice(0,1000);renderMessage();$('#messageEditForm').hidden=true;$('#editMessageButton').focus();notify('Message updated');});
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

$('#mirrorPreview').addEventListener('change',()=>{const transform=$('#mirrorPreview').checked?'scaleX(-1)':'none';video.style.transform=transform;canvas.style.transform=transform;notify('Preview orientation changed. Recognition uses the original camera input.');});

createExperienceUI({getMessage:()=>message,setMessage:text=>{message=text;renderMessage();},stopSpeech});
