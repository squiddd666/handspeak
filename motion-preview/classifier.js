import {encodeMotion} from './motion-model.js';
import {alignTemporalWindow} from './temporal-window.js';
import {bodyTipFeatures,residualMotionLogits} from './runtime.js';
// Preserve the frozen model's full-class winner and rejection thresholds.
export function classify(model,frames,aspect){
 return classifyRow(model,{rawFrames:frames,body:frames.map(()=>null),imageAspect:aspect,sequence:encodeMotion(frames,aspect)});
}
export function classifyRow(model,row){
 if(!row.sequence)return {label:null,validSequence:false};
 if(model.thresholdByLabel&&!model.labels.every(label=>Number.isFinite(model.thresholdByLabel[label])&&model.thresholdByLabel[label]>=model.threshold&&model.thresholdByLabel[label]<=1))throw Error('Invalid word cutoffs');
 const input=bodyTipFeatures(alignTemporalWindow(row));
 const scores=Array(model.outputLabels.length).fill(0);
 for(const weights of model.weights){const logits=residualMotionLogits(input,weights),max=Math.max(...logits),exp=logits.map(x=>Math.exp(x-max)),sum=exp.reduce((a,b)=>a+b,0);exp.forEach((x,i)=>scores[i]+=x/sum/model.weights.length);}
 const order=scores.map((_,i)=>i).sort((a,b)=>scores[b]-scores[a]),label=model.outputLabels[order[0]];
 const accepted=model.labels.includes(label)&&scores[order[0]]>=(model.thresholdByLabel?.[label]??model.threshold)&&scores[order[0]]-scores[order[1]]>=model.margin;
 return {label:accepted?label:null,validSequence:true};
}
