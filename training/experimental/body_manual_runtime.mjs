// OFFLINE CANDIDATE ONLY. Not imported by index.html or production capture.
// Pure landmark math for parity checks, independent of a lesson/expected word.
export const FEATURE_VERSION = 'body-manual-aspect-v1';
const LENGTH = 20, CHANNELS = 146, POSE_MIRROR = [0, 2, 1, 4, 3, 6, 5];
const f32 = Math.fround;
const number = value => typeof value === 'number' && Number.isFinite(value);
const roundEven = x => {
  const lo = Math.floor(x), rest = x - lo;
  return rest === .5 ? lo + lo % 2 : Math.round(x);
};
function points(value, count) {
  if (!Array.isArray(value) || value.length !== count) throw new Error('Malformed landmarks');
  const columns = value[0]?.length;
  if (![2, 3].includes(columns) || value.some(p => !Array.isArray(p) || p.length !== columns ||
    p.some(v => !number(v) || Math.abs(v) > 20))) throw new Error('Invalid landmark coordinates');
  return value.map(p => p.map(f32));
}
const absent = value => value == null || (Array.isArray(value) && value.length === 0);
function median(values) {
  if (!values.length) return 1;
  const sorted = values.toSorted((a, b) => a - b), middle = sorted.length >> 1;
  return sorted.length % 2 ? sorted[middle] : f32(f32(sorted[middle - 1] + sorted[middle]) / 2);
}
function norm32(values) {
  return f32(Math.sqrt(values.map(v => f32(v * v)).reduce((a, b) => f32(a + b), 0)));
}

export function tensorizeBodyManual(row) {
  try {
    const frames = row?.frames, aspect = row?.imageAspect;
    if (!number(aspect) || aspect < .2 || aspect > 5 || !Array.isArray(frames) || frames.length < 5 ||
      frames.some(frame => !frame || typeof frame !== 'object' || Array.isArray(frame))) return null;
    if (frames.filter(frame => ['left', 'right'].some(side => Array.isArray(frame[side]) && frame[side].length === 21)).length < 5) return null;
    const pose = frames.map(frame => points(frame.pose, 7).map(p => [p[0], f32(p[1] * aspect)]));
    const visible = frames.map(frame => ['left', 'right'].map(side => absent(frame[side]) ? 0 : 1));
    const hands = frames.map(frame => ['left', 'right'].map(side => absent(frame[side])
      ? Array.from({length: 21}, () => [0, 0, 0])
      : points(frame[side], 21).map(p => [p[0], f32(p[1] * aspect), p[2] ?? 0])));
    const center = [0, 1].map(axis => f32(pose.reduce((total, frame) =>
      f32(total + f32(f32(frame[3][axis] + frame[4][axis]) / 2)), 0) / pose.length));
    const span = f32(pose.reduce((total, frame) => f32(total + norm32([0, 1].map(axis =>
      f32(frame[3][axis] - frame[4][axis])))), 0) / pose.length);
    if (span < 1e-5) return null;
    const shape = hands.map(frame => frame.map(hand => hand.map(point => point.map((v, axis) => f32(v - hand[0][axis])))));
    const scales = [0, 1].map(side => Math.max(.01, median(shape.filter((_, t) => visible[t][side])
      .map(frame => norm32(frame[side][9])))));
    const values = pose.map((frame, t) => [
      ...frame.flatMap(p => p.map((v, axis) => f32(f32(v - center[axis]) / span))),
      ...hands[t].flatMap((hand, side) => [0, 1].map(axis => visible[t][side] ? f32(f32(hand[0][axis] - center[axis]) / span) : 0)),
      ...shape[t].flatMap((hand, side) => hand.flatMap(p => p.map(v => visible[t][side] ? f32(v / scales[side]) : 0))),
      ...visible[t],
    ]);
    return Array.from({length: LENGTH}, (_, t) => {
      const index = t * (values.length - 1) / (LENGTH - 1), lo = Math.floor(index);
      const hi = Math.min(lo + 1, values.length - 1), nearest = roundEven(index), w = index - lo;
      const out = values[lo].map((v, c) => v * (1 - w) + values[hi][c] * w);
      for (let side = 0; side < 2; side++) {
        const both = visible[lo][side] * visible[hi][side];
        for (const [start, end] of [[14 + side * 2, 16 + side * 2], [18 + side * 63, 81 + side * 63]]) {
          for (let c = start; c < end; c++) out[c] = (both ? out[c] : values[nearest][c]) * visible[nearest][side];
        }
        out[144 + side] = visible[nearest][side];
      }
      return out.map(v => f32(Math.max(-10, Math.min(10, v))));
    });
  } catch { return null; }
}

export function validBodySequence(sequence) {
  return Array.isArray(sequence) && sequence.length === LENGTH && sequence.every(frame =>
    Array.isArray(frame) && frame.length === CHANNELS && frame.every(number) &&
    frame.every(v => Math.abs(v) <= 10) && [0, 1].includes(frame[144]) && [0, 1].includes(frame[145]));
}

