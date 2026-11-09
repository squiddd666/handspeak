// Exact current audit/manual route kernels, no expected label or subject metadata.
import {predictManualRoutes} from '../experimental/online_manual_runtime.mjs';
import {motionFrame,encodeMotion,validMotion} from '../../motion-model.js';
import {isUsableHand} from '../../gesture-model.js';
let text='';for await(const chunk of process.stdin)text+=chunk;
const input=JSON.parse(text);
const output=input.cases.map(c=>{
  if(Object.keys(c).sort().join('|')!=='imageAspect|rawFrames')throw new Error('Only measured hand frames/aspect permitted');
  const frames=c.rawFrames.map(f=>f.map(h=>isUsableHand(h)?h:null));
  const sequence=encodeMotion(frames,c.imageAspect);
  return {baseline:predictManualRoutes(input.models,c.rawFrames,c.imageAspect),
    sequence:sequence&&validMotion(sequence)?sequence:null};
});
process.stdout.write(JSON.stringify(output));
