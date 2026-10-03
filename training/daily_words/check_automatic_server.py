"""Automatic server capture state checks using cached detector frames, not live-camera accuracy."""
import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path('/opt/handspeak/repository');live=os.environ.get('CHECK_LIVE')=='1'
frames=json.loads((root/'reports/virtual-camera/portrait-normal.json').read_text())['frames']
frames=[f for f in frames if 8<=f['time']<=12]
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.route('**/__automatic_server_test',lambda r:r.fulfill(body=(root/'index.html').read_text().split('<script type="module"')[0],content_type='text/html'))
 if not live:page.route('**/research-words.js?*',lambda r:r.fulfill(body=(root/'research-words.js').read_text(),content_type='text/javascript'))
 page.goto('https://handspeak.cvsu.dev/__automatic_server_test',wait_until='domcontentloaded')
 page.evaluate('''async()=>{
 window.posts=[];window.accepted=[];window.resolvePost=null;
 const realFetch=fetch;window.fetch=(url,options)=>url==='/api/research-words'?new Promise(resolve=>{posts.push(JSON.parse(options.body));resolvePost=data=>resolve({ok:true,json:async()=>data});}):realFetch(url,options);
 const {createResearchWords}=await import('/research-words.js?v=20261003-auto-server-1');window.harness=createResearchWords({onWord:w=>accepted.push(w),onStatus:()=>{},onChange:()=>{}});
 window.feed=frames=>{let t=performance.now();for(const f of [...Array.from({length:5},()=>({landmarks:[],handedness:[]})),...frames,...Array.from({length:15},()=>({landmarks:[],handedness:[]}))]){harness.frame({...f,imageAspect:640/480},t);t+=100;}};
 }''')
 page.wait_for_function("!document.querySelector('#researchWordsToggle').disabled")
 page.locator('#wordRecognitionControls').evaluate('(e)=>e.hidden=false')
 page.evaluate('(frames)=>feed(frames)',frames);assert page.evaluate('posts.length')==0
 page.locator('#researchWordsToggle').check();assert page.locator('#automaticWords').is_enabled()
 page.evaluate('(frames)=>feed(frames)',frames);assert page.evaluate('posts.length')==1
 payload=page.evaluate('posts[0]');assert payload['consent'] is True;assert len(payload['sequence'])==20
 page.evaluate('(frames)=>feed(frames)',frames);assert page.evaluate('posts.length')==1
 page.evaluate("resolvePost({label:'NAME'})");page.wait_for_function("!document.querySelector('#researchAccept').disabled")
 assert page.evaluate('accepted.length')==0
 page.evaluate('(frames)=>feed(frames)',frames);assert page.evaluate('posts.length')==1
 page.locator('#researchAccept').click();assert page.evaluate('accepted')==['NAME']
 page.evaluate('(frames)=>feed(frames)',frames);assert page.evaluate('posts.length')==1
 page.wait_for_timeout(6100);page.evaluate('(frames)=>feed(frames)',frames);assert page.evaluate('posts.length')==2
 page.locator('#researchWordsToggle').uncheck();page.evaluate("resolvePost({label:'HOME'})");page.wait_for_timeout(100);assert page.locator('#researchAccept').is_disabled();assert page.evaluate('accepted')==['NAME']
 page.locator('#researchWordsToggle').check();page.locator('#automaticWords').uncheck();page.wait_for_timeout(6100);page.evaluate('(frames)=>feed(frames)',frames);assert page.evaluate('posts.length')==2
 assert not errors,errors
 print('PASS: opt-in, automatic movement capture without Record, one request in flight, explicit review, cooldown, opt-out discards stale response, manual-only setting.')
 b.close()
