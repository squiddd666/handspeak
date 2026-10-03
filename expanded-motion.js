import {recognizeMotion} from './motion-model.js?v=20261001-auto-cache-1';

// The expanded vocabulary competes only when the user enables the preview.
export function recognizeExpandedMotion(sequence, examples, parameters, expansion) {
  const existing = recognizeMotion(sequence, examples, parameters);
  if (!expansion) return existing;
  if (expansion.baselineExtra) {
    const joint = recognizeMotion(sequence, examples.concat(expansion.samples), expansion.parameters);
    if (joint && expansion.newLabels.includes(joint.label)) return joint;
    if (existing) return existing;
    const prior = expansion.baselineExtra;
    const match = recognizeMotion(sequence, examples.concat(prior.samples), prior.parameters);
    return match && prior.labels.includes(match.label) ? match : null;
  }
  if (existing) return existing;
  const match = recognizeMotion(sequence, examples.concat(expansion.samples), expansion.parameters);
  return match && expansion.labels.includes(match.label) ? match : null;
}
