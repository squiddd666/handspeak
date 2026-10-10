"""Interpreter behavior with controlled responses; not a recognition accuracy test."""
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[2]
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page()
 ids=['interpretStatus','interpretResult','interpretButton','interpretOriginal','interpretSuggestion','interpretNote','interpretUndo','interpretApply','speakInterpretation','messageText']
 html=''.join('<button id="'+i+'"></button>' for i in ids)+'<input type="checkbox" id="finishInterpretSpeak"><input type="checkbox" id="sentenceAutoAdd">'
 page.route('**/__finish_test',lambda r:r.fulfill(body=html,content_type='text/html'))
 page.route('**/test-interpreter.js',lambda r:r.fulfill(body=(root/'interpretation.js').read_text(),content_type='text/javascript'))
 page.goto('https://handspeak.cvsu.dev/__finish_test')
 page.evaluate('''async()=>{
 const {createInterpreter}=await import('/test-interpreter.js');window.spoken=[];window.requests=[];window.respond=null;
 window.fetch=async(url,options)=>url.endsWith('/status')?new Promise(resolve=>{window.ready=()=>resolve({ok:true,json:async()=>({available:true})});}):new Promise(resolve=>{requests.push(JSON.parse(options.body));window.respond=(data,ok=true)=>resolve({ok,json:async()=>data});});
 window.draft='';window.edit=text=>{draft=text;document.querySelector('#messageText').textContent=text;};
 window.interpreter=createInterpreter({getMessage:()=>draft,setMessage:edit,speak:text=>spoken.push(text)});
 }''')
 def edit(s):page.evaluate('(s)=>edit(s)',s)
 def trigger():return page.evaluate('interpreter.finish()')
 def complete(unclear=False):
  page.evaluate('(unclear)=>respond({original:draft,sentence:unclear?"":"I want water, please.",needsClarification:unclear,note:"Review."})',unclear)
  page.wait_for_function('!document.querySelector("#interpretButton").disabled')
 edit('I WANT WATER PLEASE');assert not trigger();assert page.evaluate('requests.length')==0
 page.locator('#finishInterpretSpeak').check();assert page.locator('#sentenceAutoAdd').is_checked();trigger()
 page.evaluate('ready()');page.wait_for_timeout(1100)
 assert 'seconds elapsed' in page.locator('#interpretStatus').inner_text()
 assert page.locator('#interpretButton').get_attribute('aria-busy')=='true'
 trigger();assert page.evaluate('requests.length')==1
 assert 'already running' in page.locator('#interpretStatus').inner_text()
 complete();assert page.evaluate('spoken')==['I want water, please.'];assert page.evaluate('draft')=='I WANT WATER PLEASE'
 assert page.locator('#interpretButton').get_attribute('aria-busy') is None
 trigger();assert page.evaluate('requests.length')==1
 edit('I WANT FOOD');trigger();edit('CHANGED');complete();assert page.evaluate('spoken.length')==1
 edit('I WANT HOME');trigger();page.locator('#finishInterpretSpeak').uncheck();complete();assert page.evaluate('spoken.length')==1
 page.locator('#finishInterpretSpeak').check();edit('UNCLEAR');trigger();complete(True);assert page.evaluate('spoken.length')==1
 edit('ERROR');trigger();page.evaluate('respond({error:"Unavailable"},false)');page.wait_for_function('!document.querySelector("#interpretButton").disabled');assert page.evaluate('spoken.length')==1
 edit('');n=page.evaluate('requests.length');trigger();assert page.evaluate('requests.length')==n
 print('PASS: disabled, empty, FINISH, repeated match, unchanged draft, changed draft, opt-out, clarification, and API failure behavior.')
 b.close()
