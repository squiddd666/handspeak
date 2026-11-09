// Recover hands that Holistic's pose-guided ROI misses, on the SAME frozen
// image. This dedicated IMAGE-mode detector never shares live VIDEO timestamps.
// Anatomical pose wrists, not screen X or a selected word, establish the slots.
const VISION = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/';
const MODEL = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task';
const SIDES = [['leftHandLandmarks', 15, 19], ['rightHandLandmarks', 16, 20]];
const valid = hand => Array.isArray(hand) && hand.length === 21 && hand.every(p =>
  Number.isFinite(p.x) && Number.isFinite(p.y) && Number.isFinite(p.z ?? 0));
const distance = (a, b, width, height) => Math.hypot((a.x - b.x) * width, (a.y - b.y) * height);

export function imageSize(image) {
  return [image.videoWidth || image.width || 0, image.videoHeight || image.height || 0];
}

export function restoreCrop(hand, crop, width, height) {
  if (!valid(hand)) return null;
  return hand.map(p => ({...p, x: (crop.x + p.x * crop.width) / width,
    y: (crop.y + p.y * crop.height) / height, z: (p.z ?? 0) * crop.width / width}));
}

export function wristCrop(pose, wristIndex, fingerIndex, width, height) {
  const wrist = pose?.[wristIndex], finger = pose?.[fingerIndex];
  if (!wrist || (wrist.visibility ?? 1) < .35 || !Number.isFinite(wrist.x + wrist.y)
    || wrist.x < 0 || wrist.x > 1 || wrist.y < 0 || wrist.y > 1) return null;
  const span = pose?.[11] && pose?.[12] ? distance(pose[11], pose[12], width, height) : 0;
  if (!Number.isFinite(span) || span < 20) return null;
  const useFinger = finger && (finger.visibility ?? 1) >= .35 && Number.isFinite(finger.x + finger.y);
  const cx = (wrist.x * .7 + (useFinger ? finger.x : wrist.x) * .3) * width;
  const cy = (wrist.y * .7 + (useFinger ? finger.y : wrist.y) * .3) * height;
  const size = Math.max(96, Math.min(Math.min(width, height) * .6, span * .85));
  const x = Math.max(0, Math.floor(cx - size / 2)), y = Math.max(0, Math.floor(cy - size / 2));
  const right = Math.min(width, Math.ceil(cx + size / 2)), bottom = Math.min(height, Math.ceil(cy + size / 2));
  return right - x >= 32 && bottom - y >= 32 ? {x, y, width: right - x, height: bottom - y} : null;
}

export function recoverSlots(result, candidates, width, height) {
  const pose = result.poseLandmarks;
  if (!pose?.[11] || !pose?.[12] || !pose?.[15] || !pose?.[16]) return result;
  const span = Math.max(20, distance(pose[11], pose[12], width, height));
  if (!Number.isFinite(span)) return result;
  const known = SIDES.map(([key]) => result[key]).filter(valid);
  const unique = [];
  for (const hand of candidates.filter(valid)) {
    if (distance(hand[0], hand[9], width, height) < 4) continue;
    if ([...known, ...unique].some(h => distance(h[0], hand[0], width, height) < span * .1)) continue;
    unique.push(hand);
  }
  const missing = SIDES.filter(([key, wrist]) => !valid(result[key]) && (pose[wrist].visibility ?? 1) >= .35);
  // Global one-to-one matching: crossing hands cannot fill both slots with one detection.
  let best = {cost: Infinity, assignment: []};
  function visit(i, used, assignment, cost) {
    if (i === missing.length) {if (cost < best.cost) best = {cost, assignment};return;}
    visit(i + 1, used, [...assignment, -1], cost + .9);
    unique.forEach((hand, j) => {
      const d = distance(hand[0], pose[missing[i][1]], width, height) / span;
      if (!used.has(j) && d <= .9) visit(i + 1, new Set([...used, j]), [...assignment, j], cost + d);
    });
  }
  visit(0, new Set(), [], 0);
  const repaired = {...result};
  best.assignment.forEach((j, i) => {if (j >= 0) {repaired[missing[i][0]] = unique[j];repaired.usedHandFallback = true;}});
  return repaired;
}

