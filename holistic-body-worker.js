// Classic worker: the legacy Solutions WASM loader uses importScripts and
// already supports OffscreenCanvas. No window/document emulation is needed.
const CDN = 'https://cdn.jsdelivr.net/npm/@mediapipe/holistic@0.5.1675471629/';
let tracker, recovery, epoch = 0, active = false, bodyResult;
const kind = () => recovery ? 'Worker Holistic + same-frame hand recovery' : 'Worker Holistic';
self.onmessage = async ({data}) => {
  if (active) {
    data.bitmap?.close();
    self.postMessage({type: 'error', id: data.id, message: 'Concurrent body worker request'}); return;
  }
  active = true;
  try {
    if (data.type === 'init') {
      const {BODY_TRACKING_OPTIONS} = await import('./landmark-capture.js?v=20261108-capture-11');
      const {preferredVisionDelegate} = await import('./camera-performance.js');
      const {bindLegacyWorkerContext, legacyCpuInference} = await import('./legacy-holistic-worker-context.js?v=20261108-body-worker-1');
      if (JSON.stringify(data.options) !== JSON.stringify(BODY_TRACKING_OPTIONS)) throw new Error('Body options changed');
      // Recovery remains a separate IMAGE graph, on exactly the same image.
      try {
        const {createWorkerHandRecovery} = await import('./body-hand-recovery.js?v=20261108-recovery-6');
        recovery = await createWorkerHandRecovery();
      } catch (error) {console.warn('Optional worker recovery unavailable:', error.message);}
      importScripts(CDN + 'holistic.js');
      // The Solutions worker branch does not forward locateFile to the packed
      // assets loader (the page branch does). Pin its .data/WASM URLs too.
      self.createMediapipeSolutionsPackedAssets = {locateFile: file => CDN + file};
      tracker = new self.Holistic({locateFile: file => CDN + file});
      tracker.setOptions({...BODY_TRACKING_OPTIONS,
        useCpuInference: legacyCpuInference(preferredVisionDelegate(() => new OffscreenCanvas(1, 1)), self.navigator)});
      await tracker.initialize();
      bindLegacyWorkerContext(tracker, self.VERSION);
      tracker.onResults(result => {bodyResult = result;});
    } else if (data.type === 'reset') {
      if (!tracker || data.epoch !== epoch + 1) throw new Error('Invalid body graph reset');
      await tracker.reset(); epoch = data.epoch;
    } else if (data.type === 'frame') {
      try {
        if (!tracker || data.epoch !== epoch) throw new Error('Stale body worker frame');
        const width = data.bitmap.width, height = data.bitmap.height;
        bodyResult = null; await tracker.send({image: data.bitmap});
        if (!bodyResult) throw new Error('Missing Holistic result');
        let result = bodyResult;
        if (recovery) {
          try {result = await recovery.recover(result, data.bitmap);}
          catch (error) {recovery.close(); recovery = null; console.warn('Recovery stopped:', error.message);}
        }
        // Images, masks and unused face output never cross back to the UI.
        // Anatomical pose/hand coordinates and fallback metadata are unmodified.
        const output = {};
        for (const key of ['poseLandmarks', 'leftHandLandmarks', 'rightHandLandmarks', 'usedHandFallback']) {
          if (result[key] !== undefined) output[key] = result[key];
        }
        self.postMessage({type: 'result', id: data.id, epoch, width, height, kind: kind(), result: output});
        return;
      } finally {
        // Legacy Solutions can allocate an output ImageBitmap even though the
        // app consumes only landmarks. Release it after recovery has finished.
        for (const key of ['image', 'segmentationMask']) {
          if (bodyResult?.[key] !== data.bitmap) {try {bodyResult?.[key]?.close?.();} catch {}}
        }
        data.bitmap.close(); bodyResult = null;
      }
    } else throw new Error('Unknown body worker request');
    self.postMessage({type: 'ready', id: data.id, epoch, kind: kind()});
  } catch (error) {self.postMessage({type: 'error', id: data.id, message: String(error.stack || error.message || error)});}
  finally {active = false;}
};
