const text=(tag,value,className)=>{const e=document.createElement(tag);e.textContent=value;if(className)e.className=className;return e;};
export function createVocabularyLibrary({onWord,setVocabulary}) {
  const $=s=>document.querySelector(s),size=12;
  let catalog=null,packs=[],page=0,active='',loadId=0,libraryId=0;
  function defaultLabel(){const extra=$('#expandedWords');$('#activeVocabulary').textContent=extra.checked&&!extra.disabled?'Camera vocabulary: Default + extra-word preview · 13 words':'Camera vocabulary: Default words';}
  function filtered(){
    const query=$('#vocabularySearch').value.toLowerCase().trim(),category=$('#vocabularyCategory').value,kind=$('#vocabularyFilter').value;
    return catalog.items.filter(item=>(!query||[item.label,...(item.searchAliases||[])].some(value=>value.toLowerCase().includes(query)))&&(!category||item.categories.includes(category))&&(!kind||(kind==='video'&&(item.video||item.youtubeId))||(kind==='model'&&(item.cameraGroups?.length||['existing-preview','daily-preview','default-preview'].includes(item.recognition)))||(kind==='personal'&&!item.cameraGroups?.length&&!['existing-preview','daily-preview','default-preview'].includes(item.recognition))));
  }
  function cameraMode(){const mode=$('#recognitionMode');mode.value='words';mode.dispatchEvent(new Event('change',{bubbles:true}));$('#cameraButton').focus({preventScroll:true});}
  async function activate(id){
    const requested=++loadId,select=$('#cameraVocabulary'),status=$('#vocabularyCameraStatus');select.value=id;
    if(!id){if(!setVocabulary(null)){status.textContent='Default model is still loading. Try again shortly.';select.value=active;return false;}active='';defaultLabel();status.textContent='Default vocabulary selected. The extra-word preview is controlled below.';return true;}
    const pack=packs.find(p=>p.id===id);if(!pack)return false;
    status.textContent=`Loading ${pack.name}…`;
    try {
      const response=await fetch(pack.file+'?v=20261002-catalog-1');if(!response.ok)throw Error('download failed');const model=await response.json();
      if(requested!==loadId)return false;
      if(!setVocabulary(model,pack.name))throw Error('model not ready or invalid');active=id;$('#activeVocabulary').textContent=`Camera vocabulary: ${pack.name} preview`;
      status.textContent=`${pack.name} preview: ${pack.labels.join(' · ')}. Use only these words; review every suggestion.${pack.test?` Recorded check: ${pack.test.correct}/${pack.test.total} correct; ${pack.test.negativeFalse}/${pack.test.negativeTotal} unsupported clips falsely accepted. This is not live-camera accuracy.`:''} Category changes reset the current capture.`;cameraMode();return true;
    }catch{if(requested===loadId){select.value=active;status.textContent='Category could not load. The previous camera vocabulary remains selected. Try again.';}return false;}
  }
  async function practice(item){
    if(item.recognition==='default-preview'){document.dispatchEvent(new CustomEvent('handspeak:default-practice',{detail:{label:item.label}}));return;}
    if(item.recognition==='daily-preview'){document.dispatchEvent(new CustomEvent('handspeak:enable-word-preview'));return;}
    if(item.cameraGroups?.length){if(await activate(item.cameraGroups.includes(active)?active:item.cameraGroups[0])){document.dispatchEvent(new CustomEvent('handspeak:navigate',{detail:{target:'#workspace'}}));$('#workspace').scrollIntoView({block:'start',behavior:'smooth'});}return;}
    if(['existing-preview','daily-preview','default-preview'].includes(item.recognition)){
      if(!await activate(''))return;
      const extra=$('#expandedWords');if(extra.disabled){$('#vocabularyCameraStatus').textContent='Extra words are still loading. Try again shortly.';return;}
      extra.checked=true;extra.dispatchEvent(new Event('change'));cameraMode();return;
    }
    $('#motionLabel').value=item.label;$('#motionLabel').closest('details').open=true;cameraMode();document.dispatchEvent(new CustomEvent('handspeak:navigate',{detail:{target:'#motionLabel'}}));$('#motionLabel').scrollIntoView({block:'center',behavior:'smooth'});$('#motionLabel').focus({preventScroll:true});
    $('#vocabularyCameraStatus').textContent=`${item.label} has no active pretrained model. Record at least three personal examples; this does not validate recognition accuracy.`;
  }
  function render(){
    if(!catalog)return;const matches=filtered(),pages=Math.max(1,Math.ceil(matches.length/size));page=Math.min(page,pages-1);
    $('#vocabularyStatus').textContent=`${matches.length} of ${catalog.items.length} entries · videos, external lessons, and recognition availability are shown separately.`;
    $('#vocabularyPage').textContent=`Page ${page+1} of ${pages}`;$('#vocabularyPrevious').disabled=page===0;$('#vocabularyNext').disabled=page>=pages-1;
    $('#vocabularyEmergency').hidden=!['health-emergency','safety'].includes($('#vocabularyCategory').value);const cards=$('#vocabularyCards');cards.replaceChildren();
    for(const item of matches.slice(page*size,(page+1)*size)){
      const card=text('article','', 'vocabulary-card');card.append(text('h4',item.label));
      card.append(text('span',item.recognition==='default-preview'?'Default motion preview':item.recognition==='daily-preview'?'Five-word server preview':item.cameraGroups?.length?'Category recognition preview':['existing-preview','daily-preview','default-preview'].includes(item.recognition)?'Existing recognition preview':'No enabled model','vocabulary-badge'));
      if(item.testSummary)card.append(text('p',item.testSummary,'camera-tip'));
      if(item.note)card.append(text('p',item.note,'camera-tip'));
      const actions=text('div','','vocabulary-card-actions');
      if(item.video||item.youtubeId){const b=text('button','Watch example','secondary-button');b.type='button';b.onclick=()=>{document.dispatchEvent(new CustomEvent('handspeak:example',{detail:{label:item.label,src:item.video,id:item.id}}));document.dispatchEvent(new CustomEvent('handspeak:navigate',{detail:{target:'#sign-examples'}}));$('#sign-examples').scrollIntoView({block:'start',behavior:'smooth'});};actions.append(b);}
      if(item.learningUrl){const a=text('a',item.learningScope?`Lesson: ${item.learningScope}`:'View source example','primary-link');a.href=item.learningUrl;a.target='_blank';a.rel='noopener noreferrer';actions.append(a);}
      if(!item.video&&!item.learningUrl)card.append(text('p','A verified lesson or recording is still needed for this entry.','camera-tip'));
      const camera=text('button',item.cameraGroups?.length||['existing-preview','daily-preview','default-preview'].includes(item.recognition)?'Practice at camera':'Teach this sign','secondary-button');camera.type='button';camera.onclick=()=>{void practice(item);};actions.append(camera);
      const type=text('button','Add as typed text','text-button');type.type='button';type.onclick=()=>{if(onWord(item.label)!==false)$('#vocabularyStatus').textContent=`Added ${item.label} as typed text, not a camera detection.`;};actions.append(type);card.append(actions);cards.append(card);
    }
    if(!matches.length)cards.append(text('p','No matching entries. Try another word or category.'));
  }
  async function load(){
    const request=++libraryId;$('#vocabularyRetry').disabled=true;
    try {
      const response=await fetch('models/motion-vocabulary.json?v=20261003-finish-1');if(!response.ok)throw Error();const data=await response.json();
      if(!Array.isArray(data.items)||!Array.isArray(data.categories))throw Error();
      let index={groups:[]};try{const r=await fetch('models/motion-categories/index.json?v=20261002-catalog-1');if(r.ok)index=await r.json();}catch{}
      if(request!==libraryId)return;++loadId;catalog=data;packs=Array.isArray(index.groups)?index.groups:[];
      for(const item of catalog.items)item.cameraGroups=(item.cameraGroups||[]).filter(id=>packs.some(p=>p.id===id&&p.labels.includes(item.label)));
      if(active&&!packs.some(p=>p.id===active)){setVocabulary(null);active='';defaultLabel();}
      const select=$('#vocabularyCategory'),previous=select.value;select.replaceChildren(new Option('All categories',''));catalog.categories.forEach(c=>select.add(new Option(c.name,c.id)));select.value=previous;
      const camera=$('#cameraVocabulary');camera.replaceChildren(new Option('Default words',''));packs.forEach(p=>camera.add(new Option(p.name+' · preview',p.id)));camera.value=active;camera.closest('label').hidden=packs.length===0;
      if(!packs.length)$('#vocabularyCameraStatus').textContent='New category models did not pass evaluation. Default words and the existing extra-word preview remain available.';
      page=0;render();
    }catch{if(request===libraryId)$('#vocabularyStatus').textContent='Vocabulary could not load. Use Reload library to retry.';}
    finally{if(request===libraryId)$('#vocabularyRetry').disabled=false;}
  }
  for(const id of ['#vocabularySearch','#vocabularyCategory','#vocabularyFilter'])$(id).addEventListener(id==='#vocabularySearch'?'input':'change',()=>{page=0;render();});
  $('#vocabularyPrevious').onclick=()=>{page--;render();};$('#vocabularyNext').onclick=()=>{page++;render();};$('#vocabularyRetry').onclick=()=>{void load();};$('#cameraVocabulary').onchange=e=>{void activate(e.target.value);};
  $('#expandedWords').addEventListener('change',()=>{if(!active)defaultLabel();});
  document.addEventListener('handspeak:personal-words',()=>{if(!active)defaultLabel();});
  defaultLabel();
  document.addEventListener('handspeak:default-practice',async event=>{if(!await activate(''))return;const extra=$('#expandedWords');if(!extra.disabled){extra.checked=extra.checked||['DRINK','WATER','BOOK','FOOD','HUNGRY','LIKE','GO'].includes(event.detail.label);extra.dispatchEvent(new Event('change'));}cameraMode();});
  document.addEventListener('handspeak:practice',event=>{const item=catalog?.items.find(i=>i.id===event.detail.id);if(item)void practice(item);});
  void load();
}
