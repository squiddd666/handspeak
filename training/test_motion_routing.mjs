import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../motion-studio.js',import.meta.url),'utf8');
const raw=source.slice(source.indexOf('const recognizeRaw=')+'const '.length,source.indexOf('  const recognize=')).trim();
function recognizer({binary=[],expanded=false,template=null,category=null}={}){
  return vm.runInNewContext(`${raw};recognizeRaw`,{
    binaryModels:binary,categoryModel:category,defaultModel:null,parameters:{},allExamples:()=>[],expandedEnabled:()=>expanded,
    isTemporalWordModel:()=>false,recognizeTemporalWord:()=>null,recognizeMotion:()=>null,
    recognizeBinaryTemporal:model=>model.match?{label:model.word,confidence:.95}:null,
    recognizeExpandedMotion:()=>template?{label:template,distance:.5}:null,
  });
}
test('accepted BABY specialist is not swallowed by a spurious default template',()=>{
  const raw=recognizer({binary:[{word:'BABY',match:true}],template:'PLEASE'});
  assert.equal(raw([],[],.75).label,'BABY');
});
test('a rejecting specialist cannot replace a valid default suggestion',()=>{
  const raw=recognizer({binary:[{word:'BABY',match:false}],template:'YES'});
  assert.equal(raw([],[],.75).label,'YES');
});

test('accepted HELLO and enabled WATER specialists are not swallowed by templates',()=>{
  assert.equal(recognizer({binary:[{word:'HELLO',match:true}],template:'PLEASE'})([],[],.75).label,'HELLO');
  assert.equal(recognizer({binary:[{word:'WATER',match:true}],template:'NO',expanded:true})([],[],.75).label,'WATER');
});

test('conflicting specialist positives are rejected without comparing unrelated scores',()=>{
  assert.equal(recognizer({binary:[{word:'BABY',match:true},{word:'HELLO',match:true}],template:'YES'})([],[],.75),null);
});
test('WATER cannot bypass the disabled expanded vocabulary',()=>{
  const models=[{word:'WATER',match:true}];
  assert.equal(recognizer({binary:models})([],[],.75),null);
  assert.equal(recognizer({binary:models,expanded:true})([],[],.75).label,'WATER');
});
test('category recognition is isolated from default specialists',()=>{
  assert.equal(recognizer({binary:[{word:'BABY',match:true}],category:{}})([],[],.75),null);
});
test('manual models get a complete four-second window after countdown',()=>{
  assert.match(source,/start:now\+1500,end:now\+5500,deadline:now\+7500/);
  const daily=readFileSync(new URL('../research-words.js',import.meta.url),'utf8');
  assert.match(daily,/start:now\+1500,end:now\+5500/);
});
