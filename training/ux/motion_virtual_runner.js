/* Optional diagnostic fixture runner. Drives only the normal visible controls;
 * never invokes model internals, changes predictions, or adds reviewed words.
 * The separate virtual-source bootstrap enforces no physical camera access.
 */
(() => {
  'use strict';
  const config = window.HANDSPEAK_VIRTUAL_FIXTURE;
  if (!config?.runnerSha256 || location.hostname !== '127.0.0.1') return;
  const $ = id => document.getElementById(id);
  const byId = new Map(config.items.map(item => [item.id, item]));
  const ledger = () => JSON.parse($('vcReport').textContent);
  let running = false, stop = false;
  const route = item => {
    if (item.recognition === 'daily-preview') return 'daily-manual';
    if (['default-preview', 'existing-preview'].includes(item.recognition) || item.cameraGroups.length) return 'motion-manual';
    if (item.recognition === 'beginner-preview') return 'beginner';
    if (item.recognitionModes.includes('capstone-full')) return 'capstone';
    return 'beginner';
  };
  const setChecked = (id, value) => {
    const node = $(id);
    if (!node || node.disabled) throw new Error(id + ' is unavailable');
    if (node.checked !== value) {node.checked = value; node.dispatchEvent(new Event('change', {bubbles: true}));}
  };
  const wait = (predicate, timeout = 15000) => new Promise((resolve, reject) => {
    const start = performance.now();
    const tick = () => {
      if (stop) {reject(new Error('Stopped through the fixture controls')); return;}
      if (predicate()) {resolve(); return;}
      if (performance.now() - start >= timeout) {reject(new Error('The app did not reach the expected visible capture state')); return;}
      setTimeout(tick, 100);
    };
    tick();
  });
  async function run() {
    if (running) return;
    running = true;stop = false;$('vcRun').disabled = true;$('vcStopRun').disabled = false;
    try {
      if (!$('vcSafety').textContent.includes('VIRTUAL-ONLY READY')) throw new Error('Virtual-only marker missing');
      const previous = ledger();
      if (previous.attempts.some(a => !a.finishedAt)) throw new Error('An existing take is unfinished');
      const completed = new Set(previous.attempts.filter(a => a.stage === 'baseline 1×').map(a => a.id));
      const explicit = $('vcRunIds').value.trim().split(/[\s,]+/).filter(Boolean);
      if (explicit.some(id => !byId.has(id))) throw new Error('An ID is not in the verified reference manifest');
      const ids = (explicit.length ? explicit : config.items.map(i => i.id)).filter(id => !completed.has(id));
      if (!ids.length) throw new Error('No untested normal-speed labels selected');
      if ($('simpleViewButton').getAttribute('aria-pressed') === 'true') $('simpleViewButton').click();
      setChecked('automaticWords', false);setChecked('faceTrackingToggle', false);
      $('vcStage').value = 'baseline 1×';$('vcRate').value = '1';
      for (let i = 0; i < ids.length; i++) {
        const item = byId.get(ids[i]), family = route(item);
        $('vcRunStatus').textContent = `Running ${i + 1}/${ids.length} · ${item.label} · ${family}`;
        const link = document.querySelector('.example-camera-link');
        link.click();
        $('signExampleSearch').value = item.label;
        $('signExampleSearch').dispatchEvent(new Event('input', {bubbles: true}));
        await wait(() => Boolean(document.querySelector(`[data-sign-example="${item.id}"]`)));
        document.querySelector(`[data-sign-example="${item.id}"]`).click();
        await wait(() => document.querySelector('[data-sign-example][aria-pressed="true"]')?.dataset.signExample === item.id);
        $('vcArm').click();
        await wait(() => $('vcPhase').textContent.startsWith(item.label + ' armed.'));
        // A long-lived canvas capture stream can keep an obsolete decoded
        // image after switching portrait/landscape clips. Rebind only this
        // isolated virtual stream through the public camera controls; never
        // substitute a prediction or change production capture/model code.
        if (config.restartVirtualStreamEachReference) {
          if ($('cameraButton').textContent.includes('Stop camera')) $('cameraButton').click();
          await wait(() => $('cameraButton').textContent.includes('Start camera'));
          $('cameraButton').click();
          await wait(() => $('cameraButton').textContent.includes('Stop camera'));
        }
        // Use the normal app's longer recording option for longer references.
        // Playback remains at 1×; this never alters or selects a model result.
        if (['capstone','beginner'].includes(family) && $('serverCaptureSeconds')) {
          const seconds = Number($('vcSourceInfo').textContent.match(/· ([\d.]+)s/)?.[1] || 0);
          $('serverCaptureSeconds').value = String(seconds <= 3.8 ? 4 : seconds <= 5.8 ? 6 : 8);
          $('serverCaptureSeconds').dispatchEvent(new Event('change', {bubbles: true}));
        }
        $('signExamplePractice').click();
        await wait(() => $('recognitionMode').value === 'words');
        setChecked('automaticWords', false);
        let record;
        if (family === 'capstone') {
          const mode = item.recognitionModes.includes('capstone-core') ? 'core' : item.recognitionModes.includes('capstone-extended') ? 'extended' : 'full';
          const count = {core: 7, extended: 19, full: 100}[mode];
          await wait(() => $('capstoneVocabMode').value === mode && $('capstoneStatus').textContent.startsWith(`${count}-word ${mode} vocabulary ready`));
          setChecked('capstoneConsent', true);record = $('capstoneRecord');
        } else if (family === 'beginner') {
          setChecked('beginnerConsent', true);record = $('beginnerRecord');
        } else {
          await wait(() => family === 'daily-manual' ? $('researchWordsToggle').checked : !$('researchWordsToggle').checked);
          // researchWordsToggle is the public five-word processing consent;
          // there is no separate researchWordsConsent control in the app.
          if (item.cameraGroups.length) await wait(() => item.cameraGroups.includes($('cameraVocabulary').value) && /preview:/.test($('vocabularyCameraStatus').textContent));
          record = $('wordCaptureButton');
        }
        await wait(() => !record.disabled);
        const number = ledger().attempts.length + 1;
        record.click();
        await wait(() => {
          if (!$('vcPhase').textContent.startsWith(item.label + ': ')) return false;
          const last = ledger().attempts.at(-1);
          return last?.number === number && Boolean(last.finishedAt);
        }, 55000);
        const last = ledger().attempts.at(-1);
        if (last.id !== item.id || last.family !== family) throw new Error('Recorded route/reference identity differs from the public Practice route');
        if (config.auditCheckpoint) {
          const saved = await fetch(config.auditCheckpoint.endpoint, {method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-Motion-Audit': config.auditCheckpoint.token},
            body: JSON.stringify(ledger())});
          if (!saved.ok || (await saved.json()).saved !== number) throw new Error('Scalar checkpoint failed; stop before losing more outcomes');
        }
        if (stop) break;
      }
      const result = ledger().attempts.filter(a => a.stage === 'baseline 1×' && a.finishedAt);
      $('vcRunStatus').textContent = `Completed · ${result.length}/198 labels · ${result.filter(a => a.correct).length} matched · ${result.filter(a => !a.correct && a.predicted).length} wrong · ${result.filter(a => !a.predicted).length} no match`;
      // Stop only this fixture stream. No user-owned camera or draft is involved.
      if ($('cameraButton').textContent.includes('Stop camera')) $('cameraButton').click();
    } catch (error) {
      $('vcRunStatus').textContent = 'Needs attention · ' + error.message + '. Existing attempts are preserved; no blind re-recording.';
    } finally {running = false;$('vcRun').disabled = false;$('vcStopRun').disabled = true;}
  }
  document.addEventListener('DOMContentLoaded', () => {
    const section = document.createElement('section');section.id = 'vcRunner';
    section.innerHTML = '<h3>Reference batch test · virtual camera only</h3><p>This explicitly drives Watch → Practice → Record through the existing app. It never selects an expected result or clicks Add reviewed word. Current normal-speed attempts are kept; a resumed run skips already tested labels.</p><label>Optional reference IDs (comma separated)<input id="vcRunIds" placeholder="Blank = all 198 labels"></label> <button id="vcRun" type="button">Run selected reference tests</button> <button id="vcStopRun" type="button" disabled>Stop batch</button><p id="vcRunStatus" role="status">Ready · no batch started.</p>';
    $('vcPanel').append(section);
    const download = document.createElement('button');
    download.id = 'vcDownload';download.type = 'button';download.textContent = 'Download scalar test report';
    section.append(download);
    download.addEventListener('click', () => {
      const blob = new Blob([JSON.stringify(ledger(), null, 2) + '\n'], {type: 'application/json'});
      const url = URL.createObjectURL(blob), link = document.createElement('a');
      link.href = url;link.download = 'motion-virtual-camera-report.json';link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
    $('vcRun').addEventListener('click', () => void run());
    $('vcStopRun').addEventListener('click', () => {
      stop = true;
      const data = ledger(), current = data.attempts.at(-1);
      if (current && !current.finishedAt) {
        $(current.family === 'capstone' ? 'capstoneCancel' : current.family === 'beginner' ? 'beginnerCancel' : current.family === 'daily-manual' ? 'researchCancel' : 'motionCancel')?.click();
      }
      $('vcBlank').click();
    });
  });
})();
