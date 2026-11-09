/** Exercise the real reference-only player and all 198 catalog mappings. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import vm from 'node:vm';
import {canWatchReference,hasRecognitionModel,isLocalReferenceHost,recognitionBadge,serverPracticeTarget} from '../recognition-library.js';

const root=new URL('../',import.meta.url);
const read=path=>readFileSync(new URL(path,root),'utf8');
const source=read('sign-examples.js'),catalog=JSON.parse(read('models/motion-vocabulary.json'));
const manifest=JSON.parse(read('models/recognition-videos.json'));
const references=new Map(catalog.items.map(item=>[item.id,item]));
const research=manifest.items.filter(item=>item.kind==='research-local');
function segment(start,end,body=source){
  const a=body.indexOf(start),b=body.indexOf(end,a+start.length);
  assert.ok(a>=0&&b>a,`missing function ${start}`);
  return body.slice(a,b);
}
function element(){
  return {hidden:false,textContent:'',attributes:{},checked:false,
    toggleAttribute(name,on){if(on)this.attributes[name]='';else delete this.attributes[name];},
    setAttribute(name,value){this.attributes[name]=value;},removeAttribute(name){delete this.attributes[name];}};
}
function player(){
  const nodes=new Map(['.example-avatar-panel','#signExampleCompare','#signExampleVideoSource','#signExampleReferenceNote','#signExampleLoop'].map(id=>[id,element()]));
  const plays=[],sync=[],status={},speed={value:'1'};
  const video={readyState:0,videoWidth:640,videoHeight:480,dataset:{},paused:true,
    getAttribute(name){return this[name]||null;},setAttribute(name,value){this[name]=value;},
    removeAttribute(name){delete this[name];},load(){},pause(){this.paused=true;},
    play(){plays.push(this.src);this.paused=false;return Promise.resolve();}};
  const avatar={playing:true,pause(){this.playing=false;},setSyncVideo(value){sync.push(value);}};
  let initialized=0,animated=0;
  const code=`let selectedId='hello',selectedSource=null,label='HELLO',playbackRevision=0;
    ${segment('function referenceOnlySelection(', '\nfunction exampleAccuracy(')}
    ${segment('function pauseAll(', '\nfunction mocapStatus(')}
    ${segment('function videoSrcFor(', '\nfunction showLesson(')}
    ${segment('async function playSign(', '\nfunction chooseSign(')}
    ({select(id){selectedId=id;label=referenceExamples.get(id).label;return playSign(id);},pauseAll,syncVideoRate});`;
  const api=vm.runInNewContext(code,{
    referenceExamples:references,video,videoPanel:element(),avatar,status,speed,playback:{},withoutReference:new Set(),mocapOnly:new Set(),
    document:{querySelector:id=>nodes.get(id)},setTimeout(){},isLocalReferenceHost:()=>true,
    ensureAvatar(){initialized++;return {setSpeed(){},play(){animated++;return true;}};},
    hasSignAnimation:()=>true,hasSkeletalClip:async()=>true,hasReferenceClip:async()=>true,motionStatus:()=>'',
  });
  return {api,video,nodes,status,speed,plays,sync,initialized:()=>initialized,animated:()=>animated};
}

test('all 198 unique labels have playable local references; public hosts cannot offer the 147 research clips',()=>{
  assert.deepEqual(manifest.counts,{labels:198,existingLocal:51,researchLocal:147});
  assert.equal(new Set(manifest.items.map(item=>item.id)).size,198);
  assert.equal(new Set(manifest.items.map(item=>item.label)).size,198);
  for(const entry of manifest.items){
    const item=references.get(entry.id);
    assert.ok(item,entry.label);assert.equal(item.video,entry.video);
    assert.ok(existsSync(new URL(entry.video,root)),entry.video);
    assert.equal(canWatchReference(item,'localhost'),true,entry.label);
    assert.equal(hasRecognitionModel(item),true,entry.label);
    assert.equal(canWatchReference(item,'demo.example.com'),entry.kind==='existing-local',entry.label);
  }
  assert.equal(catalog.items.filter(item=>item.recognitionModes?.length).length,198);
  assert.equal(manifest.simultaneousRecognition,false);
  assert.equal(isLocalReferenceHost('[::1]'),true);
  assert.equal(isLocalReferenceHost('localhost.example.com'),false);
});

test('the real resolver uses all manifest paths, including NAME, WANT, LOVE and BABY',()=>{
  const resolve=vm.runInNewContext(`let selectedId='hello',selectedSource=null;${segment('function videoSrcFor(', '\nfunction syncVideoRate(')}\nvideoSrcFor;`,{
    referenceExamples:references,VIDEO_BASE:'./media/signs/',
  });
  for(const entry of manifest.items)assert.equal(new URL(resolve(entry.id),'http://localhost:8000/').pathname,'/'+entry.video);
  for(const id of ['name','want','love','baby'])assert.match(resolve(id),/\/research-signs\//);
});

test('explicit catalog video sources are passed through chooseExample and the actual event handler',()=>{
  const calls=[];
  const choose=vm.runInNewContext(`${segment('function chooseExample(', '\ntry{')}\nchooseExample;`,{chooseSign:(...args)=>calls.push(args)});
  choose('NAME','media/research-signs/name.mp4',null,'name');
  assert.deepEqual(calls[0],['name',null,'NAME','media/research-signs/name.mp4']);
  const body=source.match(/document\.addEventListener\('handspeak:example',event=>\{([\s\S]*?)\n\}\);/)[1];
  vm.runInNewContext(body,{event:{detail:{id:'love',label:'LOVE',src:'media/research-signs/love.mp4'}},buttons:[],chooseExample:choose});
  assert.equal(calls[1][3],'media/research-signs/love.mp4');
});

test('all 147 new recordings play without loading or displaying a stale Kai animation',async()=>{
  const ui=player();
  for(const item of research){
    assert.equal(await ui.api.select(item.id),true,item.label);
    assert.equal(ui.video.src,'./'+item.video,item.label);
    assert.equal(ui.nodes.get('.example-avatar-panel').hidden,true);
    assert.equal(ui.nodes.get('#signExampleCompare').attributes['data-reference-only'],'');
    assert.match(ui.status.textContent,/Reference video only.*local research/);
    assert.match(ui.nodes.get('#signExampleVideoSource').textContent,/No matched 3D reconstruction/);
    assert.equal(ui.sync.at(-1),null);
    ui.video.onloadeddata();
    assert.equal(ui.plays.at(-1),'./'+item.video);
  }
  assert.equal(ui.initialized(),0);assert.equal(ui.animated(),0);
});

test('reference-only playback retains slow/repeat controls and cancels delayed autoplay',async()=>{
  const ui=player();await ui.api.select('name');
  const old=ui.video.onloadeddata;ui.api.pauseAll();await ui.api.select('love');
  old();assert.deepEqual(ui.plays,[]);assert.equal(ui.video.src,'./media/research-signs/love.mp4');
  ui.speed.value='0.25';ui.nodes.get('#signExampleLoop').checked=true;ui.api.syncVideoRate();
  assert.equal(ui.video.playbackRate,.25);assert.equal(ui.video.loop,true);
  ui.video.onloadeddata();assert.deepEqual(ui.plays,['./media/research-signs/love.mp4']);
});

test('greetings distinguish legacy component labels and repaired synthetic training from natural phrases',()=>{
  for(const label of ['GOOD MORNING','GOOD AFTERNOON','GOOD NIGHT']){
    const item=research.find(item=>item.label===label);
    assert.equal(item.sequence,true);assert.equal(item.sources.length,2);assert.equal(item.sources[0].gloss,'GOOD');
    assert.match(item.referenceNote,/not a continuous phrase performance/);
    assert.match(item.referenceNote,/legacy Beginner checkpoint trained .* on .* only/);
    assert.match(item.referenceNote,/Repaired Beginner weights use synthetic joined greeting training/);
    assert.match(item.referenceNote,/natural continuous full-greeting recognition remains unverified/);
    assert.match(references.get(item.id).referenceNote,/Learning sequence:/);
  }
});

test('BROTHER keeps its existing 3D clip but exposes its already trained Beginner model',()=>{
  const check=vm.runInNewContext(`${segment('function learningOnly(', '\nfunction referenceOnlySelection(')}\nlearningOnly;`,{
    mocapOnly:new Set(['brother','buy','bye','my']),referenceExamples:references,hasRecognitionModel,
  });
  assert.equal(check('brother'),false);assert.equal(check('buy'),true);
  assert.match(recognitionBadge(references.get('brother')),/Beginner-79/);
});

test('server practice selects the right separate vocabulary without starting a camera or enabling consent',async()=>{
  const body=read('vocabulary-library.js'),events=[],nodes=new Map();
  for(const id of ['#recognitionMode','#capstoneVocabMode','#vocabularyCameraStatus','#capstoneWords','#beginnerWords','#capstoneWords button','#beginnerWords button']){
    nodes.set(id,{value:'',textContent:'',dispatchEvent(e){events.push(e.type);},scrollIntoView(){},focus(){}});
  }
  const practice=vm.runInNewContext(`${segment('  async function practice(', '\n  async function preparePractice(',body)}\npractice;`,{
    $:id=>nodes.get(id),serverPracticeTarget,Event:class{constructor(type){this.type=type;}},
    CustomEvent:class{constructor(type,init){this.type=type;this.detail=init.detail;}},
    document:{dispatchEvent:event=>events.push(event)},
  });
  await practice(references.get('comb'));assert.equal(nodes.get('#capstoneVocabMode').value,'full');
  assert.equal(events.at(-1).detail.target,'#capstoneWords');
  await practice(references.get('good-morning'));assert.equal(events.at(-1).detail.target,'#beginnerWords');
  assert.match(nodes.get('#vocabularyCameraStatus').textContent,/No camera was started/);
  assert.match(nodes.get('#vocabularyCameraStatus').textContent,/legacy Beginner checkpoint trained GOOD MORNING on MORNING only/);
  assert.match(nodes.get('#vocabularyCameraStatus').textContent,/natural continuous full-greeting recognition remains unverified/);
});

test('watch navigation occurs before selection, so changing view cannot cancel new-video autoplay',()=>{
  const body=read('vocabulary-library.js'),handler=body.slice(body.indexOf("b.onclick=()=>{document.dispatchEvent"));
  assert.ok(handler.indexOf("'handspeak:navigate'")<handler.indexOf("'handspeak:example'"));
  assert.doesNotMatch(segment('function chooseSign(', '\nfunction chooseCorePractice('),/preparePractice\(/);
  assert.match(read('index.html'),/playsinline muted controls/);
});
