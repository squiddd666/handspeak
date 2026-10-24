import {loadVocabularySettings,wordSettings,applyVocabularySettings} from './vocabulary-settings.js?v=20261011-features-1';
import {loadAccuracyProfiles,referenceAccuracy,publishedAccuracy,accuracyText,validAccuracy} from './motion-accuracy.js?v=20261021-baby-1';
const video = document.querySelector('#signExampleVideo');
const status = document.querySelector('#signExampleStatus');
const speed = document.querySelector('#signExampleSpeed');
const buttons = [...document.querySelectorAll('[data-sign-example]')];
for(const button of buttons)button.dataset.signLabel=button.textContent;
const embed=document.querySelector('#signExampleEmbed');
const lesson=document.querySelector('#signExampleLesson');
const playback=document.querySelector('.example-playback');
const embedded={name:'GbeC9TFuSX4',want:'IRUlCZ9jRjM',love:'DAZB0eVf5t0',baby:'UdYuyDhyzfI'};
const daily=new Set(['name','home','have','want','love']);
const extra=new Set(['drink','water','book','food','hungry','like','go']);
// The 7 words verified for the 100-word model's core vocabulary. Each ships a
// short local example in media/signs/ (trimmed to the sign, audio removed) plus
// the publisher lesson link. Provenance: media/signs/core-sources.json.
const coreWords=new Map([['belt','BELT'],['eat','EAT'],['empty','EMPTY'],['peg','PEG'],['soccer','SOCCER'],['squeeze','SQUEEZE'],['vlog','VLOG']]);
const CORE_VIDEO_VERSION='20261023-extended-1';
// Extended tier: 12 further words that clear the same deployability bar. Each
// ships a short local ASL Citizen example in media/signs/ (same trim pipeline as
// the core 7) plus the Signing Savvy lesson link.
const extendedWords=new Map([['lock','LOCK'],['duck','DUCK'],['baseballcap','BASEBALLCAP'],['other','OTHER'],['whatfor','WHATFOR'],['drag','DRAG'],['microscope','MICROSCOPE'],['party','PARTY'],['demand','DEMAND'],['edit','EDIT'],['mechanic','MECHANIC'],['deaf','DEAF']]);
const cameraWords=new Map([...coreWords,...extendedWords]);
const coreLessons={belt:'https://www.signingsavvy.com/search/belt',eat:'https://www.signingsavvy.com/search/eat',empty:'https://www.signingsavvy.com/search/empty',peg:'https://www.signingsavvy.com/search/peg',soccer:'https://www.signingsavvy.com/search/soccer',squeeze:'https://www.signingsavvy.com/search/squeeze',vlog:'https://www.signingsavvy.com/search/vlog',
  lock:'https://www.signingsavvy.com/search/lock',duck:'https://www.signingsavvy.com/search/duck',baseballcap:'https://www.signingsavvy.com/search/baseballcap',other:'https://www.signingsavvy.com/search/other',whatfor:'https://www.signingsavvy.com/search/whatfor',drag:'https://www.signingsavvy.com/search/drag',microscope:'https://www.signingsavvy.com/search/microscope',party:'https://www.signingsavvy.com/search/party',demand:'https://www.signingsavvy.com/search/demand',edit:'https://www.signingsavvy.com/search/edit',mechanic:'https://www.signingsavvy.com/search/mechanic',deaf:'https://www.signingsavvy.com/search/deaf'};
// Held-out test results for the deployed tiers (correct/clips), measured through
// the live endpoint on the v3+v5 ensemble. See hs-eval/DEPLOY-REPORT.md.
const coreAccuracy={BELT:[13,14],EAT:[10,11],EMPTY:[7,8],PEG:[7,8],SOCCER:[8,8],SQUEEZE:[7,8],VLOG:[9,9],
  LOCK:[9,10],DUCK:[8,9],BASEBALLCAP:[8,9],OTHER:[7,8],WHATFOR:[12,14],DRAG:[11,13],MICROSCOPE:[11,13],PARTY:[9,11],DEMAND:[9,11],EDIT:[9,11],MECHANIC:[12,15],DEAF:[8,10]};
