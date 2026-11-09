// Preserve the trained Holistic pose/hand features. If its hand ROI loses a
// hand, use the existing Tasks hand detector on the SAME frozen input frame.
// No additional detector runs when Holistic already supplies both hands.
import {createHolisticBodyTracker} from './landmark-capture.js?v=20261107-capture-4';

export function associateBodyHands(pose, hands) {
  if (!pose?.[15] || !pose?.[16]) return {leftHandLandmarks: null, rightHandLandmarks: null};
  const candidates = (hands || []).filter(h => h?.length === 21).slice(0, 2);
  const distance = (hand, wrist) => (hand[0].x - wrist.x) ** 2 + (hand[0].y - wrist.y) ** 2;
  if (candidates.length === 1) {
    const left = distance(candidates[0], pose[15]) <= distance(candidates[0], pose[16]);
    return {leftHandLandmarks: left ? candidates[0] : null, rightHandLandmarks: left ? null : candidates[0]};
  }
  if (candidates.length === 2) {
    const direct = distance(candidates[0], pose[15]) + distance(candidates[1], pose[16]);
    const swapped = distance(candidates[1], pose[15]) + distance(candidates[0], pose[16]);
    return {leftHandLandmarks: candidates[direct <= swapped ? 0 : 1], rightHandLandmarks: candidates[direct <= swapped ? 1 : 0]};
  }
  return {leftHandLandmarks: null, rightHandLandmarks: null};
}

export async function createHybridBodyTracker({getHandTracker, createHolistic = createHolisticBodyTracker,
  createCanvas = () => document.createElement('canvas')} = {}) {
  const pose = await createHolistic();
  const canvas = createCanvas(), ctx = canvas.getContext('2d');
  let callback = () => {}, timestamp = 0;
  pose.onResults(result => {
    const primary = [result.leftHandLandmarks, result.rightHandLandmarks];
    if (result.poseLandmarks && primary.some(h => !h?.length)) {
      const handTracker = getHandTracker();
      if (handTracker) {
        const hands = handTracker.detectForVideo(canvas, timestamp);
        const fallback = associateBodyHands(result.poseLandmarks, hands.landmarks);
        let used = false;
        for (const [key, other] of [['leftHandLandmarks', 'rightHandLandmarks'], ['rightHandLandmarks', 'leftHandLandmarks']]) {
          const candidate = fallback[key], known = result[other];
          // Never duplicate the same observed hand to fill a missing hand slot.
          const duplicate = candidate && known && (candidate[0].x - known[0].x) ** 2 + (candidate[0].y - known[0].y) ** 2 < .0004;
          if (!result[key]?.length && candidate && !duplicate) {result[key] = candidate; used = true;}
        }
        result.usedHandFallback = used;
      }
    }
    callback(result);
  });
  return {kind: 'hybrid-body', usesTimestamp: true, complexity: 1,
    onResults(fn) {callback = fn;},
    async send({image, timestamp: at}) {
      timestamp = at;
      canvas.width = image.videoWidth;canvas.height = image.videoHeight;
      ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
      await pose.send({image: canvas});
    },
    close() {pose.close();},
  };
}
