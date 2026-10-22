const $=s=>document.querySelector(s);
const views={home:['home'],workspace:['workspace'],learn:['learn','motion-studio'],'ai-studio':['ai-studio'],history:['history'],evaluate:['evaluate'],about:['about']};
const lesson=$('#sign-examples'),lessonHome=document.createComment('Lesson position');lesson.before(lessonHome);
let current='';
function show(target,update=true){
 const node=document.getElementById(target.replace(/^#/,''));
 let view=Object.keys(views).find(v=>views[v].some(id=>document.getElementById(id)?.contains(node)))||'home';
 if(target==='#sign-examples')view='learn';
 if(view!=='workspace'&&$('#cameraLesson').contains(lesson)){lessonHome.after(lesson);$('#cameraLesson').hidden=true;}
 for(const [key,ids] of Object.entries(views))for(const id of ids)document.getElementById(id).hidden=key!==view;
 document.querySelector('.application-help').hidden=view!=='about';
 for(const link of document.querySelectorAll('.site-header nav a')){const active=link.hash==='#'+view;link.classList.toggle('active',active);if(active)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');}
 if(current!==view)document.dispatchEvent(new CustomEvent('handspeak:view',{detail:{view}}));
 current=view;if(update&&location.hash!==target)history.pushState(null,'',target);
}
document.addEventListener('handspeak:navigate',e=>show(e.detail.target));
document.addEventListener('click',e=>{const a=e.target.closest('a[href^="#"]');if(!a)return;const target=a.hash||'#home';if(target==='#main')return;if(target==='#capstoneWords'){const mode=$('#recognitionMode');mode.value='words';mode.dispatchEvent(new Event('change'));}show(target);},true);
window.addEventListener('popstate',()=>show(location.hash||'#workspace',false));
window.addEventListener('hashchange',()=>show(location.hash||'#workspace',false));
$('#startSigning').addEventListener('click',()=>show('#workspace'));
$('#startFocusedDemo').addEventListener('click',()=>{const mode=$('#recognitionMode');mode.value='words';mode.dispatchEvent(new Event('change'));show('#workspace');});
function dock(){show('#workspace');$('#cameraLesson').hidden=false;$('#cameraLesson').append(lesson);}
function selectLesson(id){const button=words.find(b=>b.dataset.signExample===id);if(button){button.click();$('#practiceWord').value=id;$('#practiceInstructions').textContent=$('#signExampleMode').textContent;}}
document.addEventListener('handspeak:default-practice',e=>{selectLesson(e.detail.label.toLowerCase().replaceAll(' ','-'));dock();});
document.addEventListener('handspeak:practice',e=>{selectLesson(e.detail.id);dock();});
// Core 7-word camera model: select the core vocabulary, switch to words mode,
// dock the lesson next to the camera, and show the recording instructions.
document.addEventListener('handspeak:capstone-practice',e=>{
  const name=e.detail?.label||'Core 7-word';
  const mode=$('#recognitionMode');mode.value='words';mode.dispatchEvent(new Event('change'));
  // A word from the extended tier needs the extended vocabulary selected.
  const vocab=$('#capstoneVocabMode');
  if(vocab){
    const extended=['lock','duck','baseballcap','other','whatfor','drag','microscope','party','demand','edit','mechanic','deaf'];
    vocab.value=extended.includes(e.detail?.id)?'extended':'core';
    vocab.dispatchEvent(new Event('change'));
  }
  if(e.detail?.id)$('#practiceWord').value=e.detail.id;
  dock();
  $('#practiceInstructions').textContent=`${name} · Core camera model. Record one complete sign for four seconds, then review the top five before adding the word. No example video is available for this sign.`;
});
document.addEventListener('handspeak:enable-word-preview',e=>{if(e.detail?.id){selectLesson(e.detail.id);dock();}else show('#workspace');});
const words=[...document.querySelectorAll('[data-sign-example]')];
for(const b of words)$('#practiceWord').add(new Option(b.textContent,b.dataset.signExample));
$('#preparePractice').addEventListener('click',()=>{
 const id=$('#practiceWord').value,button=words.find(b=>b.dataset.signExample===id);
 if(!button){$('#practiceInstructions').textContent='Choose a word first.';return;}
 button.click();dock();
 const daily=['name','home','have','want','love'].includes(id);
 const core=['belt','eat','empty','peg','soccer','squeeze','vlog'].includes(id);
 if(core){$('#signExamplePractice').click();}
 else if(daily){const mode=$('#recognitionMode');mode.value='words';mode.dispatchEvent(new Event('change'));$('#practiceInstructions').textContent='Automatic server capture · Enable five-word server processing below and Automatic words. Start the camera, sign once, then pause. Review each result. Manual recording is also available.';}
 else{$('#signExamplePractice').click();$('#practiceInstructions').textContent='Automatic capture · Start the camera, sign once, then pause. Review the suggested word. If capture misses your movement, use Record a word.';}
});
// Keep the LLM comparison next to the editable message and speech controls.
const interpreter=$('#interpretTitle').closest('section');$('#messageBox').closest('article').append(interpreter);
let simple=true;
try{simple=localStorage.getItem('handspeak-simple-view')!=='off';}catch{}
function renderSimpleView(){
 document.body.classList.toggle('simple-mode',simple);
 const button=$('#simpleViewButton');button.setAttribute('aria-pressed',String(simple));
 button.textContent=simple?'Show more tools':'Use simple view';
}
$('#simpleViewButton').addEventListener('click',()=>{
 simple=!simple;renderSimpleView();
 try{localStorage.setItem('handspeak-simple-view',simple?'on':'off');}catch{}
 $('#simpleViewButton').focus();
});
renderSimpleView();
const initialTarget=location.hash||'#workspace';
if(!location.hash)history.replaceState(null,'','#workspace');
show(initialTarget,false);
