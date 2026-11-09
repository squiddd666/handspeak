// The unchanged Holistic graph runs off the camera/UI thread. A transferred
// COPY belongs to the worker; callers retain ownership of their source image.
import {BODY_TRACKING_OPTIONS} from './landmark-capture.js?v=20261108-capture-11';

export async function createHolisticWorkerTracker({
  makeWorker = () => new Worker(new URL('./holistic-body-worker.js?v=20261108-body-worker-1', import.meta.url)),
  copyImage = image => createImageBitmap(image), timeoutMs = 30000,
} = {}) {
  const worker = makeWorker();
  let closed = false, serial = 0, pending = null, busy = false, epoch = 0;
  let callback = () => {}, kind = 'Worker Holistic';
  function stop(error = new Error('Body worker closed')) {
    if (closed) return;
    closed = true;
    if (pending) {clearTimeout(pending.timer); pending.reject(error); pending = null;}
    worker.terminate();
  }
  function request(type, payload = {}, transfers = []) {
    if (closed || pending) return Promise.reject(new Error('Body worker is unavailable'));
    const id = ++serial;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => stop(new Error('Body worker timed out')), timeoutMs);
      pending = {id, type, resolve, reject, timer};
      try {worker.postMessage({type, id, ...payload}, transfers);}
      catch (error) {stop(error);}
    });
  }
  worker.onmessage = ({data}) => {
    if (closed || data.id !== pending?.id) return;
    const p = pending;
    if (data.type === 'error') {stop(new Error(data.message || 'Body worker failed')); return;}
    if (data.type !== (p.type === 'frame' ? 'result' : 'ready')) {
      stop(new Error('Invalid body worker response')); return;
    }
    clearTimeout(p.timer); pending = null; p.resolve(data);
  };
  worker.onerror = event => stop(new Error(event.message || 'Body worker failed'));
  worker.onmessageerror = () => stop(new Error('Body worker result could not be decoded'));
  try {kind = (await request('init', {options: BODY_TRACKING_OPTIONS})).kind;}
  catch (error) {stop(error); throw error;}
  return {
    get kind() {return kind;}, complexity: BODY_TRACKING_OPTIONS.modelComplexity,
    executionContext: 'worker', onResults(fn) {callback = fn;},
    async send({image}) {
      if (closed || busy || pending) throw new Error('Concurrent or closed body worker send');
      busy = true; let bitmap;
      try {
        bitmap = await copyImage(image);
        if (closed) throw new Error('Body worker closed during image copy');
        const width = bitmap.width, height = bitmap.height, expectedEpoch = epoch;
        const response = await request('frame', {bitmap, epoch}, [bitmap]);
        if (closed) throw new Error('Body worker closed');
        if (response.epoch !== expectedEpoch || response.width !== width || response.height !== height ||
            !response.result || typeof response.result !== 'object') {
          const error = new Error('Body worker frame identity differs');stop(error);throw error;
        }
        kind = response.kind; callback(response.result);
      } finally {try {bitmap?.close();} catch {} busy = false;}
    },
    async reset() {
      if (closed || busy || pending) throw new Error('Cannot reset an active body worker');
      busy = true;
      try {await request('reset', {epoch: epoch + 1}); epoch++;}
      finally {busy = false;}
    },
    close: () => stop(),
  };
}