export function mirrorBodyManual(sequence) {
  if (!validBodySequence(sequence)) throw new Error('Invalid body sequence');
  return sequence.map(frame => {
    const out = frame.slice();
    POSE_MIRROR.forEach((source, target) => {out[target * 2] = -frame[source * 2];out[target * 2 + 1] = frame[source * 2 + 1];});
    for (let side = 0; side < 2; side++) {
      const other = 1 - side;
      out[14 + side * 2] = -frame[14 + other * 2];out[15 + side * 2] = frame[15 + other * 2];
      for (let p = 0; p < 21; p++) for (let axis = 0; axis < 3; axis++) {
        out[18 + side * 63 + p * 3 + axis] = frame[18 + other * 63 + p * 3 + axis] * (axis === 0 ? -1 : 1);
      }
      out[144 + side] = frame[144 + other];
    }
    return out;
  });
}

function weights(parameters) {
  const out = {wrist_weight: 1, shape_weight: .5, pose_weight: .15, missing_cost: .75, ...parameters};
  if (Object.keys(out).some(key => !['wrist_weight', 'shape_weight', 'pose_weight', 'missing_cost'].includes(key)) ||
    Object.values(out).some(v => !number(v) || v < 0)) throw new Error('Invalid body distance weights');
  return out;
}
function rms(a, b, start, end, depth = false) {
  let sum = 0;
  for (let c = start; c < end; c++) {
    const delta = (a[c] - b[c]) * (depth && (c - start) % 3 === 2 ? .5 : 1);
    sum += delta * delta;
  }
  return Math.sqrt(sum / (end - start));
}
export function bodyManualDistances(sequence, references, parameters = {}) {
  if (!validBodySequence(sequence) || !Array.isArray(references) || references.some(ref => !validBodySequence(ref))) throw new Error('Body motion dimensions differ');
  const p = weights(parameters);
  return references.map(reference => {
    let previous = Array(LENGTH + 1).fill(Infinity);previous[0] = 0;
    for (let i = 1; i <= LENGTH; i++) {
      const current = Array(LENGTH + 1).fill(Infinity), a = sequence[i - 1];
      for (let j = Math.max(1, i - 5); j <= Math.min(LENGTH, i + 5); j++) {
        const b = reference[j - 1];
        let cost = p.pose_weight * rms(a, b, 0, 14);
        for (let side = 0; side < 2; side++) {
          cost += (p.wrist_weight * rms(a, b, 14 + side * 2, 16 + side * 2) +
            p.shape_weight * rms(a, b, 18 + side * 63, 81 + side * 63, true)) * a[144 + side] * b[144 + side] +
            p.missing_cost * Number(a[144 + side] !== b[144 + side]);
        }
        current[j] = cost + Math.min(previous[j], current[j - 1], previous[j - 1]);
      }
      previous = current;
    }
    return previous[LENGTH] / LENGTH;
  });
}

export function validBodyManualModel(model) {
  const p = model?.parameters;
  if (model?.version !== 1 || model.featureVersion !== FEATURE_VERSION || !Array.isArray(model.labels) ||
    !model.labels.length || new Set(model.labels).size !== model.labels.length ||
    model.labels.some(label => typeof label !== 'string' || !label || label === 'OTHER MOVEMENT') ||
    !Array.isArray(model.samples) || !model.samples.length || !p || p.mirror !== true ||
    !number(p.maxDistance) || p.maxDistance < 0 || !number(p.minRatio) || p.minRatio < 1 ||
    ![1, 2, 3].includes(p.minVotes) || !number(p.strongRatio) || p.strongRatio < p.minRatio ||
    model.samples.some(sample => !sample || (!model.labels.includes(sample.label) && sample.label !== 'OTHER MOVEMENT') || !validBodySequence(sample.sequence))) return false;
  try {weights(model.featureParameters);return true;} catch {return false;}
}

export function predictBodyManual(model, row) {
  if (!validBodyManualModel(model)) throw new Error('Invalid frozen body model');
  const sequence = tensorizeBodyManual(row);
  if (!sequence) return {prediction: null, tracked: false, distance: null, separation: null, votes: 0};
  const refs = model.samples.map(sample => sample.sequence);
  const direct = bodyManualDistances(sequence, refs, model.featureParameters);
  const reflected = bodyManualDistances(mirrorBodyManual(sequence), refs, model.featureParameters);
  const ranking = model.samples.map((sample, index) => ({label: sample.label, index, distance: Math.min(direct[index], reflected[index])}))
    .sort((a, b) => a.distance - b.distance || a.index - b.index);
  const best = ranking[0], other = ranking.find(sample => sample.label !== best.label);
  const separation = (other?.distance ?? Infinity) / (best.distance + 1e-6);
  const votes = ranking.slice(0, 3).filter(sample => sample.label === best.label).length, p = model.parameters;
  const accepted = model.labels.includes(best.label) && best.distance <= p.maxDistance && separation >= p.minRatio &&
    (votes >= p.minVotes || separation >= p.strongRatio);
  return {prediction: accepted ? best.label : null, tracked: true, distance: best.distance, separation, votes};
}
