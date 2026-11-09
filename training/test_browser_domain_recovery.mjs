import test from 'node:test';import assert from 'node:assert/strict';
import {validBrowserDomainRecovery,predictBrowserDomainRecovery} from './experimental/browser_domain_recovery.mjs';
const sequence=value=>Array.from({length:20},()=>[1,...Array(63).fill(value),...Array(64).fill(0)]);
function model(){return {version:1,featureVersion:'browser-domain-recovery-v1',samples:[{label:'YES',sequence:sequence(0)},{label:'OTHER',sequence:sequence(10)}],
  modes:Object.fromEntries(['default','expanded','daily','pack'].map(m=>[m,{labels:['YES','NO'],guardPolicies:{},recoveryPolicies:{}}]))};}
const baseline=(v=null)=>({default:v,expanded:null,daily:null,pack:null});
test('sparse labels keep baseline rather than another detector global gate',()=>{
  const m=model();assert.ok(validBrowserDomainRecovery(m));assert.equal(predictBrowserDomainRecovery(m,null,baseline('NO')).predictions.default,'NO');
});
test('fallback can run only after rejection and with an explicit class gate',()=>{
  const m=model();m.modes.default.recoveryPolicies.YES={maxDistance:.2,minRatio:1.3,minVotes:1};
  assert.equal(predictBrowserDomainRecovery(m,sequence(0),baseline()).predictions.default,'YES');
  assert.equal(predictBrowserDomainRecovery(m,sequence(0),baseline('NO')).predictions.default,'NO');
  assert.equal(predictBrowserDomainRecovery(model(),sequence(0),baseline()).predictions.default,null);
});
test('unsupported nearest signs and invalid frames cannot become known words',()=>{
  const m=model();m.modes.default.recoveryPolicies.YES={maxDistance:10,minRatio:1,minVotes:1};
  assert.equal(predictBrowserDomainRecovery(m,sequence(10),baseline()).predictions.default,null);
  assert.equal(predictBrowserDomainRecovery(m,null,baseline()).predictions.default,null);
});
test('guard cannot relabel a baseline word; independent recovery may follow veto',()=>{
  const m=model();m.modes.default.guardPolicies.NO={maxDistance:.3,minRatio:1};
  const r=predictBrowserDomainRecovery(m,sequence(0),baseline('NO'));assert.equal(r.guarded.default,null);assert.equal(r.predictions.default,null);
});
test('rejects incomplete baseline modes and invalid model thresholds',()=>{
  const m=model();assert.throws(()=>predictBrowserDomainRecovery(m,sequence(0),{default:'YES'}));
  m.modes.default.recoveryPolicies.YES={maxDistance:.3,minRatio:.5,minVotes:1};assert.equal(validBrowserDomainRecovery(m),false);
});
