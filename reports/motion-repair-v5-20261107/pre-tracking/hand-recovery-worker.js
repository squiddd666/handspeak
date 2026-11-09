// Isolated Tasks WASM globals, and no synchronous hand inference on the UI
// thread: the camera can keep sampling while a difficult frozen frame drains.
let recovery;
self.onmessage = async ({data}) => {
  try {
    if (data.type === 'init') {
      const {createHandRecovery} = await import('./body-hand-recovery.js?v=20261107-recovery-4');
      recovery = await createHandRecovery({createCanvas: () => new OffscreenCanvas(1, 1)});
      self.postMessage({type: 'ready'});
    } else if (data.type === 'frame') {
      try {
        const result = recovery.recover(data.result, data.bitmap);
        self.postMessage({type: 'result', id: data.id, result});
      } finally {data.bitmap.close();}
    }
  } catch (error) {self.postMessage({type: 'error', id: data.id, message: String(error.message || error)});}
};
