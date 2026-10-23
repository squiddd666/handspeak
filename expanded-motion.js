import {recognizeMotion} from './motion-model.js?v=20261023-hungry-cutoff-2';

// The expanded vocabulary competes only when the user enables the preview.
const compatibilityMatch=(sequence,profile)=>profile&&recognizeMotion(sequence,profile.samples,profile.parameters);

export function recognizeExpandedMotion(sequence, examples, parameters, expansion, baseCompatibility=null) {
  const basePractice = compatibilityMatch(sequence,baseCompatibility);
  const existing = recognizeMotion(sequence, examples, parameters);
  if (!expansion) return existing || basePractice;
  const extraPractice=compatibilityMatch(sequence,expansion.cameraCompatibility);
  if(extraPractice)return extraPractice;
  if (expansion.baselineExtra) {
    // Extra-seven alone first: on phone clips PLEASE is often a slightly closer
    // joint neighbor than HUNGRY but above maxDistance 0.8, so joint-only returned
    // null even when HUNGRY sat inside maxDistanceByLabel 1.5 among extra words.
    const extraLabels = new Set(expansion.labels || expansion.samples.map(s => s.label));
    const extraOnly = recognizeMotion(sequence, expansion.samples, expansion.parameters);
    if (extraOnly) return extraOnly;
    // Joint may still confirm an extra label against the default six; never
    // return PLEASE/YES/etc. during expanded practice (that was the old miss).
    const joint = recognizeMotion(sequence, examples.concat(expansion.samples), expansion.parameters);
    if (joint && extraLabels.has(joint.label)) return joint;
    const prior = expansion.baselineExtra;
    const priorOnly = recognizeMotion(sequence, prior.samples, prior.parameters);
    if (priorOnly) return priorOnly;
    return null;
  }
  const match = recognizeMotion(sequence, examples.concat(expansion.samples), expansion.parameters);
  return match || existing || basePractice;
}
