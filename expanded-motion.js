import {recognizeMotion} from './motion-model.js?v=20261018-perword-1';

// The expanded vocabulary competes only when the user enables the preview.
const compatibilityMatch=(sequence,profile)=>profile&&recognizeMotion(sequence,profile.samples,profile.parameters);

export function recognizeExpandedMotion(sequence, examples, parameters, expansion, baseCompatibility=null) {
  const basePractice = compatibilityMatch(sequence,baseCompatibility);
  const existing = recognizeMotion(sequence, examples, parameters);
  if (!expansion) return existing || basePractice;
  const extraPractice=compatibilityMatch(sequence,expansion.cameraCompatibility);
  if(extraPractice)return extraPractice;
  if (expansion.baselineExtra) {
    const joint = recognizeMotion(sequence, examples.concat(expansion.samples), expansion.parameters);
    if (joint && expansion.labels.includes(joint.label)) return joint;
    if (existing) return existing;
    const prior = expansion.baselineExtra;
    const match = recognizeMotion(sequence, examples.concat(prior.samples), prior.parameters);
    return match && prior.labels.includes(match.label) ? match : basePractice;
  }
  if (existing) return existing;
  const match = recognizeMotion(sequence, examples.concat(expansion.samples), expansion.parameters);
  return match && expansion.labels.includes(match.label) ? match : basePractice;
}
