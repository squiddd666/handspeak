"""Staging-only public UI/API tests. No physical camera accuracy claim."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
import os
BASE=os.environ.get('HANDSPEAK_TEST_URL','http://127.0.0.1:8005')
root=Path('/opt/handspeak-training/daily-words/citizen-research')
row=next(r for r in json.loads((root/'development-features.json').read_text()) if r['label']=='NAME' and r['sequence'])
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);context=b.new_context();context.route("https://fonts.googleapis.com/**",lambda r:r.abort());context.route("https://fonts.gstatic.com/**",lambda r:r.abort());page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(BASE,wait_until='networkidle');assert page.locator('#researchWordsToggle').is_enabled()
 page.reload(wait_until='networkidle');page.locator('#recognitionMode').select_option('words')
 page.wait_for_function("!document.querySelector('#researchWordsToggle').disabled")
 requests=[];page.on('request',lambda r:requests.append(r.url) if r.url.endswith('/api/research-words') else None)
 page.locator('#researchWordsToggle').check();assert page.locator('#standardWordOptions').is_hidden();assert page.locator('#automaticWords').is_enabled();assert not requests
 assert page.locator('#processingLocation').inner_text()=='SERVER PREVIEW'
 page.locator('#recognitionMode').select_option('letters');assert not page.locator('#researchWordsToggle').is_checked()
 assert page.locator('#processingLocation').inner_text()=='ON DEVICE'
 for width in [390,1280]:
  page.set_viewport_size({'width':width,'height':900});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 assert context.request.get(BASE+'/api/auth/me').json()['user'] is None
 page.locator('[data-daily-word=NAME] [data-daily-preview]').click();assert page.locator('#researchWordsToggle').is_checked()
 page.locator('#vocabularySearch').fill('NAME');page.locator('#vocabularyFilter').select_option('model')
 assert 'Five-word server preview' in page.locator('#vocabularyCards').inner_text()
 page.locator('#vocabularyCards').get_by_role('button',name='Practice at camera').click();assert page.locator('#researchWordsToggle').is_checked()
 # Test frozen model through guest HTTP with known development features.
 r=context.request.post(BASE+'/api/research-words',data={'consent':True,'sequence':row['sequence']});assert r.status==200,r.text();assert r.json()['label']=='NAME'
 # Isolated browser module harness supplies known detector frames, not video.
 harness=context.new_page();harness.on('pageerror',lambda e:errors.append(str(e)))
 harness.route('**/app.js?*',lambda route:route.fulfill(content_type='text/javascript',body="import {createResearchWords} from './research-words.js?v=20261002-public-words-1';window.accepted=[];window.researchHarness=createResearchWords({onWord:w=>accepted.push(w),onStatus:()=>{},onChange:()=>{}});"))
 harness.goto(BASE,wait_until='networkidle');harness.locator('#wordRecognitionControls').evaluate('(e)=>e.hidden=false');harness.wait_for_function("!document.querySelector('#researchWordsToggle').disabled");harness.locator('#researchWordsToggle').check()
 harness.evaluate('''row=>{researchHarness.recognize();const start=performance.now()+1501;row.rawFrames.forEach((frame,i)=>researchHarness.frame({landmarks:frame.filter(Boolean),handedness:frame.map((h,side)=>h?[{categoryName:side===0?'Left':'Right'}]:null).filter(Boolean),imageAspect:row.imageAspect},start+i*90));}''',row)
 harness.wait_for_function("document.querySelector('#researchWordsStatus').textContent.includes('Possible match')",timeout=12000)
 assert harness.evaluate('accepted.length')==0;harness.locator('#researchAccept').click();assert harness.evaluate('accepted')==['NAME']
 harness.evaluate('researchHarness.recognize();researchHarness.cancel()');assert harness.locator('#researchAccept').is_disabled()
 harness.locator('#researchWordsToggle').uncheck();assert harness.locator('#researchRecord').is_disabled()
 assert not errors,errors
 print(json.dumps({'guestAccess':True,'optInWithoutUpload':True,'publicApiInference':'NAME','manualCaptureAndReview':True,'modeReset':True,'mobileFit':True,'pageErrors':errors}))
 b.close()
