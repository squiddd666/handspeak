// Audit-only composition of existing route kernels. Never receives an expected
// word, lesson, signer, or selected clip label. All four modes run on each take.
import {encodeMotion,validMotion,recognizeMotion,motionDistance,mirrorMotion} from '../../motion-model.js';
import {recognizeExpandedMotion} from '../../expanded-motion.js';
import {recognizeBinaryTemporal} from '../../hello-binary.js';
import {isUsableHand} from '../../gesture-model.js';

function onlineDailyMatch(sequence,profile) {
  if(!profile?.samples?.length)return null;
  const ranked=profile.samples.map(sample=>({label:sample.label,
    distance:Math.min(motionDistance(sequence,sample.sequence),motionDistance(mirrorMotion(sequence),sample.sequence))}));
  ranked.sort((a,b)=>a.distance-b.distance||(a.label<b.label?-1:a.label>b.label?1:0));
  const best=ranked[0],other=ranked.find(row=>row.label!==best.label),p=profile.parameters;
  const ratio=(other?.distance??Infinity)/(best.distance+1e-6),votes=ranked.slice(0,3).filter(row=>row.label===best.label).length;
  return profile.labels.includes(best.label)&&best.distance<=(p.maxDistanceByLabel?.[best.label]??p.maxDistance)&&
    ratio>=p.minRatio&&(votes>=p.minVotes||ratio>=(p.strongRatio??Infinity))?best.label:null;
}

export function predictManualRoutes(models,raw,aspect) {
  const frames=raw.map(frame=>frame.map(hand=>isUsableHand(hand)?hand:null)),sequence=encodeMotion(frames,aspect);
  const empty={default:null,expanded:null,daily:null,pack:null};
  if(!sequence)return empty;
  const specific=[models.hello,models.baby,models.water].map(model=>recognizeBinaryTemporal(model,frames,aspect));
  const motion=expanded=>{
    const positive=specific.filter((match,index)=>match&&(expanded||index!==2));
    if(positive.length>1)return null;
    if(positive.length===1)return positive[0].label;
    return recognizeExpandedMotion(sequence,models.base.samples,models.base.parameters,expanded?models.extra:null,models.base.cameraCompatibility)?.label||null;
  };
  const daily=validMotion(sequence)?onlineDailyMatch(sequence,models.daily)||onlineDailyMatch(sequence,models.daily.cameraCompatibility):null;
  const pack=recognizeMotion(sequence,models.pack.samples,models.pack.parameters)?.label||null;
  return {default:motion(false),expanded:motion(true),daily,pack:pack==='OTHER MOVEMENT'?null:pack};
}
