// Terminal-only validation adapter. Never loads an app, video, or camera.
import {readFileSync} from 'node:fs';
import {tensorizeBodyManual, mirrorBodyManual, predictBodyManual, bodyManualDistances} from '../training/experimental/body_manual_runtime.mjs';

const input = JSON.parse(readFileSync(0, 'utf8'));
const results = input.rows.map(row => {
  const sequence = tensorizeBodyManual(row);
  const result = {sequence, mirrored: sequence ? mirrorBodyManual(sequence) : null};
  if (input.model) result.result = predictBodyManual(input.model, row);
  if (input.references && sequence) result.distances = bodyManualDistances(sequence, input.references, input.weights);
  return result;
});
process.stdout.write(JSON.stringify(results));