export async function createHandRecovery({vision, files, createCanvas = () => document.createElement('canvas')} = {}) {
  vision ||= await import(VISION + '+esm');
  files ||= await vision.FilesetResolver.forVisionTasks(VISION + 'wasm');
  const make = delegate => vision.HandLandmarker.createFromOptions(files, {
    baseOptions: {modelAssetPath: MODEL, delegate}, runningMode: 'IMAGE', numHands: 2,
    minHandDetectionConfidence: .35, minHandPresenceConfidence: .35, minTrackingConfidence: .5,
  });
  let detector;
  try {detector = await make('GPU');} catch {detector = await make('CPU');}
  const canvas = createCanvas(), ctx = canvas.getContext('2d', {alpha: false});
  return {
    recover(result, image) {
      if (!result.poseLandmarks || SIDES.every(([key]) => valid(result[key]))) return result;
      const [width, height] = imageSize(image);
      if (!width || !height) return result;
      let recovered = recoverSlots(result, detector.detect(image).landmarks || [], width, height);
      // A resting second hand is often legitimately absent. Crop recovery is
      // reserved for a complete loss, not an extra detector on every one-hand sign.
      for (const [key, wrist, finger] of SIDES) {
        if (SIDES.some(([side]) => valid(recovered[side]))) break;
        if (valid(recovered[key])) continue;
        const crop = wristCrop(result.poseLandmarks, wrist, finger, width, height);
        if (!crop) continue;
        canvas.width = crop.width;canvas.height = crop.height;
        ctx.drawImage(image, crop.x, crop.y, crop.width, crop.height, 0, 0, crop.width, crop.height);
        const hands = (detector.detect(canvas).landmarks || []).map(h => restoreCrop(h, crop, width, height));
        recovered = recoverSlots(recovered, hands, width, height);
      }
      return recovered;
    },
    close() {detector.close();canvas.width = 0;canvas.height = 0;},
  };
}

export async function createWorkerHandRecovery() {
  // Tasks' WASM loader uses importScripts(), so use a classic worker with a
  // dynamic module import rather than an unsupported module-worker loader.
  const worker = new Worker('./hand-recovery-worker.js?v=20261107-recovery-4');
  let sequence = 0, pending = null, stopped = false;
  let resolveReady, rejectReady;
  const ready = new Promise((resolve, reject) => {resolveReady = resolve;rejectReady = reject;});
  const loading = setTimeout(() => rejectReady(new Error('Hand recovery loading timed out')), 20000);
  worker.onerror = event => {
    const error = new Error(event.message || 'Hand recovery worker failed');
    clearTimeout(loading);rejectReady(error);
    if (pending) {clearTimeout(pending.timer);pending.reject(error);pending = null;}
  };
  worker.onmessage = ({data}) => {
    if (data.type === 'ready') {clearTimeout(loading);resolveReady();return;}
    if (data.type === 'error') {
      clearTimeout(loading);rejectReady(new Error(data.message));
      if (pending) {clearTimeout(pending.timer);pending.reject(new Error(data.message));pending = null;}
      return;
    }
    if (data.id === pending?.id) {clearTimeout(pending.timer);pending.resolve(data.result);pending = null;}
  };
  worker.postMessage({type: 'init'});
  try {await ready;} catch (error) {clearTimeout(loading);worker.terminate();throw error;}
  return {
    async recover(result, image) {
      if (!result.poseLandmarks || SIDES.some(([key]) => valid(result[key]))) return result;
      if (stopped || pending) throw new Error('Hand recovery is unavailable');
      const bitmap = await createImageBitmap(image);
      if (stopped) {bitmap.close();throw new Error('Hand recovery stopped');}
      const id = ++sequence;
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {pending = null;reject(new Error('Hand recovery frame timed out'));}, 5000);
        pending = {id, resolve: value => resolve({...result, ...value}), reject, timer};
        try {
          worker.postMessage({type: 'frame', id, bitmap, result: {poseLandmarks: result.poseLandmarks,
            leftHandLandmarks: result.leftHandLandmarks, rightHandLandmarks: result.rightHandLandmarks}}, [bitmap]);
        } catch (error) {clearTimeout(timer);pending = null;bitmap.close();reject(error);}
      });
    },
    close() {stopped = true;clearTimeout(loading);if (pending) {clearTimeout(pending.timer);pending.reject(new Error('Hand recovery stopped'));pending = null;}worker.terminate();},
  };
}
