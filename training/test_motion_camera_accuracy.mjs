import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {cameraAccuracy,validAccuracy} from '../motion-accuracy.js';
import {hasRecognitionModel} from '../recognition-library.js';

const read=name=>readFileSync(new URL('../'+name,import.meta.url),'utf8');
const profiles=JSON.parse(read('models/motion-word-accuracy.json')).profiles;
const items=JSON.parse(read('models/motion-vocabulary.json')).items;
const manifest=JSON.parse(read('models/recognition-videos.json')).items;
const packs=JSON.parse(read('models/motion-categories/index.json')).groups;

test('camera badges resolve all 198 primary Practice routes, not only six default words',()=>{
  for(const row of manifest){
    const item=items.find(item=>item.id===row.id);
    const small=['default-preview','daily-preview','existing-preview'].includes(item.recognition)||item.cameraGroups?.length;
    const family=small?'motion':item.recognition==='beginner-preview'?'beginner':'capstone';
    const vocabulary=item.recognitionModes?.includes('capstone-core')?'core':item.recognitionModes?.includes('capstone-extended')?'extended':'full';
    const metrics=cameraAccuracy(profiles,item.label,{family,vocabulary,daily:item.recognition==='daily-preview',
      expanded:item.recognition==='existing-preview',pack:packs.find(p=>item.cameraGroups?.includes(p.id))});
    assert.ok(validAccuracy(metrics),`${item.label} (${family})`);
  }
});
test('a live match uses the actual server family rather than the default-word profile',()=>{
  assert.equal(cameraAccuracy(profiles,'APPLE',{family:'capstone'}).profile,'capstoneFull');
  assert.equal(cameraAccuracy(profiles,'BROTHER',{family:'beginner'}).profile,'beginner');
  assert.equal(cameraAccuracy(profiles,'APPLE'),null);
  assert.equal(cameraAccuracy(profiles,'BROTHER',{family:'capstone'}),null);
  const overlap=Object.keys(profiles.beginner.words).find(label=>profiles.capstoneFull.words[label]);
  assert.ok(overlap);
  assert.equal(cameraAccuracy(profiles,overlap,{family:'beginner'}).profile,'beginner');
  assert.equal(cameraAccuracy(profiles,overlap,{family:'capstone'}).profile,'capstoneFull');
});
test('core/extended legacy scores and the all-attempt full score stay distinct',()=>{
  const {current:ignored,...fullArchive}=profiles.capstoneFull;
  const {capstoneCore:ignoredCore,capstoneExtended:ignoredExtended,...legacy}=profiles;
  legacy.capstoneFull=fullArchive;
  const core=cameraAccuracy(legacy,'BELT',{family:'capstone',vocabulary:'core'});
  assert.deepEqual([core.correct,core.total],[13,14]);
  assert.match(core.scope,/tracking failures are not in this legacy denominator/);
  const full=cameraAccuracy(legacy,'BELT',{family:'capstone',vocabulary:'full'});
  assert.deepEqual([full.correct,full.total],[13,18]);
  assert.equal(cameraAccuracy(legacy,'LOCK',{family:'capstone',vocabulary:'core'}),null);
  assert.equal(cameraAccuracy(legacy,'LOCK',{family:'capstone',vocabulary:'extended'}).total,10);
  assert.match(cameraAccuracy(legacy,'BELT',{family:'capstone',vocabulary:'extended'}).scope,/not a per-word measurement of the current extended-19 setting/);
  assert.equal(cameraAccuracy(legacy,'APPLE',{family:'capstone',vocabulary:'core'}),null);
});
test('current core and extended badges use their own all-attempt gated benchmark',()=>{
  for(const [mode,name] of [['core','capstoneCore'],['extended','capstoneExtended']]){
    const expected=profiles[name].current.words.BELT;
    const measured=cameraAccuracy(profiles,'BELT',{family:'capstone',vocabulary:mode});
    assert.deepEqual([measured.correct,measured.total,measured.noMatch],[expected.correct,expected.total,expected.noMatch]);
    assert.match(measured.scope,/tracking failures count as misses/);
    assert.doesNotMatch(measured.scope,/legacy denominator|core-7 reference score/);
    assert.equal(cameraAccuracy(profiles,'APPLE',{family:'capstone',vocabulary:mode}),null);
  }
  assert.equal(cameraAccuracy(profiles,'LOCK',{family:'capstone',vocabulary:'core'}),null);
});
test('personal examples are not assigned pretrained or virtual-camera accuracy',()=>{
  assert.equal(cameraAccuracy(profiles,'HELLO',{personal:true}),null);
  assert.match(read('vocabulary-library.js'),/Personal example · no independently measured recognition benchmark/);
});
test('the camera-label guard accepts known numeric/slash labels and rejects no-match statuses',()=>{
  const source=read('vocabulary-library.js');
  const body=source.slice(source.indexOf('  return {showCameraAccuracy('),source.lastIndexOf('\n}')).trim().replace(/^return\s+/,'');
  const api=vm.runInNewContext(`let cameraMatch=null;const api=${body}\n({show:api.showCameraAccuracy,match:()=>cameraMatch});`,{
    catalog:{items},hasRecognitionModel,renderCameraAccuracy(){},
  });
  for(const row of manifest){api.show(row.label);assert.equal(api.match()?.label,row.label);}
  for(const label of ['8HOUR','HE / SHE','HURDLE / TRIP','I / ME','MY / MINE','YOUR / YOURS']){
    api.show(label);assert.equal(api.match()?.label,label);
  }
  for(const label of ['—','No reliable match','Hands not tracked']){api.show(label);assert.equal(api.match(),null);}
});
test('server callbacks explicitly identify the score family without changing capture logic',()=>{
  const source=read('app.js');
  assert.match(source,/setWordCameraResult\(word,detail,false,'capstone'\)/);
  assert.match(source,/setWordCameraResult\(word,detail,false,'beginner'\)/);
  assert.match(source,/personal:family==='motion'/);
});
