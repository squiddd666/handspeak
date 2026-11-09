// Experimental measured-browser-domain candidate, not imported by the app.
import {validMotion,motionDistance,mirrorMotion} from '../../motion-model.js';
export const DOMAIN_MODES=Object.freeze(['default','expanded','daily','pack']);
export function validBrowserDomainRecovery(model){
  const maxSamples=model?.featureVersion==='body-context-recovery-v1'?1024:256;
  if(model?.version!==1||!['browser-domain-recovery-v1','body-context-recovery-v1'].includes(model.featureVersion)||!Array.isArray(model.samples)
    ||model.samples.length<2||model.samples.length>maxSamples||!model.samples.every(r=>typeof r.label==='string'&&validMotion(r.sequence))
    ||!model.modes||Object.keys(model.modes).sort().join('|')!==[...DOMAIN_MODES].sort().join('|'))return false;
  return DOMAIN_MODES.every(m=>{const p=model.modes[m];return p&&Array.isArray(p.labels)&&p.labels.length>0&&new Set(p.labels).size===p.labels.length
    &&p.labels.every(l=>typeof l==='string')&&p.guardPolicies&&p.recoveryPolicies
    &&[p.guardPolicies,p.recoveryPolicies].every((policies,index)=>Object.entries(policies).every(([label,g])=>p.labels.includes(label)
      &&g&&Number.isFinite(g.maxDistance)&&g.maxDistance>0&&g.maxDistance<=10&&Number.isFinite(g.minRatio)&&g.minRatio>=(index?1:0)&&g.minRatio<=5
      &&(!index||(Number.isInteger(g.minVotes)&&g.minVotes>=1&&g.minVotes<=3))));});
}
export function browserDomainStatistics(model,sequence){
  if(!validBrowserDomainRecovery(model))throw new Error('Invalid detector-domain candidate');
  if(!validMotion(sequence)||!sequence.some(f=>f[0]||f[64]))return null;
  const reflected=mirrorMotion(sequence),byLabel={};
  const ranked=model.samples.map((r,index)=>{const distance=Math.min(motionDistance(sequence,r.sequence),motionDistance(reflected,r.sequence));
    byLabel[r.label]=Math.min(byLabel[r.label]??Infinity,distance);return {label:r.label,distance,index};
  }).sort((a,b)=>a.distance-b.distance||a.index-b.index);
  const best=ranked[0],other=ranked.find(r=>r.label!==best.label);
  if(!other)return null;
  return {byLabel,label:best.label,distance:best.distance,ratio:other.distance/(best.distance+1e-6),votes:ranked.slice(0,3).filter(r=>r.label===best.label).length};
}
export function predictBrowserDomainRecovery(model,sequence,baseline){
  if(!validBrowserDomainRecovery(model))throw new Error('Invalid detector-domain candidate');
  if(!baseline||Object.keys(baseline).sort().join('|')!==[...DOMAIN_MODES].sort().join('|')
    ||Object.values(baseline).some(v=>v!=null&&typeof v!=='string'))throw new Error('Independent baseline modes required');
  const stats=browserDomainStatistics(model,sequence),predictions={},guarded={},reasons={};
  for(const mode of DOMAIN_MODES){
    const p=model.modes[mode],label=baseline[mode],gate=p.guardPolicies[label];
    let accepted=p.labels.includes(label)?label:null;
    // Sparse/untested labels have NO guard policy: retain the baseline rather
    // than using an unvalidated global gate from another label or detector.
    if(accepted!=null&&gate){
      const same=stats?.byLabel[label],other=stats?Math.min(...Object.entries(stats.byLabel).filter(([l])=>l!==label).map(([,d])=>d)):null;
      if(!Number.isFinite(same)||!Number.isFinite(other)||same>gate.maxDistance||other/(same+1e-6)<gate.minRatio)accepted=null;
    }
    guarded[mode]=accepted;predictions[mode]=accepted;reasons[mode]=accepted?'retained':'rejected';
    if(accepted!=null||!stats)continue;
    const fallback=p.recoveryPolicies[stats.label];
    if(fallback&&stats.distance<=fallback.maxDistance&&stats.ratio>=fallback.minRatio&&stats.votes>=fallback.minVotes){
      predictions[mode]=stats.label;reasons[mode]=label==null?'recovered-no-match':'recovered-after-veto';
    }
  }
  return {predictions,guarded,reasons,statistics:stats};
}