const CORE_SENTINEL='capstone-core';
let coreId=null;
const publishedExamples=new Map();
let accuracyProfiles={},publishedPacks=[];
function exampleAccuracy(name){
  const pack=publishedPacks.find(pack=>pack.labels?.includes(name));
  return pack?publishedAccuracy(pack,name):referenceAccuracy(accuracyProfiles,name);
}
function updateAccuracy(){
  const core=coreAccuracy[label];
  const tier=coreWords.has(coreId)||[...coreWords.values()].includes(label)?'Core 7-word':(core?'Extended 19-word':null);
  const metrics=core?null:exampleAccuracy(label),target=document.querySelector('#signExampleAccuracy');
  target.textContent=core
    ?`${tier} ST-GCN · ${core[0]}/${core[1]} correct on the held-out test split (${(100*core[0]/core[1]).toFixed(1).replace(/\.0$/,'')}%). Live-camera accuracy is unverified.`
    :`${accuracyText(metrics)}${metrics?` · ${metrics.model}. ${metrics.scope}`:'. No measured test result is available for this word.'}`;
  for(const button of buttons){
    const name=button.dataset.signLabel||button.textContent;
    const core=coreAccuracy[name];
    const isCore=coreWords.has(button.dataset.signExample);
    let badge=button.querySelector('[data-word-accuracy]');
    if(!badge){badge=document.createElement('small');badge.dataset.wordAccuracy='';badge.style.display='block';button.append(badge);}
    if(core){
      badge.textContent=`${(100*core[0]/core[1]).toFixed(1).replace(/\.0$/,'')}% test · ${core[0]}/${core[1]}`;
      button.title=`${isCore?'Core 7-word':'Extended 19-word'} ST-GCN, held-out test split: ${core[0]}/${core[1]} correct. Live-camera accuracy is unverified.`;
      continue;
    }
    const m=exampleAccuracy(name);
    badge.textContent=validAccuracy(m)?`${(100*m.correct/m.total).toFixed(1).replace(/\.0$/,'')}% test · ${m.correct}/${m.total}`:'Not measured';
    button.title=m?`${accuracyText(m)} · ${m.model}. ${m.scope}`:'Recorded accuracy not measured';
  }
}
let external=false;
function preparePractice(id){
  document.dispatchEvent(new CustomEvent('handspeak:prepare-practice',{detail:{id}}));
}
function pauseAll(){video.pause();if(external&&embed.getAttribute('src'))embed.src=embed.getAttribute('src');}
function instructions(id){const standard=buttons.some(b=>b.dataset.signExample===id),published=publishedExamples.get(id);document.querySelector("#signExampleMode").textContent=published?`${published.label} · Experimental word preview. Select Practice at camera to load its vocabulary, then start the camera, sign once and pause. Review every match; live-camera accuracy is unverified.`:daily.has(id)?`${id.toUpperCase()} · Five-word server preview prepared automatically. Start the camera, sign once, then pause. Review the match before signing again.`:extra.has(id)?`${id.toUpperCase()} · Extra-word preview prepared automatically. Start the camera, sign once, then pause. Review every match; live-camera accuracy is unverified.`:standard?`${id.toUpperCase()} · Automatic capture: start the camera, sign once, then pause. Review the match. You can also use Record a word.`:"Learning example · No enabled model for this word. Personal training is needed before camera practice.";const description=wordSettings(id).description;if(description)document.querySelector("#signExampleMode").textContent+=` ${description}`;}
function chooseEmbedded(id,button=null){
 instructions(id);
 preparePractice(id);
 selection++;pauseAll();label=id.toUpperCase();libraryId=id;external=true;video.hidden=true;embed.hidden=false;playback.hidden=true;
 embed.title=`${label} ASL lesson by ASL University`;embed.src=`https://www.youtube-nocookie.com/embed/${embedded[id]}?playsinline=1&rel=0`;
 lesson.hidden=false;lesson.href=`https://www.lifeprint.com/asl101/pages-signs/${id[0]}/${id}.htm`;lesson.textContent=`${label} lesson · ASL University / Bill Vicars (opens in a new tab)`;
 status.textContent=`${label} · Press play in the YouTube player. If it is unavailable, open the lesson below. Playback loads from YouTube.`;
 updateAccuracy();
 for(const other of buttons)other.setAttribute('aria-pressed',String(other===button));
}
let label = 'HELLO';
let selection = 0;
const applySpeed = () => { video.playbackRate = Number(speed.value); };
async function play() {
  const requested = selection;
  try { applySpeed(); await video.play(); }
  catch { if (requested === selection) status.textContent = `${label} · Use the video play button to start.`; }
}
let libraryId=null;
function chooseCorePractice(id,button=null){
  const name=cameraWords.get(id);
  const isCore=coreWords.has(id);
  const tier=isCore?'Core 7-word':'Extended 19-word';
  selection++;pauseAll();external=false;libraryId=CORE_SENTINEL;label=name;coreId=id;
  video.hidden=false;embed.hidden=true;embed.removeAttribute('src');playback.hidden=false;
  lesson.hidden=false;lesson.href=coreLessons[id];lesson.textContent=`${name} lesson · Signing Savvy (opens in a new tab)`;
  for(const other of buttons)other.setAttribute('aria-pressed',String(other===button));
  video.src=`media/signs/${id}.mp4?v=${CORE_VIDEO_VERSION}`;
  video.setAttribute('aria-label',`${label} ASL sign example from the ASL Citizen research dataset`);
  const fallback=video.querySelector('a');fallback.href=video.src;fallback.textContent=`Download the ${label} example`;
  status.textContent=`${label} · Press play to watch. ASL Citizen research example, trimmed to the sign.`;
  document.querySelector('#signExampleMode').textContent=`${name} · ${tier} camera model ready. Watch the example, then record one complete sign for four seconds and review the top five before adding the word.`;
  video.load();
  updateAccuracy();
}
function chooseExample(name,src,button=null,id=null){
  const selectedId=id||src.split("/").pop().split('?')[0].replace(".mp4","");
  instructions(selectedId);preparePractice(selectedId);selection++;pauseAll();external=false;embed.hidden=true;embed.removeAttribute('src');video.hidden=false;playback.hidden=false;lesson.hidden=true;label=name;libraryId=id;
  for(const other of buttons)other.setAttribute('aria-pressed',String(other===button));
  video.src=src;video.setAttribute('aria-label',`${label} ASL gesture example`);
  const fallback=video.querySelector('a');fallback.href=video.src;fallback.textContent=`Download the ${label} example`;
  status.textContent=`${label} · Press play to watch. Review recognition availability in the vocabulary library.`;video.load();
  updateAccuracy();
}
for(const button of buttons)button.addEventListener('click',()=>{const id=button.dataset.signExample;if(cameraWords.has(id)){chooseCorePractice(id,button);return;}if(wordSettings(id).video)chooseExample(button.dataset.signLabel,wordSettings(id).video,button,id);else if(embedded[id])chooseEmbedded(id,button);else chooseExample(button.dataset.signLabel,`media/signs/${id}.mp4?v=20261020-practice-2`,button,daily.has(id)?id:null);});
document.addEventListener('handspeak:example',event=>{const data=event.detail;if(wordSettings(data.id).video){chooseExample(data.label,wordSettings(data.id).video,null,data.id);return;}if(embedded[data.id]){chooseEmbedded(data.id,buttons.find(b=>b.dataset.signExample===data.id));return;}if(typeof data.label==='string'&&/^media\/signs\/[a-z0-9-]+\.mp4$/.test(data.src))chooseExample(data.label,data.src,null,data.id);});
speed.addEventListener('change', applySpeed);
video.addEventListener('loadedmetadata', () => { video.dataset.orientation = video.videoWidth >= video.videoHeight ? 'landscape' : 'portrait'; applySpeed(); });
video.addEventListener('playing', () => { if(external)return;status.textContent = `${label} · ${video.playbackRate === 1 ? 'Normal speed' : `${video.playbackRate}× speed`}`; });
video.addEventListener('ended', () => { if(external)return;status.textContent = `${label} · Play again or try it at the camera.`; });
video.addEventListener('error', () => { if(external)return;status.textContent = libraryId===CORE_SENTINEL && cameraWords.has(coreId) ? `${label} · Example video could not load. Open the lesson link, then practice with the camera model.` : `${label} · Video could not load. Select the word again to retry.`; });
document.querySelector('#signExampleLoop').addEventListener('change', event => { video.loop = event.target.checked; });
document.querySelector('#signExampleReplay').addEventListener('click', () => { video.currentTime = 0; play(); });
document.querySelector('#signExamplePractice').addEventListener('click', () => {
  pauseAll();
  if(libraryId===CORE_SENTINEL&&coreId){document.dispatchEvent(new CustomEvent('handspeak:capstone-practice',{detail:{id:coreId,label:cameraWords.get(coreId)}}));return;}
  if(libraryId){document.dispatchEvent(new CustomEvent('handspeak:practice',{detail:{id:libraryId}}));return;}
  document.dispatchEvent(new CustomEvent('handspeak:default-practice',{detail:{label}}));
});
// Do not keep decoding a looping example while the visitor is using the camera.
new IntersectionObserver(entries => { if (!entries[0].isIntersecting) pauseAll(); }).observe(document.querySelector('.example-player'));
document.addEventListener('visibilitychange', () => { if (document.hidden) pauseAll(); });

