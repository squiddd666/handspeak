// One Holistic graph for both server vocabularies. Samples are real, unique
// camera frames: countdown results are discarded. Transient, downscaled frames
// are buffered in this tab so a slow tracker cannot skip a short sign. Images
// are released after tracking/cancellation; only landmarks reach the server.
import {trackingSnapshot} from './landmark-frame-geometry.js?v=20261107-padding-1';
const POSE_INDICES = [0, 2, 5, 11, 12, 13, 14];
const CDN = 'https://cdn.jsdelivr.net/npm/@mediapipe/holistic@0.5.1675471629/';
export const BODY_TRACKING_OPTIONS = Object.freeze({
  modelComplexity: 1, smoothLandmarks: true,
  minDetectionConfidence: .5, minTrackingConfidence: .5,
});
let scriptPromise, sharedCapture;

export function recordingDurationMs(value) {
  const seconds = Number(value);
  return [4, 6, 8].includes(seconds) ? seconds * 1000 : 4000;
}

export async function createHolisticBodyTracker() {
  // A worker isolates Tasks' WASM globals and keeps camera sampling responsive.
  let recovery = null, callback = () => {}, input, recoveryResult;
  try {
    const {createWorkerHandRecovery} = await import('./body-hand-recovery.js?v=20261107-recovery-5');
    recovery = await createWorkerHandRecovery();
  } catch (error) {console.warn('Optional hand recovery unavailable; using Holistic.', error);}
  if (!window.Holistic) {
    scriptPromise ||= new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = CDN + 'holistic.js';
      script.onload = resolve;
      script.onerror = () => { scriptPromise = null; reject(new Error('Holistic tracker download failed')); };
      document.head.append(script);
    });
    await scriptPromise;
  }
  const tracker = new window.Holistic({locateFile: file => CDN + file});
  tracker.setOptions(BODY_TRACKING_OPTIONS);
  await tracker.initialize?.();
  tracker.onResults(result => {
    recoveryResult = Promise.resolve().then(() => recovery && input ? recovery.recover(result, input) : result).catch(error => {
      console.warn('Hand recovery stopped; using Holistic.', error);
      try {recovery?.close();} catch {}
      recovery = null;
      return result;
    }).then(callback);
  });
  return {
    get kind() {return recovery ? 'Holistic + same-frame hand recovery' : 'Holistic';}, complexity: BODY_TRACKING_OPTIONS.modelComplexity,
    onResults(fn) {callback = fn;},
    async send({image}) {input = image;recoveryResult = null;try {await tracker.send({image});await recoveryResult;} finally {input = null;}},
    reset() {return tracker.reset?.();},
    close() {try {recovery?.close();} finally {return tracker.close();}},
  };
}

const snapshotCameraFrame = trackingSnapshot;

function points(value, count) {
  if (!Array.isArray(value) || value.length !== count) return null;
  const result = value.map(p => [p.x, p.y, p.z ?? 0]);
  return result.every(p => p.every(Number.isFinite)) ? result : null;
}

