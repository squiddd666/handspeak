/** Check the real Watch & practice functions without a browser/GPU. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync, existsSync} from 'node:fs';
import vm from 'node:vm';

const root = new URL('../', import.meta.url);
const text = (name) => readFileSync(new URL(name, root), 'utf8');
const html = text('index.html'), source = text('sign-examples.js');
const manifest = JSON.parse(text('scripts/studio-galt-sources.json'));
const clips = JSON.parse(text('media/avatar/clips/index.json')).signs;
const newWords = manifest.clips.filter((entry) => entry.learningOnly);
const learning = new Set(newWords.map((entry) => entry.id));
const noReference = new Set(newWords.filter((entry) => !entry.referenceVideo).map((entry) => entry.id));
const silentConsole = {warn() {}};
const authoredSource = text('sign-animations.js').replace(/^export /gm, '');
const authored = vm.runInNewContext(`${authoredSource}\nSIGN_ANIMATIONS;`);
const catalog = JSON.parse(text('models/motion-vocabulary.json'));
const packs = JSON.parse(text('models/motion-categories/index.json')).groups;
const published = catalog.items.filter((item) => packs.some((pack) =>
  pack.labels?.includes(item.label) && item.cameraGroups?.includes(pack.id)));
const staticIds = [...html.matchAll(/data-sign-example="([a-z0-9-]+)"/g)].map((match) => match[1]);
const allIds = [...new Set([...staticIds, ...published.map((item) => item.id)])];
const filledIds = ['fish', 'pain', 'see', 'sick', 'night'];
const videoSupport=()=>({referenceExamples:new Map(),referenceOnlySelection:()=>false,
  setReferenceLayout(){},learningOnly:id=>learning.has(id),hasRecognitionModel:()=>false,
  isLocalReferenceHost:()=>true,recognitionBadge:()=>'',referenceStatus:()=> 'Reference video only',avatar:null,
  document:{querySelector:()=>null}});

function extract(start, end) {
  const a = source.indexOf(start), b = source.indexOf(end, a + start.length);
  assert.ok(a >= 0 && b > a, `missing UI function ${start}`);
  return source.slice(a, b);
}
function element(id, label = id.toUpperCase()) {
  return {
    dataset: {signExample: id, signLabel: label}, attributes: {}, hidden: false,
    children: [], textContent: label, style: {},
    setAttribute(name, value) {this.attributes[name] = value;},
    removeAttribute(name) {delete this.attributes[name];},
    toggleAttribute(name, value) {if (value) this.attributes[name] = ''; else delete this.attributes[name];},
    querySelector() {return this.children[0] || null;},
    append(child) {this.children.push(child);},
  };
}

test('four new, distinct learning-only buttons match shipped mocap and reference metadata', () => {
  assert.deepEqual([...learning].sort(), ['brother', 'buy', 'bye', 'my']);
  for (const entry of newWords) {
    const buttons = [...html.matchAll(/<button\b([^>]*)>([^<]*)<\/button>/g)]
      .filter((match) => match[1].includes(`data-sign-example="${entry.id}"`));
    assert.equal(buttons.length, 1);
    const [button] = buttons;
    assert.equal(button[2], entry.label);
    assert.match(button[1], /\bdata-mocap-only\b/);
    assert.equal(/\bdata-no-reference\b/.test(button[1]), !entry.referenceVideo);
    assert.match(button[1], /aria-pressed="false"/);
    assert.equal(clips[entry.id].learningOnly, true);
    assert.ok(existsSync(new URL(`media/avatar/clips/${clips[entry.id].file}`, root)));
    if (entry.referenceVideo) assert.ok(existsSync(new URL(entry.referenceVideo, root)));
  }
  for (const id of ['hello', 'please']) assert.match(html, new RegExp(`data-sign-example="${id}"`));
  assert.match(html, /id="signExampleReferenceNote"/);
});

test('47 quick examples preserve Kai playback; the four newly supplied recordings are reference-only', async () => {
  const played = [], references = [], status = {}, playback = {};
  const player = {setSpeed() {}, play(id) {played.push(id);}};
  const play = vm.runInNewContext(`let playbackRevision=0;
    ${extract('async function playSign(', '\nfunction chooseSign(')}\nplaySign;`, {
    ...videoSupport(),referenceOnlySelection:id=>Boolean(catalog.items.find(item=>item.id===id)?.referenceOnly),
    referenceExamples:new Map(catalog.items.map(item=>[item.id,item])),
    ensureAvatar: () => player, playback, status, label: 'BYE', speed: {value: '0.5'}, mocapOnly: learning,
    playReferenceVideo: (id) => references.push(id), hasSignAnimation: (id) => Boolean(authored[id]),
    hasSkeletalClip: async (id) => Boolean(clips[id]?.file), hasReferenceClip: async () => false, video: {getAttribute:()=> 'reference.mp4'},
  });
  assert.equal(staticIds.length, 42);
  assert.equal(allIds.length, 47);
  assert.deepEqual(published.map((entry) => entry.id).sort(), [...filledIds].sort());
  for (const id of allIds) {
    assert.ok(authored[id]?.frames?.length || clips[id]?.file, `${id} lacks a Kai motion`);
    if (clips[id]?.file) assert.ok(existsSync(new URL(`media/avatar/clips/${clips[id].file}`, root)));
    await play(id);
  }
  const kaiIds=allIds.filter(id=>!catalog.items.find(item=>item.id===id)?.referenceOnly);
  assert.deepEqual(played, kaiIds);
  assert.deepEqual(allIds.filter(id=>!kaiIds.includes(id)).sort(),['baby','love','name','want']);
  await play('unavailable');
  assert.equal(played.length, kaiIds.length);
  assert.match(status.textContent, /unavailable/);
  assert.equal(playback.hidden, false);
});

test('the real catalog loader publishes the five newly animated buttons without changing camera packs', async () => {
  const buttons = staticIds.map((id) => element(id));
  const added = [], selected = [], publishedExamples = new Map();
  const load = vm.runInNewContext(`let publishedPacks=[],libraryId=null;
    ${extract('async function loadPublishedExamples(', '\nvoid loadPublishedExamples(')}\nloadPublishedExamples;`, {
    ...videoSupport(),
    buttons, publishedExamples, fetch: async (url) => ({ok: true, json: async () => url.includes('vocabulary') ? catalog : {groups: packs}}),
    loadVocabularySettings: async () => ({}), applyVocabularySettings: (items) => items,
    updateAccuracy() {}, instructions() {}, chooseSign: (id) => selected.push(id),
    document: {
      querySelector: () => ({append: (button) => added.push(button)}),
      createElement: () => ({dataset: {}, setAttribute() {}, addEventListener(event, callback) {this.click = callback;}}),
    },
  });
  await load();
  assert.equal(buttons.length, 47);
  assert.deepEqual(added.map((button) => button.dataset.signExample).sort(), [...filledIds].sort());
  for (const button of added) button.click();
  assert.deepEqual(selected, added.map((button) => button.dataset.signExample));
  for (const id of filledIds) {
    assert.equal(publishedExamples.get(id).recognition, 'category-preview');
    assert.deepEqual(publishedExamples.get(id).cameraGroups, ['pack-dtw']);
    assert.equal(clips[id].learningOnly, false, 'keep the existing experimental camera preview');
  }
});

function pendingPlayback() {
  const played = [], requests = [], video = {pause() {}, onloadeddata: null, onerror: null};
  const avatar = {pause() {}, setSpeed() {}, play(id) {played.push(id); return true;}};
  const api = vm.runInNewContext(`let playbackRevision=0;
    ${extract('function pauseAll(', '\nfunction speedLabel(')}
    ${extract('async function playSign(', '\nfunction chooseSign(')}
    ({playSign,pauseAll});`, {
    ...videoSupport(),
    avatar, video, ensureAvatar: () => avatar, playback: {}, status: {}, label: 'FISH', speed: {value: '1'},
    mocapOnly: learning, hasSignAnimation: () => false, playReferenceVideo() {},
    hasSkeletalClip: (id) => new Promise((resolve) => requests.push({id, resolve})),
  });
  return {...api, played, requests};
}

test('late availability checks cannot restart Kai after leaving the preview', async () => {
  const ui = pendingPlayback(), pending = ui.playSign('fish');
  ui.pauseAll();
  ui.requests[0].resolve(true);
  assert.equal(await pending, false);
  assert.deepEqual(ui.played, []);
});

test('late availability checks cannot play the previous word after a newer selection', async () => {
  const ui = pendingPlayback(), old = ui.playSign('fish'), next = ui.playSign('sick');
  ui.requests[1].resolve(true);
  assert.equal(await next, true);
  ui.requests[0].resolve(true);
  assert.equal(await old, false);
  assert.deepEqual(ui.played, ['sick']);
});

test('replay always uses the selected word, not a stale avatar clip', () => {
  const code = source.match(/querySelector\('#signExampleReplay'\)\.addEventListener\('click',\(\)=>\{([\s\S]*?)\n\}\);/);
  assert.ok(code);
  const played = [];
  vm.runInNewContext(code[1], {selectedId: 'sick', avatar: {currentId: 'hello'}, playSign: (id) => played.push(id)});
  assert.deepEqual(played, ['sick']);
});

test('skeletal format is not mislabeled as mocap; authored demos retain an approximation label', () => {
  const avatar = {approximate: true, usingSkeletal: true, mocap: false};
  const status = vm.runInNewContext(`${extract('function motionStatus(', '\nfunction videoSrcFor(')}\nmotionStatus;`, {
    ...videoSupport(),
    avatar, label: 'FISH', speedLabel: () => 'Normal speed', video: null, videoPanel: null,
    mocapStatus: () => 'Studio Galt ASL mocap',
  });
  assert.match(status(), /Kai hand-authored approximation/);
  assert.doesNotMatch(status(), /mocap|matched|synced/);
  avatar.approximate = false;
  assert.match(status(), /Kai 3D skeletal animation/);
  assert.doesNotMatch(status(), /mocap/);
  avatar.mocap = true;
  assert.equal(status(), 'Studio Galt ASL mocap');
});

test('watching any quick example never prepares a model; learning-only selection hides camera practice', () => {
  const practice = {}, mode = {}, prepared = [], played = [];
  const buttons = [...newWords.map((entry) => element(entry.id)), element('hello')];
  const ui = vm.runInNewContext(`let label='HELLO', selection=0, libraryId=null, coreId=null;
    ${extract('function chooseSign(', '\nfunction chooseCorePractice(')}
    ({chooseSign, selected: () => libraryId});`, {
    ...videoSupport(),
    buttons, mocapOnly: learning, cameraWords: new Map(), coreWords: new Map(), CORE_SENTINEL: 'capstone-core',
    pauseAll() {}, showLesson() {}, instructions() {}, updateAccuracy() {},
    preparePractice: (id) => prepared.push(id), playSign: (id) => played.push(id),
    document: {querySelector: (selector) => selector === '#signExamplePractice' ? practice : mode},
  });
  for (const entry of newWords) {
    ui.chooseSign(entry.id, buttons.find((button) => button.dataset.signExample === entry.id));
    assert.equal(practice.hidden, true);
    assert.equal(ui.selected(), entry.id);
  }
  assert.deepEqual(prepared, []);
  assert.deepEqual(played, newWords.map((entry) => entry.id));
  ui.chooseSign('hello', buttons.at(-1));
  assert.equal(practice.hidden, false);
  assert.deepEqual(prepared, []);
});

test('new instructions remain learning-only even if an unrelated catalog lists a camera pack', () => {
  const mode = {};
  const instructions = vm.runInNewContext(`${extract('function instructions(', '\nfunction ensureAvatar(')}\ninstructions;`, {
    ...videoSupport(),
    buttons: [element('bye'), element('hello')], mocapOnly: learning,
    publishedExamples: new Map([['bye', {label: 'BYE'}]]), daily: new Set(), extra: new Set(),
    document: {querySelector: () => mode}, wordSettings: () => ({}),
  });
  instructions('bye');
  assert.match(mode.textContent, /Learning example only/);
  assert.match(mode.textContent, /Camera-recognition models are unchanged/);
  assert.doesNotMatch(mode.textContent, /Automatic capture|Experimental word preview/);
  instructions('hello');
  assert.match(mode.textContent, /Select Practice at camera/);
});

test('new button badges and accuracy text cannot imply newly measured recognition accuracy', () => {
  const target = {}, buttons = newWords.map((entry) => element(entry.id));
  const update = vm.runInNewContext(`${extract('function updateAccuracy(', '\nfunction preparePractice(')}\nupdateAccuracy;`, {
    ...videoSupport(),
    label: 'BYE', libraryId: 'bye', coreId: null, coreWords: new Map(), coreAccuracy: {},
    mocapOnly: learning, buttons, exampleAccuracy: () => ({correct: 99, total: 100}),
    validAccuracy: () => true, accuracyText: () => '99%',
    document: {querySelector: () => target, createElement: () => element('badge')},
  });
  update();
  assert.match(target.textContent, /3D learning example only/);
  assert.doesNotMatch(target.textContent, /99%/);
  for (const button of buttons) {
    assert.equal(button.children[0].textContent, '3D demo · learning only');
    assert.match(button.title, /No new camera-recognition model/);
  }
});

test('missing reference video becomes a clean Kai-only view; a real reference restores comparison', () => {
  const panel = element('panel'), compare = element('compare'), note = element('note');
  const synced = [];
  const video = {
    src: './media/signs/hello.mp4', readyState: 0, paused: false, loaded: 0,
    pause() {this.paused = true;}, load() {this.loaded++;},
    getAttribute(name) {return this[name] || null;}, removeAttribute(name) {delete this[name];},
  };
  const play = vm.runInNewContext(`${extract('function playReferenceVideo(', '\nfunction showLesson(')}\nplayReferenceVideo;`, {
    ...videoSupport(),
    video, playbackRevision: 0, videoPanel: panel, withoutReference: noReference, avatar: {setSyncVideo: (el) => synced.push(el)},
    videoSrcFor: (id) => `./media/signs/${id}.mp4`, syncVideoRate() {},
    document: {querySelector: (selector) => selector === '#signExampleCompare' ? compare : note},
    console: silentConsole,
  });
  play('bye');
  assert.equal(panel.hidden, true);
  assert.equal(note.hidden, false);
  assert.equal(compare.attributes['data-mocap-only'], '');
  assert.equal(video.src, undefined);
  assert.equal(video.paused, true);
  assert.equal(synced.at(-1), null);
  play('brother');
  assert.equal(panel.hidden, false);
  assert.equal(note.hidden, true);
  assert.equal(compare.attributes['data-mocap-only'], undefined);
  assert.equal(video.src, './media/signs/brother.mp4');
  assert.equal(synced.at(-1), video);
});

test('a delayed reference-video callback cannot autoplay after pause or overwrite a newer reference', () => {
  let plays = 0;
  const video = {
    readyState: 0, videoWidth: 100, videoHeight: 200, dataset: {},
    pause() {}, load() {}, play() {plays++;},
    getAttribute(name) {return this[name] || null;}, removeAttribute(name) {delete this[name];},
  };
  const panel = element('panel');
  const ui = vm.runInNewContext(`let playbackRevision=0;
    ${extract('function pauseAll(', '\nfunction speedLabel(')}
    ${extract('function playReferenceVideo(', '\nfunction showLesson(')}
    ({playReferenceVideo,pauseAll});`, {
    ...videoSupport(),
    video, videoPanel: panel, withoutReference: noReference, avatar: {pause() {}, setSyncVideo() {}},
    videoSrcFor: (id) => `./media/signs/${id}.mp4`, syncVideoRate() {}, refreshMirrorStatus() {}, setTimeout() {},
    document: {querySelector: () => element('note')},
  });
  ui.playReferenceVideo('fish');
  const oldLoad = video.onloadeddata, oldError = video.onerror;
  ui.pauseAll();
  ui.playReferenceVideo('sick');
  oldLoad(); oldError();
  assert.equal(plays, 0);
  assert.equal(video.src, './media/signs/sick.mp4');
  assert.equal(panel.attributes['data-missing'], undefined);
  video.onloadeddata();
  assert.equal(plays, 1);
});

test('every new mocap word has the expected safe external lesson link', () => {
  const lesson = {};
  const show = vm.runInNewContext(`${extract('function showLesson(', '\nfunction instructions(')}\nshowLesson;`, {
    ...videoSupport(),
    mocapOnly: learning, lesson,
  });
  for (const entry of newWords) {
    show(entry.id, entry.label);
    assert.equal(lesson.hidden, false);
    assert.equal(lesson.href, entry.lessonUrl);
    assert.match(lesson.textContent, /Signing Savvy/);
  }
});

test('all five filled words have their own ASL lesson links and keep their reference videos', () => {
  const lessons = vm.runInNewContext(`${extract('const lifeprintLessons=', '\n// The 7 words')}\nlifeprintLessons;`);
  const lesson = {};
  const show = vm.runInNewContext(`${extract('function showLesson(', '\nfunction instructions(')}\nshowLesson;`, {
    ...videoSupport(),
    mocapOnly: learning, cameraWords: new Map(), lifeprintLessons: lessons, lesson,
  });
  for (const id of filledIds) {
    show(id, id.toUpperCase());
    assert.equal(lesson.hidden, false);
    assert.equal(lesson.href, clips[id].lessonUrl);
    assert.match(lesson.href, /^https:\/\/www\.lifeprint\.com\/asl101\/pages-signs\//);
    assert.equal(clips[id].referenceVideo, `media/signs/${id}.mp4`);
    assert.ok(existsSync(new URL(clips[id].referenceVideo, root)));
  }
});

test('the live catalog shell is refreshed while the verified Kai module version is retained', () => {
  assert.match(text('index.html'), /sign-examples\.js\?v=20261107-motion-release-1/);
  for (const path of ['sign-examples.js', 'sign-avatar.js', 'sign-clips.js', 'sign-reference.js']) {
    assert.match(text(path), /20261105-reference-3/);
    assert.doesNotMatch(text(path), /20261105-reference-[12](?:['"]|\b)/);
    assert.doesNotMatch(text(path), /20261105-studio-galt-3/);
  }
});