document.addEventListener('handspeak:view',pauseAll);

// Keep this panel in sync with published camera vocabularies and their existing lessons.
async function loadPublishedExamples(){
  try{
    const responses=await Promise.all([
      fetch('models/motion-vocabulary.json',{cache:'no-store'}),
      fetch('models/motion-categories/index.json',{cache:'no-store'})
    ]);
    if(responses.some(response=>!response.ok))return;
    const [catalog,index]=await Promise.all(responses.map(response=>response.json()));
    if(!Array.isArray(catalog.items)||!Array.isArray(index.groups))return;
    publishedPacks=index.groups;
    const container=document.querySelector('.example-words');
    await loadVocabularySettings();
    for(const item of applyVocabularySettings(catalog.items)){
      if(typeof item.id!=='string'||typeof item.label!=='string'||!/^media\/signs\/[a-z0-9-]+\.mp4$/.test(item.video||''))continue;
      const enabled=index.groups.some(pack=>Array.isArray(pack.labels)&&pack.labels.includes(item.label)&&item.cameraGroups?.includes(pack.id));
      if(!enabled)continue;
      publishedExamples.set(item.id,item);
      if(buttons.some(button=>button.dataset.signExample===item.id))continue;
      const button=document.createElement('button');button.type='button';button.className='secondary-button';
      button.dataset.signExample=item.id;button.setAttribute('aria-pressed','false');button.textContent=item.label;
      button.dataset.signLabel=item.label;
      button.addEventListener('click',()=>chooseExample(item.label,item.video,button,item.id));
      buttons.push(button);container.append(button);
    }
    if(libraryId&&publishedExamples.has(libraryId))instructions(libraryId);
    updateAccuracy();
  }catch{ /* Existing practice examples remain available when the library cannot load. */ }
}
void loadPublishedExamples();
void loadAccuracyProfiles().then(profiles=>{accuracyProfiles=profiles;updateAccuracy();});

void loadVocabularySettings().then(()=>{for(const button of buttons){button.hidden=Boolean(wordSettings(button.dataset.signExample).hidden);}for(const option of document.querySelectorAll('#practiceWord option'))option.hidden=Boolean(wordSettings(option.value).hidden);for(const card of document.querySelectorAll('[data-daily-word]'))card.hidden=Boolean(wordSettings(card.dataset.dailyWord.toLowerCase()).hidden);if(buttons.find(b=>b.getAttribute('aria-pressed')==='true')?.hidden)buttons.find(b=>!b.hidden)?.click();});
