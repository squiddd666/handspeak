/** Cover the complete Watch & Learn selector without camera or project writes. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {hasRecognitionModel} from '../recognition-library.js';

const root=new URL('../',import.meta.url);
const read=path=>readFileSync(new URL(path,root),'utf8');
const source=read('sign-examples.js'),html=read('index.html');
const catalog=JSON.parse(read('models/motion-vocabulary.json'));
const index=JSON.parse(read('models/motion-categories/index.json'));
const manifest=JSON.parse(read('models/recognition-videos.json'));
const a=source.indexOf('function filterExampleButtons(){'),b=source.indexOf('\nvoid loadPublishedExamples();',a);
assert.ok(a>=0&&b>a);
const selector=source.slice(a,b);
function node(){
  return {dataset:{},attributes:{},textContent:'',hidden:false,children:[],handlers:{},
    setAttribute(name,value){this.attributes[name]=value;},
    addEventListener(name,fn){this.handlers[name]=fn;},
    append(child){this.children.push(child);}};
}
function ui({indexFails=false,catalogFails=false,hidden=[],libraryId=null}={}){
  const buttons=[...html.matchAll(/<button\b([^>]*)data-sign-example="([^"]+)"([^>]*)>([^<]*)<\/button>/g)].map(match=>{
    const button=node();button.dataset.signExample=match[2];button.dataset.signLabel=match[4];button.textContent=match[4];
    button.mocap=/data-mocap-only/.test(match[1]+match[3]);return button;
  });
  const group=node(),container=node(),search=node(),count=node(),empty=node();
  search.value='';
  group.querySelectorAll=()=>buttons.filter(button=>button.mocap);
  container.children=buttons.filter(button=>!button.mocap);
  const nodes=new Map([['.mocap-word-group',group],['.example-words',container],['#signExampleSearch',search],['#signExampleListStatus',count],['#signExampleEmpty',empty]]);
  const references=new Map(),published=new Map(),chosen=[],instructed=[];
  const settings=id=>hidden.includes(id)?{hidden:true}:{};
  const api=vm.runInNewContext('let publishedPacks=[],exampleCatalogReady=false;\n'+selector+'\n({loadPublishedExamples,filterExampleButtons});',{
    buttons,referenceExamples:references,publishedExamples:published,libraryId,hasRecognitionModel,
    wordSettings:settings,loadVocabularySettings:async()=>({}),
    applyVocabularySettings:items=>items.filter(item=>!settings(item.id).hidden),
    fetch:async path=>{
      if(path.includes('motion-categories')){
        if(indexFails)throw Error('category index unavailable');
        return {ok:true,json:async()=>index};
      }
      return {ok:!catalogFails,json:async()=>catalog};
    },
    document:{querySelector:id=>nodes.get(id)||null,createElement:()=>node()},
    chooseSign:(...args)=>chosen.push(args),instructions:id=>instructed.push(id),updateAccuracy(){},
  });
  return {api,buttons,group,container,search,count,empty,references,published,chosen,instructed};
}

test('all 198 recognition labels have direct selectors, with existing demos retained and no duplicate IDs',async()=>{
  const x=ui();await x.api.loadPublishedExamples();
  const expected=new Set(manifest.items.map(item=>item.id));
  const actual=new Set(x.buttons.filter(button=>hasRecognitionModel(x.references.get(button.dataset.signExample))).map(button=>button.dataset.signExample));
  assert.deepEqual(actual,expected);
  assert.equal(x.buttons.length,201);
  assert.equal(new Set(x.buttons.map(button=>button.dataset.signExample)).size,201);
  assert.equal(x.container.children.length,197); // BROTHER remains in its captured-demo group.
  assert.match(x.count.textContent,/198 of 198 recognition labels shown.*3 learning-only demos/);
  assert.equal(x.buttons.filter(button=>button.mocap).length,4);
  const before=x.buttons.length;await x.api.loadPublishedExamples();assert.equal(x.buttons.length,before);
});

test('full-100 and Beginner references no longer require a category pack',async()=>{
  const x=ui({indexFails:true});await x.api.loadPublishedExamples();
  assert.equal(x.buttons.length,201);
  for(const id of ['apple','8hour','good-morning','yesterday','i-me']){
    assert.ok(x.buttons.some(button=>button.dataset.signExample===id),id);
    assert.equal(x.published.has(id),false,id);
  }
  assert.match(x.count.textContent,/198 of 198/);
});

test('new buttons preserve their label/reference identity and select only on an explicit click',async()=>{
  const x=ui({libraryId:'good-morning'});await x.api.loadPublishedExamples();
  assert.equal(x.chosen.length,0);
  const apple=x.buttons.find(button=>button.dataset.signExample==='apple');
  assert.equal(apple.dataset.signLabel,'APPLE');assert.equal(apple.attributes['aria-pressed'],'false');
  assert.equal(x.references.get('apple').video,'media/research-signs/apple.mp4');
  apple.handlers.click();assert.deepEqual(x.chosen[0],['apple',apple,'APPLE']);
  assert.deepEqual(x.instructed,['good-morning']);
});

test('search filters new references case-insensitively without changing playback or model consent',async()=>{
  const x=ui();await x.api.loadPublishedExamples();
  x.search.value='  aPpLe  ';x.search.handlers.input();
  assert.deepEqual(x.buttons.filter(button=>!button.hidden).map(button=>button.dataset.signExample),['apple']);
  assert.match(x.count.textContent,/1 of 198 recognition labels shown/);
  assert.equal(x.group.hidden,true);assert.equal(x.empty.hidden,true);assert.equal(x.chosen.length,0);
  x.search.value='GOOD MORNING';x.api.filterExampleButtons();
  assert.deepEqual(x.buttons.filter(button=>!button.hidden).map(button=>button.dataset.signExample),['good-morning']);
  x.search.value='';x.api.filterExampleButtons();
  assert.equal(x.buttons.filter(button=>!button.hidden).length,201);
});

test('search includes existing captured demos and has a clean no-match state',async()=>{
  const x=ui();await x.api.loadPublishedExamples();
  x.search.value='BROTHER';x.api.filterExampleButtons();
  assert.equal(x.group.hidden,false);assert.match(x.count.textContent,/1 of 198/);
  x.search.value='no-such-motion-word';x.api.filterExampleButtons();
  assert.equal(x.empty.hidden,false);assert.match(x.count.textContent,/0 of 198/);
  assert.equal(x.buttons.filter(button=>!button.hidden).length,0);
});

test('administrator-hidden words remain hidden after loading and searching',async()=>{
  const x=ui({hidden:['hello','apple']});await x.api.loadPublishedExamples();
  assert.equal(x.buttons.find(button=>button.dataset.signExample==='hello').hidden,true);
  assert.equal(x.buttons.some(button=>button.dataset.signExample==='apple'),false);
  assert.match(x.count.textContent,/196 of 196/);
  x.search.value='HELLO';x.api.filterExampleButtons();
  assert.equal(x.buttons.find(button=>button.dataset.signExample==='hello').hidden,true);
  assert.equal(x.empty.hidden,false);
});

test('catalog failure keeps original selectors and explicitly reports that the full list did not load',async()=>{
  const x=ui({catalogFails:true});await x.api.loadPublishedExamples();
  assert.equal(x.buttons.length,42);
  assert.match(x.count.textContent,/full motion-word list could not load.*Existing examples remain available/);
  assert.equal(x.chosen.length,0);
});

test('HTML and styling expose an accessible searchable, scrollable selector with a fresh cache tag',()=>{
  assert.match(html,/label for="signExampleSearch"/);
  assert.match(html,/id="signExampleSearch"[^>]*type="search"/);
  assert.match(html,/aria-controls="signExampleWords"/);
  assert.match(html,/id="signExampleListStatus"[^>]*role="status"/);
  assert.match(html,/sign-examples\.js\?v=20261107-motion-release-1/);
  const css=read('studio-theme.css');
  assert.match(css,/#signExampleWords\{[^}]*max-height:[^}]*overflow-y:auto/);
  assert.match(css,/button\[data-sign-example\]\[hidden\]/);
});

