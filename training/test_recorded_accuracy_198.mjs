import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {referenceAccuracy,publishedAccuracy,accuracyText,validAccuracy} from '../motion-accuracy.js';

const read=path=>readFileSync(new URL(`../${path}`,import.meta.url),'utf8');
const profiles=JSON.parse(read('models/motion-word-accuracy.json')).profiles;
const items=JSON.parse(read('models/motion-vocabulary.json')).items;
const manifest=JSON.parse(read('models/recognition-videos.json')).items;
const packs=JSON.parse(read('models/motion-categories/index.json')).groups;
const evidence=JSON.parse(read('reports/recorded-word-accuracy/provenance.json'));

test('all 198 recognition labels resolve to real recorded-result counts',()=>{
  const missing=[];
  for(const row of manifest){
    const item=items.find(item=>item.id===row.id);
    const pack=packs.find(pack=>item.cameraGroups?.includes(pack.id)&&pack.labels?.includes(item.label));
    const metrics=(pack?publishedAccuracy(pack,item.label):null)||referenceAccuracy(profiles,item.label,item);
    if(!validAccuracy(metrics))missing.push(item.label);
    else assert.doesNotMatch(accuracyText(metrics),/Not measured/);
  }
  assert.equal(manifest.length,198);
  assert.deepEqual(missing,[]);
  assert.equal(evidence.recognitionLabelsWithRecordedResults,198);
  assert.deepEqual(evidence.missingLabels,[]);
});

test('full benchmark retains every reported attempt, including tracking misses',()=>{
  const words=Object.values(profiles.capstoneFull.words);
  assert.equal(words.length,100);
  assert.equal(words.reduce((n,x)=>n+x.total,0),1157);
  assert.equal(words.reduce((n,x)=>n+x.correct,0),732);
  assert.equal(words.reduce((n,x)=>n+x.answered,0),984);
  assert.ok(words.some(x=>x.answered<x.total));
  assert.match(profiles.capstoneFull.scope,/count as misses/);
  assert.equal(evidence.full.evaluatedWeightsMatch,true);
  assert.equal(evidence.full.snapshots,4);
  assert.equal(profiles.capstoneFull.modelSha256,evidence.full.sha256);
});

test('Beginner publishes all 79 labels, not only the previously passing subset',()=>{
  const words=Object.values(profiles.beginner.words);
  assert.equal(words.length,79);
  assert.equal(words.reduce((n,x)=>n+x.total,0),677);
  assert.equal(words.reduce((n,x)=>n+x.correct,0),505);
  assert.ok(words.some(x=>x.correct/x.total<0.7));
  assert.equal(profiles.beginner.checkpoint,'beginner-need79-v1.pt');
  assert.equal(profiles.beginner.modelSha256,evidence.beginner.sha256);
});

test('overlapping labels prefer the same server family selected by Practice',()=>{
  const shared={
    default:{words:{WORD:{correct:1,total:3}}},
    beginner:{words:{WORD:{correct:2,total:3}}},
    capstoneFull:{words:{WORD:{correct:3,total:3}}},
  };
  assert.equal(referenceAccuracy(shared,'WORD',{recognition:'beginner-preview'}).profile,'beginner');
  assert.equal(referenceAccuracy(shared,'WORD',{recognition:'capstone-preview'}).profile,'capstoneFull');
  assert.equal(referenceAccuracy(profiles,'BROTHER',items.find(x=>x.id==='brother')).profile,'beginner');
  assert.equal(referenceAccuracy(profiles,'APPLE',items.find(x=>x.id==='apple')).profile,'capstoneFull');
});

test('existing small-model scores are preserved and zero scores are not hidden',()=>{
  assert.equal(referenceAccuracy(profiles,'HELLO').correct,11);
  assert.equal(referenceAccuracy(profiles,'HELLO').total,12);
  assert.equal(referenceAccuracy(profiles,'WATER').correct,5);
  assert.equal(referenceAccuracy(profiles,'WATER').total,8);
  assert.equal(referenceAccuracy(profiles,'BABY').correct,8);
  assert.equal(accuracyText({correct:0,total:7}),'Recorded accuracy: 0% (0/7 clips)');
  for(const x of [null,{correct:7,total:0},{correct:8,total:7},{correct:1.5,total:7}])assert.equal(validAccuracy(x),false);
  assert.match(accuracyText(null),/Not measured/);
});

