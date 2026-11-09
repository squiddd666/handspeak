import test from 'node:test';import assert from 'node:assert/strict';
import {GUARD_VERSION,GUARD_MODES,validManualOpenSetGuard,applyManualOpenSetGuard} from './experimental/manual_open_set_guard_v2.mjs';
const seq=x=>Array.from({length:20},()=>[1,...Array.from({length:63},(_,i)=>i%3===0?x:0),...Array(64).fill(0)]);
const base=()=>({version:1,featureVersion:GUARD_VERSION,encoding:'two-hand-motion-v3',samples:[{label:'A',sequence:seq(0)},{label:'B',sequence:seq(1)}],
  modes:Object.fromEntries(GUARD_MODES.map(m=>[m,{enabled:true,labels:['A'],maxDistance:10,minRatio:0,classPolicies:{A:{maxDistance:.1,minRatio:1}}}]))});
test('class gates only tighten and never generate another prediction',()=>{
  const m=base();assert.equal(validManualOpenSetGuard(m),true);
  const b=Object.fromEntries(GUARD_MODES.map(m=>[m,'A']));
  assert.deepEqual(applyManualOpenSetGuard(m,seq(1),b).predictions,Object.fromEntries(GUARD_MODES.map(m=>[m,null])));
  assert.deepEqual(applyManualOpenSetGuard(m,seq(0),b).predictions,b);
});
test('sparse class fallback remains the global gate',()=>{
  const m=base();m.modes.default.classPolicies={};
  assert.equal(applyManualOpenSetGuard(m,seq(1),Object.fromEntries(GUARD_MODES.map(m=>[m,'A']))).predictions.default,'A');
});
test('relaxing, unknown or malformed class gates fail closed',()=>{
  for(const q of [{maxDistance:11,minRatio:1},{maxDistance:1,minRatio:-1},{maxDistance:1,minRatio:1,expected:'A'}]){
    const m=base();m.modes.default.classPolicies.A=q;assert.equal(validManualOpenSetGuard(m),false);
  }
  const m=base();m.modes.default.classPolicies.UNKNOWN={maxDistance:1,minRatio:1};assert.equal(validManualOpenSetGuard(m),false);
});
