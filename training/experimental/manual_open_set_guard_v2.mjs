// Offline rejection-only candidate. Never creates a word prediction, never
// sees a lesson/expected label, and is deliberately absent from application imports.
import {validMotion,motionDistance,mirrorMotion} from '../../motion-model.js';

export const GUARD_VERSION='manual-open-set-competition-v2';
export const GUARD_MODES=Object.freeze(['default','expanded','daily','pack']);

export function validManualOpenSetGuard(model){
  if(!model||model.version!==1||model.featureVersion!==GUARD_VERSION||model.encoding!=='two-hand-motion-v3'
    ||!Array.isArray(model.samples)||model.samples.length<2||model.samples.length>256
    ||!model.samples.every(r=>typeof r.label==='string'&&r.label&&validMotion(r.sequence)))return false;
  const names=new Set(model.samples.map(r=>r.label));
  if(names.size<2||!model.modes||Object.keys(model.modes).sort().join('|')!==[...GUARD_MODES].sort().join('|'))return false;
  return GUARD_MODES.every(mode=>{const p=model.modes[mode];return p&&typeof p.enabled==='boolean'
    &&Array.isArray(p.labels)&&p.labels.length>0&&new Set(p.labels).size===p.labels.length
    &&p.labels.every(l=>typeof l==='string'&&names.has(l))
    &&Number.isFinite(p.maxDistance)&&p.maxDistance>0&&p.maxDistance<=10
    &&Number.isFinite(p.minRatio)&&p.minRatio>=0&&p.minRatio<=5
    &&(!p.classPolicies||Object.entries(p.classPolicies).every(([label,q])=>p.labels.includes(label)
      &&q&&Object.keys(q).sort().join('|')==='maxDistance|minRatio'
      &&Number.isFinite(q.maxDistance)&&q.maxDistance>0&&q.maxDistance<=p.maxDistance
      &&Number.isFinite(q.minRatio)&&q.minRatio>=p.minRatio&&q.minRatio<=5));});
}

export function manualGuardStatistics(model,sequence){
  if(!validManualOpenSetGuard(model))throw new Error('Invalid open-set guard candidate');
  if(!validMotion(sequence)||!sequence.some(f=>f[0]||f[64]))return null;
  const mirrored=mirrorMotion(sequence),byLabel={};
  for(const r of model.samples){
    const d=Math.min(motionDistance(sequence,r.sequence),motionDistance(mirrored,r.sequence));
    byLabel[r.label]=Math.min(byLabel[r.label]??Infinity,d);
  }
  return byLabel;
}

export function applyManualOpenSetGuard(model,sequence,baseline){
  if(!validManualOpenSetGuard(model))throw new Error('Invalid open-set guard candidate');
  if(!baseline||Object.keys(baseline).sort().join('|')!==[...GUARD_MODES].sort().join('|'))throw new Error('Independent baseline modes required');
  const needs=GUARD_MODES.some(mode=>model.modes[mode].enabled&&baseline[mode]!=null);
  const distances=needs?manualGuardStatistics(model,sequence):null,predictions={},diagnostics={};
  for(const mode of GUARD_MODES){
    const p=model.modes[mode],label=baseline[mode],gate=p.classPolicies?.[label]||p;
    if(label!=null&&typeof label!=='string')throw new Error('Invalid baseline prediction');
    let reason='baseline-rejected',accepted=null,same=null,other=null,ratio=null;
    if(label!=null&&p.labels.includes(label)){
      if(!p.enabled){accepted=label;reason='guard-disabled';}
      else if(!distances){reason='invalid-sequence';}
      else{
        same=distances[label];other=Math.min(...Object.entries(distances).filter(([name])=>name!==label).map(([,d])=>d));
        ratio=other/(same+1e-6);
        if(Number.isFinite(same)&&Number.isFinite(other)&&same<=gate.maxDistance&&ratio>=gate.minRatio){accepted=label;reason='retained';}
        else reason='open-set-veto';
      }
    }else if(label!=null)reason='outside-mode';
    predictions[mode]=accepted;
    diagnostics[mode]={baseline:label??null,reason,sameDistance:same,competitorDistance:other,separation:ratio};
  }
  return {predictions,diagnostics};
}