test('archived component and current synthetic greeting counts cannot imply natural phrase accuracy',()=>{
  for(const label of ['GOOD MORNING','GOOD AFTERNOON','GOOD NIGHT']){
    const item=items.find(x=>x.label===label);
    const metrics=referenceAccuracy(profiles,label,item);
    assert.match(profiles.beginner.words[label].note,/not the complete greeting sequence/);
    assert.match(metrics.scope,/synthetic joined/);
    assert.match(metrics.scope,/natural continuous greetings/);
    assert.match(metrics.scope,/live-camera accuracy remains unverified/i);
    assert.ok(metrics.syntheticGreeting>0);
  }
});

test('both visible catalogs reload the shared accuracy resolver and distinguish learning-only entries',()=>{
  for(const name of ['sign-examples.js','vocabulary-library.js'])assert.match(read(name),/motion-accuracy\.js\?v=20261107-calibrated-metrics-1/);
  assert.match(read('vocabulary-library.js'),/Learning-only entry · no pretrained recognition benchmark/);
  assert.match(read('index.html'),/id="signExampleMetricsCoverage"/);
  assert.match(read('index.html'),/app\.js\?v=20261108-capture-worker-8/);
  assert.match(read('index.html'),/sign-examples\.js\?v=20261107-motion-release-1/);
  assert.match(read('app.js'),/vocabulary-library\.js\?v=20261107-motion-release-2/);
});

test('current profiles publish exact frozen held-out counts and retain zero-accuracy words',()=>{
  const current=JSON.parse(read('models/motion-word-accuracy.json')).currentRelease;
  const release=JSON.parse(read(current.provenance));
  const reportDir=current.provenance.slice(0,current.provenance.lastIndexOf('/'));
  const calibration=JSON.parse(read('models/motion-calibration.json'));
  assert.equal(release.archivesPreserved,true);
  assert.equal(release.watchClipsExcluded,true);
  assert.equal(release.testUsedForSelection,false);
  for(const [name,family,mode] of [['beginner','beginner','full'],['capstoneFull','capstone','full'],['capstoneCore','capstone','core'],['capstoneExtended','capstone','extended']]){
    const profile=profiles[name].current;
    const report=JSON.parse(read(`${reportDir}/heldout-${family}.json`));
    const measured=report.selected.modes[mode].accepted;
    assert.equal(profile.modelSha256,report.selected.checkpointSha256);
    assert.equal(profile.modelSha256,calibration.models[family].checkpointSha256);
    assert.equal(profile.calibrationId,calibration.calibrationId);
    const auxiliary=calibration.models[family].auxiliary;
    if(auxiliary){
      assert.equal(profile.auxiliarySha256,auxiliary.checkpointSha256);
      assert.equal(profile.auxiliarySha256,report.selected.auxiliarySha256);
      assert.equal(profile.auxiliaryWeight,report.selected.modes[mode].auxiliaryWeight);
      assert.equal(profile.auxiliaryWeight,auxiliary.weights[mode]);
    }
    assert.equal(profile.totals.attempts,measured.attempts);
    assert.equal(profile.totals.correct,measured.correct);
    assert.equal(profile.totals.wrong,measured.wrong);
    assert.equal(profile.totals.noMatch,measured.noMatch);
    assert.equal(profile.totals.negativeFalse,measured.negativeFalse);
    for(const [label,word] of Object.entries(profile.words)){
      const expected=measured.perLabel[word.datasetLabel];
      assert.deepEqual([word.correct,word.total,word.wrong,word.noMatch,word.tracked],
        [expected.correct,expected.total,expected.wrong,expected.noMatch,expected.tracked],label);
      assert.equal(word.answered,word.correct+word.wrong);
    }
  }
  const metrics=referenceAccuracy(profiles,'GOOD MORNING',items.find(x=>x.label==='GOOD MORNING'));
  assert.equal(metrics.correct,profiles.beginner.current.words['GOOD MORNING'].correct);
  // A retrained greeting need not stay at zero. Keep an explicit zero-score
  // fixture so reporting regressions cannot hide genuinely failed classes.
  const zero=referenceAccuracy({beginner:{current:{words:{WORD:{correct:0,total:7}}}}},'WORD',{recognition:'beginner-preview'});
  assert.equal(zero.correct,0);
  assert.match(accuracyText(zero),/^Recorded accuracy: 0%/);
});