export function createLandmarkCapture({
  createTracker = createHolisticBodyTracker, clock = () => performance.now(),
  setTimer = (fn, ms) => setTimeout(fn, ms), clearTimer = id => clearTimeout(id),
  snapshotFrame = snapshotCameraFrame,
} = {}) {
  let tracker, loading, take = null, flight = null, closed = false;
  const active = owner => Boolean(take && take.owner === owner);
  function clearTimers(value) {
    for (const id of value.timers) clearTimer(id);
    value.timers.clear();
  }
  function timer(value, fn, ms) {
    const id = setTimer(() => { value.timers.delete(id); if (take === value) fn(); }, ms);
    value.timers.add(id);
    return id;
  }
  function cancel(owner) {
    if (!take || (owner !== undefined && take.owner !== owner)) return;
    const prior = take;
    take = null;
    clearTimers(prior);
    for (const packet of prior.queue.splice(0)) packet.snapshot?.dispose?.();
    // A canceled send may finish later; its tagged result cannot enter a new take.
    prior.onCancel?.();
  }
  function fail(value, error) {
    if (take !== value) return;
    take = null;
    clearTimers(value);
    for (const packet of value.queue.splice(0)) packet.snapshot?.dispose?.();
    if (flight && /timed out/.test(String(error?.message || error))) {
      const stalled = tracker;
      flight = null;tracker = null;loading = null;
      try { Promise.resolve(stalled?.close?.()).catch(() => {}); } catch {}
    }
    value.onError(error instanceof Error ? error : new Error(String(error)));
  }
  function metrics(value) {
    return {frames: value.frames.length, trackedFrames: value.frames.length,
      processedFrames: value.processedFrames, warmupFrames: value.warmups,
      poseWarmupFrames: value.poseWarmups,
      poseFrames: value.poseFrames, handFrames: value.handFrames, fallbackFrames: value.fallbackFrames,
      paddingFrames: value.paddingFrames,
      sampledFrames: value.sampledFrames, peakBufferedFrames: value.peakBufferedFrames,
      trackingInput: value.trackingInput, transientFrameStorage: 'tab memory only; released after processing',
      durationMs: Math.round(clock() - value.start),
      recordingWindowMs: value.durationMs, tracker: tracker?.kind || 'Holistic',
      trackerComplexity: tracker?.complexity ?? BODY_TRACKING_OPTIONS.modelComplexity};
  }
  function complete(value) {
    if (take !== value) return;
    take = null;
    clearTimers(value);
    const info = metrics(value);
    // Retain full temporal coverage if a faster machine exceeds the API limit.
    const frames = value.frames.length <= 90 ? value.frames : Array.from({length: 90}, (_, i) =>
      value.frames[Math.round(i * (value.frames.length - 1) / 89)]);
    value.onComplete(frames, info);
  }
  function drain(value) {
    if (take !== value || value.phase !== 'recording') return;
    value.phase = 'draining';
    value.onPhase('draining');
    if (!flight && !value.queue.length) { complete(value); return; }
    pump(value);
    timer(value, () => fail(value, new Error('Tracking stopped: captured camera frames timed out. Try again.')), 25000);
  }
  function startRecording(value) {
    if (take !== value || !value.countdownDone || !value.poseWarmups || flight) return;
    if (!value.isRunning()) { fail(value, new Error('Start the camera and try again.')); return; }
    value.phase = 'recording';
    value.start = clock();
    value.deadline = value.start + value.durationMs;
    value.lastAt = -Infinity;
    value.lastVideoTime = -1;
    value.onPhase('recording');
    timer(value, () => drain(value), value.durationMs);
  }
  function onResults(model, result) {
    const packet = flight, value = packet?.take;
    if (!value || take !== value || packet.model !== model || packet.received) return;
    packet.received = true;
    // The tracker sees only uniform-padding removal. Models and overlay keep
    // the original camera coordinate system (including wrist-relative depth).
    result = packet.snapshot?.restore?.(result) || result;
    const left = points(result.leftHandLandmarks, 21);
    const right = points(result.rightHandLandmarks, 21);
    value.onTracking?.({landmarks: [result.leftHandLandmarks, result.rightHandLandmarks].filter((_, i) => i ? right : left),
      tracker: packet.model.kind || 'Holistic', delegate: packet.model.delegate});
    if (packet.phase === 'countdown') {
      value.warmups++;
      // A completed blank result does not mean the pose-guided hand tracker
      // is ready. Wait for an actual finite body pose before starting the take.
      value.poseWarmups += Boolean(points(result.poseLandmarks, 33));
      return;
    }
    if (packet.phase !== 'recording' || packet.at > value.deadline) return;
    value.processedFrames++;
    value.paddingFrames += Boolean(packet.snapshot?.cropped);
    const pose = points(result.poseLandmarks, 33);
    value.poseFrames += Boolean(pose);value.handFrames += Boolean(left || right);
    value.fallbackFrames += Boolean(result.usedHandFallback);
    if (pose && (left || right)) value.frames.push({pose: POSE_INDICES.map(i => pose[i]), left, right});
  }
  async function begin({owner, isRunning, onPhase, onComplete, onError, onCancel, onTracking, durationMs = 4000}) {
    if (closed) throw new Error('Body tracker is closed. Reload the page.');
    cancel();
    const value = {owner, isRunning, onPhase, onComplete, onError, onCancel, onTracking,
      phase: 'loading', durationMs: Math.min(8000, Math.max(2500, durationMs)),
      frames: [], timers: new Set(), warmups: 0, poseWarmups: 0, processedFrames: 0, poseFrames: 0, handFrames: 0, fallbackFrames: 0, paddingFrames: 0,
      queue: [], sampledFrames: 0, peakBufferedFrames: 0, trackingInput: null,
      countdownDone: false, lastAt: -Infinity, lastVideoTime: -1};
    take = value;
    onPhase('loading');
    timer(value, () => fail(value, new Error('Body tracker loading timed out. Reload and try again.')), 30000);
    try {
      loading ||= Promise.resolve().then(createTracker).then(model => {
        tracker = model;
        tracker.onResults(result => onResults(model, result));
        return model;
      }).catch(error => { loading = null; throw error; });
      await loading;
      if (take !== value) return false;
      // An earlier/canceled take must finish before the temporal pose graph is
      // reset. Otherwise a stale ROI/smoothing state can prevent the next take
      // from detecting a new signer or a changed camera view during warm-up.
      await flight?.done;
      if (take !== value) return false;
      await tracker.reset?.();
      if (take !== value) return false;
      clearTimers(value);
      if (!isRunning()) { fail(value, new Error('Start the camera and try again.')); return false; }
      value.phase = 'countdown';
      onPhase('countdown');
      timer(value, () => { value.countdownDone = true; startRecording(value); }, 1500);
      timer(value, () => {
        if (value.phase === 'countdown') fail(value, new Error('Body tracker could not warm up. Keep your upper body visible and try again.'));
      }, 15000);
      return true;
    } catch (error) { fail(value, error); return false; }
  }
  function dispatch(packet) {
    const value = packet.take;
    packet.model = tracker;
    flight = packet;
    packet.done = Promise.resolve().then(() => packet.model.send({image: packet.snapshot?.image || packet.video,
      ...(packet.model.usesTimestamp ? {timestamp: packet.at} : {})})).catch(error => {
      fail(value, new Error(`Tracking stopped: ${error.message || error}`));
    }).finally(() => {
      packet.snapshot?.dispose?.();
      if (flight === packet) flight = null;
      if (take !== value) return;
      if (value.phase === 'draining' && !value.queue.length) complete(value);
      else if (value.queue.length) pump(value);
      else if (value.phase === 'countdown') startRecording(value);
    });
  }
  function pump(value) {
    if (take !== value || !tracker || flight || !value.queue.length) return;
    dispatch(value.queue.shift());
  }
  function frame(owner, now, video) {
    const value = take;
    if (!value || value.owner !== owner) return;
    if (!value.isRunning()) { fail(value, new Error('Start the camera and try again.')); return; }
    // The deadline is checked BEFORE the busy check, and also has its own timer.
    if (value.phase === 'recording' && now >= value.deadline) { drain(value); return; }
    const interval = value.phase === 'recording' ? Math.max(50, value.durationMs / 80) : 65;
    if (!tracker || !['countdown', 'recording'].includes(value.phase) || now - value.lastAt < interval) return;
    if (value.phase === 'countdown' && flight) return;
    if (value.phase === 'recording' && value.sampledFrames >= 80) return;
    if (video.readyState < 2 || video.currentTime === value.lastVideoTime) return;
    value.lastAt = now;
    value.lastVideoTime = video.currentTime;
    const packet = {take: value, phase: value.phase, at: now, received: false};
    if (value.phase === 'countdown') {
      try {
        packet.snapshot = snapshotFrame(video);
        // Preserve the old full-resolution warm-up when no padding exists.
        // Only a genuinely padded image needs a frozen cropped warm-up.
        if (!packet.snapshot.cropped) {
          packet.snapshot.dispose?.();packet.snapshot = null;packet.video = video;
        }
        dispatch(packet);
      } catch (error) {fail(value, error);}
      return;
    }
    try {
      packet.snapshot = snapshotFrame(video);
      value.sampledFrames++;
      value.trackingInput = packet.snapshot.dimensions || value.trackingInput;
      value.queue.push(packet);
      value.peakBufferedFrames = Math.max(value.peakBufferedFrames, value.queue.length);
      pump(value);
    } catch (error) {fail(value, error);}
  }
  function close() {
    closed = true;
    cancel();
    try { Promise.resolve(tracker?.close?.()).catch(() => {}); } catch {}
  }
  return {begin, frame, cancel, active, close};
}

export function sharedLandmarkCapture(options) {
  if (!sharedCapture) {
    sharedCapture = createLandmarkCapture(options);
    window.addEventListener('pagehide', () => sharedCapture.close(), {once: true});
  }
  return sharedCapture;
}
