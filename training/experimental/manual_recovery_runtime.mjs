// Experimental local-only recognizer. TRAIN prototypes and VAL-selected gates;
// never receives a target word, signer, lesson, or reference identity.
import {validMotion,motionDistance,mirrorMotion} from '../../motion-model.js';
import {validManualOpenSetGuard,GUARD_MODES} from './manual_open_set_guard_v2.mjs';

export function validManualRecovery(model){
  return model?.version===1&&model.featureVersion==='manual-recovery-v1'
    &&validManualOpenSetGuard(model.guard)&&model.modes
    &&Object.keys(model.modes).sort().join('|')===[...GUARD_MODES].sort().join('|')
    &&GUARD_MODES.every(m=>{
      const p=model.modes[m];return p&&typeof p.enabled==='boolean'&&p.classPolicies
        &&Object.entries(p.classPolicies).every(([label,g])=>model.guard.modes[m].labels.includes(label)
          &&g&&Number.isFinite(g.maxDistance)&&g.maxDistance>0&&g.maxDistance<=10
          &&Number.isFinite(g.minRatio)&&g.minRatio>=1&&g.minRatio<=5
          &&Number.isInteger(g.minVotes)&&g.minVotes>=1&&g.minVotes<=3);
    });
}

export function manualRecoveryStatistics(model,sequence){
  if(!validManualRecovery(model))throw new Error('Invalid manual recovery candidate');
  if(!validMotion(sequence)||!sequence.some(f=>f[0]||f[64]))return null;
  const reflected=mirrorMotion(sequence),byLabel={};
  const ranked=model.guard.samples.map((r,i)=>{
    const distance=Math.min(motionDistance(sequence,r.sequence),motionDistance(reflected,r.sequence));
    byLabel[r.label]=Math.min(byLabel[r.label]??Infinity,distance);
    return {label:r.label,distance,index:i};
  }).sort((a,b)=>a.distance-b.distance||a.index-b.index);
  const best=ranked[0],other=ranked.find(r=>r.label!==best.label);
  return {byLabel,label:best.label,distance:best.distance,ratio:other.distance/(best.distance+1e-6),
    votes:ranked.slice(0,3).filter(r=>r.label===best.label).length};
}

export function predictManualRecovery(model,sequence,baseline){
  if(!validManualRecovery(model))throw new Error('Invalid manual recovery candidate');
  if(!baseline||Object.keys(baseline).sort().join('|')!==[...GUARD_MODES].sort().join('|')
    ||Object.values(baseline).some(l=>l!=null&&typeof l!=='string'))throw new Error('Independent baseline modes required');
  const stats=manualRecoveryStatistics(model,sequence),guarded={},predictions={},reasons={};
  for(const mode of GUARD_MODES){
    const guard=model.guard.modes[mode],label=baseline[mode],gate=guard.classPolicies?.[label]||guard;
    let accepted=null;
    if(label!=null&&guard.labels.includes(label)){
      if(!guard.enabled)accepted=label;
      else if(stats){
        const same=stats.byLabel[label],other=Math.min(...Object.entries(stats.byLabel).filter(([name])=>name!==label).map(([,d])=>d));
        if(Number.isFinite(same)&&same<=gate.maxDistance&&other/(same+1e-6)>=gate.minRatio)accepted=label;
      }
    }
    guarded[mode]=accepted;predictions[mode]=accepted;reasons[mode]=accepted?'guard-retained':'rejected';
    if(accepted!==null||!stats||!model.modes[mode].enabled)continue;
    const recovery=model.modes[mode].classPolicies[stats.label];
    if(recovery&&stats.distance<=recovery.maxDistance&&stats.ratio>=recovery.minRatio&&stats.votes>=recovery.minVotes){
      predictions[mode]=stats.label;reasons[mode]=label==null?'recovered-no-match':'recovered-after-veto';
    }
  }
  return {predictions,guarded,reasons,statistics:stats};
}
