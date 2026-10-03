export function createInterpreter({getMessage,setMessage,speak=()=>{}}) {
  const $=s=>document.querySelector(s);
  let result=null, applied=false, revision=0, lastSpoken=null;
  const status=$('#interpretStatus'), box=$('#interpretResult'), button=$('#interpretButton');
  async function availability(){
    try {const response=await fetch('/api/interpret/status');if(!response.ok)throw Error();const data=await response.json();status.textContent=data.available?'Local sentence assistant ready. Up to 500 characters.':'Local model is unavailable. Your draft and other features still work.';}
    catch{status.textContent='Could not check the local model. You can retry interpretation.';}
  }
  async function interpret(autoSpeak=false){
    if(button.disabled)return;
    const requestRevision=revision;
    const original=getMessage();
    if(!original.trim()||original.length>500){status.textContent='Enter 1–500 characters. Use Edit message to adjust your draft.';return;}
    result=null;applied=false;box.hidden=true;button.disabled=true;
    status.textContent='Interpreting on this server… This can take up to 45 seconds. Your draft is unchanged.';
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),50000);
    try {
      const response=await fetch('/api/interpret',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:original}),signal:controller.signal});
      const data=await response.json();if(!response.ok)throw Error(data.error||'Interpretation failed.');
      result=data;$('#interpretOriginal').textContent=original;$('#interpretSuggestion').textContent=data.sentence||'More context is needed.';$('#interpretNote').textContent=data.note;
      box.hidden=false;$('#interpretUndo').hidden=true;
      $('#interpretApply').disabled=data.needsClarification||!data.sentence||getMessage()!==original;
      status.textContent=getMessage()!==original?'Your draft changed. Interpret again to use a current suggestion.':'Suggestion only. Compare it with your original words before applying.';
      if(autoSpeak){
        if(!$('#finishInterpretSpeak').checked||revision!==requestRevision||getMessage()!==original){status.textContent='Automatic speech canceled: the draft or FINISH setting changed.';}
        else if(data.needsClarification||!data.sentence){status.textContent='Nothing spoken. The sentence needs clarification; edit the draft and try again.';}
        else{lastSpoken=original;speak(data.sentence);status.textContent='FINISH received — requested speech for the interpreted sentence. Original words remain in your draft. If audio is blocked, use Speak suggestion.';}
      }
    } catch(error){status.textContent=error.name==='AbortError'?'Interpretation timed out. Your draft is unchanged.':error.message;}
    finally{clearTimeout(timer);button.disabled=false;}
  }
  button.addEventListener('click',()=>{void interpret();});
  $('#speakInterpretation').addEventListener('click',()=>{if(result&&!result.needsClarification&&result.sentence)speak(result.sentence);});
  $('#finishInterpretSpeak').addEventListener('change',()=>{revision++;});
  $('#interpretApply').addEventListener('click',()=>{
    if(!result||result.needsClarification)return;
    if(getMessage()!==result.original){status.textContent='Your draft changed. Interpret again before applying.';$('#interpretApply').disabled=true;return;}
    setMessage(result.sentence);applied=true;$('#interpretApply').disabled=true;$('#interpretUndo').hidden=false;status.textContent='Suggestion applied. Review before speaking or saving. Original words remain below.';
  });
  $('#interpretUndo').addEventListener('click',()=>{
    if(!applied||!result)return;
    if(getMessage()!==result.sentence){status.textContent='Your draft changed after applying. Use Edit message to avoid overwriting your edits.';return;}
    setMessage(result.original);applied=false;$('#interpretUndo').hidden=true;$('#interpretApply').disabled=false;status.textContent='Original draft restored.';
  });
  new MutationObserver(()=>{revision++;lastSpoken=null;if(result&&!applied&&getMessage()!==result.original)$('#interpretApply').disabled=true;}).observe($('#messageText'),{childList:true,subtree:true,characterData:true});
  void availability();
  return {finish(){
    if(!$('#finishInterpretSpeak').checked)return false;
    if(!getMessage().trim()){status.textContent='FINISH received, but the draft is empty. Add your words first.';return true;}
    if(lastSpoken===getMessage()){status.textContent='This draft was already spoken. Add or edit words before signing FINISH again.';return true;}
    void interpret(true);return true;
  }};
}
