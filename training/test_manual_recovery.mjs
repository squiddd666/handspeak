import test from 'node:test';
import assert from 'node:assert/strict';
import {validManualRecovery,predictManualRecovery} from './experimental/manual_recovery_runtime.mjs';

const sequence=x=>Array.from({length:20},()=>[1,...Array(63).fill(x),...Array(64).fill(0)]);
const modes=['default','expanded','daily','pack'];
function model(){
  return {version:1,featureVersion:'manual-recovery-v1',guard:{version:1,featureVersion:'manual-open-set-competition-v2',encoding:'two-hand-motion-v3',
    samples:[{label:'YES',sequence:sequence(0)},{label:'YES',sequence:sequence(.01)},{label:'YES',sequence:sequence(.02)},{label:'OTHER',sequence:sequence(2)}],
    modes:Object.fromEntries(modes.map(m=>[m,{enabled:true,labels:['YES'],maxDistance:.2,minRatio:1.1}]))},
    modes:Object.fromEntries(modes.map(m=>[m,{enabled:true,classPolicies:{YES:{maxDistance:.2,minRatio:1.1,minVotes:2}}}]))};
}
const baseline=label=>Object.fromEntries(modes.map(m=>[m,label]));
test('a supported fallback can recover a no-match without a target label',()=>{
  const m=model();assert.equal(validManualRecovery(m),true);
  const r=predictManualRecovery(m,sequence(0),baseline(null));assert.equal(r.predictions.default,'YES');assert.equal(r.guarded.default,null);
  assert.equal(r.reasons.default,'recovered-no-match');
});
test('unsupported movements cannot be narrowed into a vocabulary match',()=>{
  assert.equal(predictManualRecovery(model(),sequence(2),baseline(null)).predictions.default,null);
});
test('a retained guard prediction is unchanged; disabling recovery keeps no-match',()=>{
  const m=model();assert.equal(predictManualRecovery(m,sequence(0),baseline('YES')).reasons.default,'guard-retained');
  m.modes.default.enabled=false;assert.equal(predictManualRecovery(m,sequence(0),baseline(null)).predictions.default,null);
});
test('blank or absent measured sequences cannot create predictions',()=>{
  for(const seq of [null,Array.from({length:20},()=>Array(128).fill(0))])assert.equal(predictManualRecovery(model(),seq,baseline(null)).predictions.default,null);
});
test('unknown class and malformed baseline cannot bypass mode policies',()=>{
  const m=model();m.modes.default.classPolicies.OTHER={maxDistance:.2,minRatio:1.1,minVotes:2};assert.equal(validManualRecovery(m),false);
  assert.throws(()=>predictManualRecovery(model(),sequence(0),{default:null}),/baseline/);
});
