import json,time
from pathlib import Path
from playwright.sync_api import sync_playwright
rows=[]
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page(viewport={'width':1365,'height':1000});errors=[];writes=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('request',lambda r:writes.append(r.url) if r.method=='POST' else None)
 page.route('https://fonts.googleapis.com/**',lambda r:r.abort())
 page.goto('https://handspeak.cvsu.dev/#workspace',wait_until='domcontentloaded')
 page.wait_for_function("document.querySelector('#interpretStatus').textContent.includes('ready')",timeout=20000)
 page.evaluate('() => {window.testSpeechCount=0;window.speechSynthesis.speak=()=>{window.testSpeechCount++};}')
 assert page.evaluate('window.testSpeechCount')==0
 for draft in ['I WANT WATER PLEASE','NO FOOD PLEASE','BOOK GO FOOD']:
  page.locator('#editMessageButton').click();page.locator('#messageEditor').fill(draft);page.locator('#messageEditForm button[type=submit]').click()
  start=time.monotonic()
  with page.expect_response(lambda r:r.url.endswith('/api/interpret') and r.request.method=='POST',timeout=60000) as received:
   page.locator('#interpretButton').click()
  response=received.value;data=response.json();page.wait_for_function("!document.querySelector('#interpretButton').disabled",timeout=60000)
  row={'input':draft,'httpStatus':response.status,'seconds':round(time.monotonic()-start,2),'response':data,'status':page.locator('#interpretStatus').inner_text()}
  assert response.status==200,row
  assert page.locator('#messageText').inner_text()==draft
  assert page.locator('#interpretOriginal').inner_text()==draft
  if not data['needsClarification']:
   page.locator('#interpretApply').click();assert page.locator('#messageText').inner_text()==data['sentence'];assert page.locator('#interpretOriginal').inner_text()==draft
   page.locator('#interpretUndo').click();assert page.locator('#messageText').inner_text()==draft
   row['applyAndUndo']=True
  else:assert page.locator('#interpretApply').is_disabled()
  row['draftUnchangedUntilApplied']=True
  rows.append(row);print(json.dumps(row),flush=True)
  if len(rows)<3:page.wait_for_timeout(25000)
 assert page.evaluate('window.testSpeechCount')==0
 assert not any('/api/sessions' in u for u in writes)
 assert not errors,errors
 result={'site':'https://handspeak.cvsu.dev','date':'2026-10-03','method':'Manually entered text using motion vocabulary; no physical-camera detection tested. I is typed context.','tests':rows,'automaticSpeech':False,'automaticSave':False,'pageErrors':errors}
 Path('/opt/handspeak/repository/reports/local-llm/live-interpretation-20261003.json').write_text(json.dumps(result,indent=2)+'\n')
 b.close()
