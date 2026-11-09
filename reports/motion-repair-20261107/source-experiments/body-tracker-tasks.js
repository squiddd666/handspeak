// Tasks pose + hand inference on the SAME video frame. Pose wrists establish
// anatomical left/right, independent of mirrored preview CSS or hand category
// names. Unlike Holistic's hand ROI, the hand detector can reacquire fast hands.
const FULL_POSE = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task';

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

export async function createTaskBodyTracker({vision, files, getHandTracker, preferredDelegate = 'GPU'}) {
  const make = delegate => vision.PoseLandmarker.createFromOptions(files, {
    baseOptions: {modelAssetPath: FULL_POSE, delegate}, runningMode: 'VIDEO', numPoses: 1,
    minPoseDetectionConfidence: .5, minPosePresenceConfidence: .5, minTrackingConfidence: .5,
    outputSegmentationMasks: false,
  });
  let pose, delegate = preferredDelegate, callback = () => {};
  try { pose = await make(delegate); }
  catch (error) { if (delegate === 'CPU') throw error; delegate = 'CPU'; pose = await make(delegate); }
  return {kind: 'tasks-body', complexity: 1, delegate,
    onResults(fn) {callback = fn;},
    async send({image, timestamp}) {
      const handTracker = getHandTracker();
      if (!handTracker) throw new Error('Hand tracker is unavailable. Stop and restart the camera.');
      const result = pose.detectForVideo(image, timestamp);
      const hands = handTracker.detectForVideo(image, timestamp);
      const landmarks = result.landmarks?.[0];
      callback({poseLandmarks: landmarks, ...associateBodyHands(landmarks, hands.landmarks)});
    },
    close() {pose.close();},
  };
}
