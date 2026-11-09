import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../vocabulary-library.js',import.meta.url),'utf8');
const start=source.indexOf("document.addEventListener('handspeak:default-practice',async event=>");
const end=source.indexOf("document.addEventListener('handspeak:practice'",start);
function setup({checked=true,disabled=false,ready=true}={}){
  const toggle={checked,disabled,events:[],dispatchEvent(event){this.events.push(event.type);}};
  const status={textContent:''};let handler,navigated=0;
  vm.runInNewContext(source.slice(start,end),{
    document:{addEventListener(name,fn){handler=fn;}},activate:async()=>ready,
    $:selector=>selector==='#expandedWords'?toggle:status,Event:class {constructor(type){this.type=type;}},
    cameraMode:()=>navigated++,
  });
  return {toggle,status,run:label=>handler({detail:{label}}),navigated:()=>navigated};
}
test('default Practice clears an expanded vocabulary from an earlier exercise',async()=>{
  const s=setup();await s.run('HUNGRY');assert.equal(s.toggle.checked,true);
  await s.run('HELLO');assert.equal(s.toggle.checked,false);
  await s.run('THANK YOU');assert.equal(s.toggle.checked,false);
  assert.equal(s.navigated(),3);
});
test('all seven extra words explicitly select their full expanded vocabulary',async()=>{
  for(const word of ['DRINK','WATER','BOOK','FOOD','HUNGRY','LIKE','GO']){
    const s=setup({checked:false});await s.run(word);assert.equal(s.toggle.checked,true);
    assert.deepEqual(s.toggle.events,['change']);
  }
});
test('a missing extra model does not silently practice its word against default labels',async()=>{
  const s=setup({checked:false,disabled:true});await s.run('DRINK');
  assert.equal(s.navigated(),0);assert.match(s.status.textContent,/still loading/);
  await s.run('HELLO');assert.equal(s.navigated(),1);assert.equal(s.toggle.checked,false);
});
test('an unavailable default model does not change the current camera selection',async()=>{
  const s=setup({ready:false});await s.run('HELLO');assert.equal(s.toggle.checked,true);assert.equal(s.navigated(),0);
});
