/* Diagnostic-only source. Embedded BEFORE app modules by the fixture generator.
 * Does not click app controls, invoke a real camera, replace model predictions,
 * store landmarks, or change the normal index.html.
 */
(() => {
  'use strict';
  const config = window.HANDSPEAK_VIRTUAL_FIXTURE;
  if (!config || location.hostname !== '127.0.0.1') {
    if (navigator.mediaDevices) navigator.mediaDevices.getUserMedia = async () => {
      throw new Error('This virtual-only fixture requires the isolated loopback host.');
    };
    throw new Error('Virtual fixture refused a non-isolated host.');
  }
  const memory = () => {
    const values = new Map();
    return {
      get length() { return values.size; },
      key: i => [...values.keys()][i] ?? null,
      getItem: k => values.get(String(k)) ?? null,
      setItem: (k, v) => values.set(String(k), String(v)),
      removeItem: k => values.delete(String(k)),
      clear: () => values.clear(),
    };
  };
  Object.defineProperty(window, 'localStorage', {value: memory()});
  Object.defineProperty(window, 'sessionStorage', {value: memory()});
  const canvas = document.createElement('canvas');
  canvas.width = config.width;
  canvas.height = config.height;
  const ctx = canvas.getContext('2d', {alpha: false});
  const source = document.createElement('video');
  source.muted = true;
  source.playsInline = true;
  source.preload = 'auto';
  source.loop = false;
  source.controls = true;
  const items = new Map(config.items.map(item => [item.id, item]));
  const report = {
    schema: 1, startedAt: new Date().toISOString(),
    scope: 'Watch & Learn reference-clip smoke tests through the actual live capture pipeline. Not independent held-out or live-user accuracy.',
    geometry: {width: canvas.width, height: canvas.height, fps: 30, fit: 'contain/letterbox', cropping: false, pixelFlip: false},
    isolation: {host: location.hostname, storage: 'in-memory only', realCameraCalls: 0, microphoneCalls: 0, getUserMediaCalls: 0},
    indexSha256: config.indexSha256, bootstrapSha256: config.bootstrapSha256,
    runtimeSha256: config.runtimeSha256 || {}, runnerSha256: config.runnerSha256 || null,
    activeModelSha256: config.activeModelSha256 || {}, calibrationSha256: config.calibrationSha256 || null,
    activeAuxiliaryModelSha256: config.activeAuxiliaryModelSha256 || {},
    recognitionLabels: config.items.length, attempts: [],
  };
  let panel, armed = null, active = null, blank = true, drawing = true, drawFrames = 0;
  let phase = 'Virtual-only ready. Select a Watch word and arm its clip.';
  let armRevision = 0;
  const $ = id => document.getElementById(id);
  const text = id => $(id)?.textContent || '';
  const checked = id => Boolean($(id)?.checked);
  function paint() {
    if (!drawing) return;
    ctx.fillStyle = '#101010';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    if (!blank && source.readyState >= 2 && source.videoWidth && source.videoHeight) {
      const scale = Math.min(canvas.width / source.videoWidth, canvas.height / source.videoHeight);
      const w = source.videoWidth * scale, h = source.videoHeight * scale;
      ctx.drawImage(source, (canvas.width - w) / 2, (canvas.height - h) / 2, w, h);
    }
    drawFrames++;
  }
  paint();
  const drawingTimer = setInterval(paint, 1000 / 30);
  // No call or fallback to the original camera API exists in this fixture.
  if (!navigator.mediaDevices || !canvas.captureStream) throw new Error('Virtual stream APIs unavailable.');
  Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {configurable: true, value: async constraints => {
    if (constraints?.audio) throw new Error('Microphone access is prohibited in this fixture.');
    if (!panel || !$('vcSafety')?.textContent.includes('VIRTUAL-ONLY READY')) throw new Error('Virtual-only marker not ready.');
    report.isolation.getUserMediaCalls++;
    render();
    return canvas.captureStream(30);
  }});
  const realFetch = window.fetch.bind(window);
  const endpoints = new Set(['/api/capstone-asl', '/api/beginner-asl', '/api/research-words']);
  window.fetch = async (input, init) => {
    const url = new URL(typeof input === 'string' ? input : input.url, location.href);
    const method = (init?.method || input?.method || 'GET').toUpperCase();
    // Opt-in, token-authorized scalar checkpoint on the separate local audit
    // server. Production has no such endpoint. All other writes stay blocked.
    const checkpoint = config.auditCheckpoint;
    if (checkpoint && url.origin === location.origin && method === 'POST'
        && url.pathname === '/__motion_audit__/checkpoint' && checkpoint.endpoint === url.pathname
        && init?.headers?.['X-Motion-Audit'] === checkpoint.token) return realFetch(input, init);
    if (url.origin === location.origin && method !== 'GET' && method !== 'HEAD' && !endpoints.has(url.pathname)) {
      throw new Error('Diagnostic isolation blocks unrelated server writes.');
    }
    const take = method === 'POST' && endpoints.has(url.pathname) ? active : null;
    if (take) {
      try {
        const body = JSON.parse(init?.body || '{}');
        // Only scalar counts survive; raw coordinates are not retained.
        take.request = {endpoint: url.pathname, frames: body.frames?.length ?? null,
          sequenceFrames: body.sequence?.length ?? null, vocabulary: body.vocabulary ?? null};
      } catch { take.request = {endpoint: url.pathname, invalidBody: true}; }
    }
    try {
      const response = await realFetch(input, init);
      if (take) {
        // Clone only for scalar telemetry; leave the app's response untouched.
        response.clone().json().then(data => {
          take.response = {httpStatus: response.status, lowConfidence: Boolean(data.lowConfidence),
            label: data.label ?? null, vocabulary: data.vocabulary ?? null,
            predictions: (data.predictions || []).map(p => ({label: p.label, score: p.score ?? p.confidence ?? null})),
            suggestions: (data.suggestions || []).map(p => ({label: p.label, score: p.score ?? null})),
            rejectionReason: data.rejectionReason ?? null, minScore: data.minScore ?? null,
            minMargin: data.minMargin ?? null, vocabularyMass: data.vocabularyMass ?? null,
            model: data.model ?? null, checkpointSha256: data.checkpointSha256 ?? null,
             auxiliarySha256: data.auxiliarySha256 ?? null, auxiliaryWeight: data.auxiliaryWeight ?? null,
             auxiliaryFeatureVersion: data.auxiliaryFeatureVersion ?? null,
            preprocessorVersion: data.preprocessorVersion ?? null, calibrationId: data.calibrationId ?? null,
            error: data.error ?? null};
          render();
        }).catch(() => {});
      }
      return response;
    } catch (error) {
      if (take) { take.requestError = error.name + ': ' + error.message; render(); }
      throw error;
    }
  };
  function diagnostic() {
    try {
      const data = JSON.parse(text('cameraDiagnostics'));
      const last = data.lastCapture;
      return {trackerState: data.trackerState, delegate: data.delegate, input: data.input,
        processedFps: data.processedFps, rawHands: data.rawHands, usableHands: data.usableHands,
        vocabulary: data.vocabulary, extraWords: data.extraWords, serverPreview: data.serverPreview,
        automaticWords: data.automaticWords, faceTracking: data.faceTracking,
        lastCapture: last ? {capture: last.capture, frames: last.frames, trackedFrames: last.trackedFrames,
          durationMs: last.durationMs, recordingWindowMs: last.recordingWindowMs, processedFrames: last.processedFrames,
          sampledFrames: last.sampledFrames, peakBufferedFrames: last.peakBufferedFrames, trackingInput: last.trackingInput,
          warmupFrames: last.warmupFrames, poseFrames: last.poseFrames, handFrames: last.handFrames,
          fallbackFrames: last.fallbackFrames, tracker: last.tracker,
          paddingFrames: last.paddingFrames,
          trackerComplexity: last.trackerComplexity, validSequence: last.validSequence, match: last.match ?? null} : null};
    } catch { return {unavailable: true}; }
  }
  function prediction(take) {
    const response = take.response;
    if (response) return response.predictions?.[0]?.label || response.label || null;
    const word = take.events.filter(e => !['—', 'No reliable match', 'Not enough frames', 'Hands not tracked', 'Capture incomplete'].includes(e.word)).at(-1)?.word;
    return word || null;
  }
  function closeTake(reason) {
    if (!active) return;
    const take = active;
    active = null;
    clearTimeout(take.timeout);
    delete take.timeout;
    source.pause(); blank = true; paint();
    take.finishedAt = new Date().toISOString();
    take.elapsedMs = Math.round(performance.now() - take.startClock);
    delete take.startClock;
    take.endReason = reason;
    take.sourceAtEnd = {time: source.currentTime, duration: source.duration, paused: source.paused,
      ended: source.ended, readyState: source.readyState, drawFrames: drawFrames - take.drawFramesStart};
    take.status = text(take.statusId);
    take.camera = diagnostic();
    take.predicted = prediction(take);
    const normalize = value => String(value || '').replace(/[12]$/, '').replace(/[-/]+/g, ' ').replace(/\s+/g, ' ').trim().toUpperCase();
    take.correct = take.stage !== 'warm-up discard' && normalize(take.predicted) === normalize(take.label);
    phase = `${take.label}: ${take.stage === 'warm-up discard' ? 'warm-up discarded' : take.correct ? 'MATCH' : take.predicted ? 'WRONG MATCH: ' + take.predicted : 'NO MATCH'} · ${take.status}`;
    render();
  }
  function render() {
    if (!panel) return;
    $('vcPhase').textContent = phase;
    $('vcSourceInfo').textContent = armed
      ? `${armed.item.label} · ${armed.item.video} · ${source.videoWidth}×${source.videoHeight} · ${Number(source.duration || 0).toFixed(2)}s · ${armed.rate}× · ${armed.stage}`
      : 'No clip armed.';
    $('vcSourceState').textContent = `Decoder: ${source.currentTime.toFixed(2)}/${Number(source.duration || 0).toFixed(2)}s · ready ${source.readyState} · ${source.paused ? 'paused' : 'playing'} · canvas ${blank ? 'blank' : 'clip'} · ${drawFrames} draws`;
    const tests = report.attempts.filter(a => a.stage !== 'warm-up discard' && a.finishedAt);
    const labels = new Set(tests.map(a => a.id));
    const baseline = tests.filter(a => a.stage === 'baseline 1×');
    $('vcSummary').textContent = `${labels.size}/${config.items.length} labels tested · ${baseline.filter(a => a.correct).length}/${baseline.length} baseline attempts matched · ${report.isolation.getUserMediaCalls} virtual streams · 0 physical camera calls`;
    const rows = $('vcRows'); rows.replaceChildren();
    for (const take of report.attempts.slice(-8).reverse()) {
      const row = document.createElement('tr');
      const cells = [take.number, take.label, take.family + (take.vocabulary ? '/' + take.vocabulary : ''), take.stage,
        take.finishedAt ? (take.predicted || take.endReason) : 'In progress', take.finishedAt ? (take.stage === 'warm-up discard' ? 'Discarded' : take.correct ? 'Match' : 'Failed') : 'Recording'];
      for (const cell of cells) { const td = document.createElement('td'); td.textContent = String(cell); row.append(td); }
      rows.append(row);
    }
    $('vcReport').textContent = JSON.stringify(report, null, 2);
  }
  async function arm() {
    if (active) { phase = 'Finish or stop the current attempt first.'; render(); return; }
    const revision = ++armRevision;
    const button = document.querySelector('[data-sign-example][aria-pressed="true"]');
    const item = items.get(button?.dataset.signExample);
    const watch = $('signExampleVideo');
    if (!item || !watch?.getAttribute('src') || new URL(watch.getAttribute('src'), location.href).pathname !== '/' + item.video.replace(/^\.\//, '')) {
      phase = 'Select an enabled recognition word in Watch & Learn first; its exact primary clip must be visible.'; render(); return;
    }
    const rate = Number($('vcRate').value);
    const stage = $('vcStage').value;
    if (stage === 'baseline 1×' && rate !== 1) { phase = 'Baseline requires normal 1× speed. Label a slower run as a separate retry.'; render(); return; }
    armed = {item, rate, stage, ready: false};
    source.pause(); blank = true;
    source.src = watch.getAttribute('src');
    source.playbackRate = rate;
    phase = `Loading ${item.label}…`; render();
    try {
      await new Promise((resolve, reject) => {
        source.onloadeddata = resolve;
        source.onerror = () => reject(new Error('Primary clip could not load.'));
        source.load();
      });
      if (revision !== armRevision) return;
      // A fixed 35%-timeline frame offers a repeatable warm-up; no cropping.
      source.currentTime = stage === 'warm-up discard' ? source.duration * .35 : 0;
      blank = false;
      armed.ready = true;
      paint();
      phase = `${item.label} armed. Use Practice at camera, then the actual app Record button.`;
    } catch (error) { phase = error.message; armed = null; blank = true; }
    render();
  }
  function beginTake(family, statusId) {
    if (!armed?.ready || active) return;
    const take = {number: report.attempts.length + 1, id: armed.item.id, label: armed.item.label,
      clip: armed.item.video, clipSha256: armed.item.videoSha256,
      family, vocabulary: family === 'capstone' ? $('capstoneVocabMode')?.value : null,
      stage: armed.stage, rate: armed.rate, sourceDuration: source.duration,
      sourceDimensions: [source.videoWidth, source.videoHeight], statusId,
      startedAt: new Date().toISOString(), startClock: performance.now(), drawFramesStart: drawFrames,
      events: [], statuses: [], playbackStarted: false};
    report.attempts.push(take); active = take;
    take.timeout = setTimeout(() => closeTake('timeout / incomplete capture'), 45000);
    phase = `${take.label}: waiting for the app's recording window (${family}).`; render();
  }
  function startPlayback() {
    if (!active || active.playbackStarted) return;
    active.playbackStarted = true;
    active.playbackStartedAt = new Date().toISOString();
    blank = false;
    if (active.stage !== 'warm-up discard') {
      source.currentTime = 0;
      source.playbackRate = active.rate;
      source.play().catch(error => { active && (active.playbackError = error.message); closeTake('video playback blocked'); });
    }
    phase = `${active.label}: ${active.stage === 'warm-up discard' ? 'holding warm-up frame' : 'playing the exact Watch clip'} through the virtual stream.`;
    render();
  }
  source.addEventListener('ended', () => {
    if (active) { active.playbackEndedAt = new Date().toISOString(); active.completeSourcePlayed = true; }
    blank = true; paint();
    if (active?.family.endsWith('-automatic')) {
      setTimeout(() => { if (active?.family.endsWith('-automatic')) closeTake('automatic observation window ended'); }, 6500);
    }
    render();
  });
  document.addEventListener('handspeak:camera-match', event => {
    if (!active) return;
    const {word, model} = event.detail || {};
    active.events.push({at: new Date().toISOString(), word, model});
    render();
  });
  document.addEventListener('click', event => {
    const id = event.target.closest('button')?.id;
    if (id === 'capstoneRecord') beginTake('capstone', 'capstoneStatus');
    else if (id === 'beginnerRecord') beginTake('beginner', 'beginnerStatus');
    else if (['wordCaptureButton', 'motionRecognize', 'researchRecord'].includes(id)) {
      beginTake(checked('researchWordsToggle') ? 'daily-manual' : 'motion-manual', checked('researchWordsToggle') ? 'researchWordsStatus' : 'motionHelp');
    } else if (['capstoneCancel', 'beginnerCancel', 'motionCancel', 'researchCancel'].includes(id)) closeTake('canceled through app');
  }, true);
  document.addEventListener('DOMContentLoaded', () => {
    const style = document.createElement('style');
    style.textContent = '#vcPanel{margin:16px auto;padding:16px;max-width:1400px;border:2px solid #72e8b4;background:#11251f;color:#fff;border-radius:10px;font:14px system-ui}#vcPanel label{display:inline-block;margin:5px 12px 5px 0}#vcPanel button,#vcPanel select{background:#f8fff9;color:#14271d;padding:6px 10px;border:1px solid #7c9e8d;border-radius:5px}#vcPanel p{margin:6px 0;max-width:none;font:inherit;color:inherit}#vcPanel h2{font:700 20px system-ui;margin:0 0 8px}#vcPanel table{width:100%;text-align:left;font:12px system-ui}#vcPanel th,#vcPanel td{padding:3px 8px}#vcPanel pre{max-height:280px;overflow:auto;white-space:pre-wrap;font:11px monospace}#vcCanvasSlot{float:right;display:flex;gap:8px}#vcCanvas,#vcDecoder{width:200px;height:150px;border:1px solid #75ae8b}#vcPanel:after{content:"";display:block;clear:both}';
    document.head.append(style);
    panel = document.createElement('section'); panel.id = 'vcPanel';
    panel.setAttribute('aria-label', 'In-page virtual camera diagnostics');
    panel.innerHTML = '<h2 id="vcSafety">VIRTUAL-ONLY READY · physical camera and microphone never called</h2><p>Isolated local test fixture. Normal app capture and prediction code is unchanged. Reference checks are not live-user accuracy.</p><div id="vcCanvasSlot"></div><label>Test stage <select id="vcStage"><option value="baseline 1×">Baseline 1×</option><option value="warm-up discard">Warm-up discard</option><option value="slow retry">Slow retry (separate)</option></select></label><label>Virtual playback rate <select id="vcRate"><option value="1">1× normal</option><option value="0.5">0.5× slow</option><option value="0.35">0.35× diagnostic</option></select></label><button id="vcArm" type="button">Arm selected Watch clip</button> <button id="vcPlay" type="button">Play armed clip for Automatic words</button> <button id="vcBlank" type="button">Blank virtual source</button><p id="vcSourceInfo"></p><p id="vcSourceState"></p><p id="vcPhase" role="status"></p><p id="vcSummary" role="status"></p><table aria-label="Latest virtual-camera attempts"><thead><tr><th>Attempt</th><th>Expected</th><th>Capture model</th><th>Condition</th><th>Prediction / result</th><th>Outcome</th></tr></thead><tbody id="vcRows"></tbody></table><details><summary>Full scalar-only test report</summary><pre id="vcReport"></pre></details>';
    document.body.prepend(panel); canvas.id = 'vcCanvas'; canvas.setAttribute('aria-label', 'Virtual source only');
    source.id = 'vcDecoder'; source.setAttribute('aria-label', 'Reference clip decoder for virtual camera');
    $('vcCanvasSlot').append(source, canvas);
    $('vcArm').addEventListener('click', () => void arm());
    $('vcBlank').addEventListener('click', () => { source.pause(); blank = true; paint(); closeTake('blanked through fixture'); phase = 'Virtual source blank.'; render(); });
    $('vcPlay').addEventListener('click', () => {
      if (!checked('automaticWords')) { phase = 'Enable Automatic words through the app first.'; render(); return; }
      beginTake(checked('researchWordsToggle') ? 'daily-automatic' : 'motion-automatic', checked('researchWordsToggle') ? 'researchWordsStatus' : 'motionHelp');
      startPlayback();
    });
    const ids = ['capstoneStatus', 'beginnerStatus', 'motionHelp', 'researchWordsStatus'];
    const observer = new MutationObserver(() => {
      if (!active) return;
      const value = text(active.statusId);
      if (value !== active.statuses.at(-1)?.text) active.statuses.push({at: new Date().toISOString(), text: value});
      const recording = active.family === 'capstone' || active.family === 'beginner'
        ? /^Recording for (?:four|[468]) seconds/.test(value)
        : /^Recording(…| your movement)/.test(value);
      if (recording) startPlayback();
      const terminal = /Possible match:|No confident|No prediction|No reliable match|Not enough|Captured \d+|recognition.*timed out|Recognition timed out|Tracking stopped:|Could not load|tracker.*(?:timed out|could not warm up)|Capture incomplete:|Hands captured, but|request timed out|word model is not ready|Select Words in motion/i.test(value);
      if (terminal && !active.family.endsWith('-automatic')) {
        // Let the unmodified fetch response and app status settle before reading.
        const take = active;
        setTimeout(() => { if (active === take) closeTake('app terminal status'); }, 100);
      }
      render();
    });
    for (const id of ids) if ($(id)) observer.observe($(id), {childList: true, characterData: true, subtree: true});
    render();
    const telemetryTimer = setInterval(render, 1000);
    window.addEventListener('pagehide', () => clearInterval(telemetryTimer), {once: true});
  });
  window.addEventListener('pagehide', () => { drawing = false; clearInterval(drawingTimer); source.pause(); });
})();
