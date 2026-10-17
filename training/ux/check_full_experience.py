from pathlib import Path
from playwright.sync_api import sync_playwright
import json
root=Path(__file__).resolve().parents[2];catalog=json.loads((root/'models/motion-vocabulary.json').read_text());packs=json.loads((root/'models/motion-categories/index.json').read_text())['groups'];catalog['items'] += [{'id':'hello','label':'HELLO','note':''}];feedback=[];settings={'go':{'label':'GO','hidden':True,'description':'','video':''}}
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page(viewport={'width':1365,'height':1000});errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)));page.route('https://fonts.googleapis.com/**',lambda r:r.abort())
 def serve(name,mime):
  def handler(route):route.fulfill(body=(root/name).read_text(),content_type=mime)
  return handler
 for name in ['index.html','admin.html']:page.route('**/'+name+'*',serve(name,'text/html'))
 for name in ['app.js','experience-ui.js','vocabulary-settings.js','vocabulary-library.js','motion-studio.js','research-words.js','sign-examples.js','interpretation.js','admin-experience.js','admin.js']:page.route('**/'+name+'?*',serve(name,'text/javascript'))
 page.route('**/experience.css?*',serve('experience.css','text/css'))
 page.route('**/api/vocabulary-settings',lambda route:route.fulfill(json={'items':settings}))
 def match_post(route):
  data=route.request.post_data_json;assert data['consent'] is True;assert set(data)<=set(['predicted','model','missed','expected','verdict','consent'])
  feedback.append({'id':'fixture','status':'pending','created_at':'2026-10-11T00:00:00+00:00',**data});route.fulfill(status=201,json={'ok':True})
 page.route('**/api/match-feedback',match_post)
 page.goto('http://127.0.0.1:8000/index.html#workspace',wait_until='domcontentloaded')
 page.wait_for_selector('#tutorialDialog[open]');page.locator('#tutorialNext').click();assert 'Set up your camera' in page.locator('#tutorialTitle').inner_text();page.locator('#tutorialSkip').click()
 page.wait_for_function("!document.querySelector('#expandedWords').disabled")
 page.locator('#recognitionMode').select_option('words')
 page.locator('#editMessageButton').click();page.locator('#messageEditor').fill('I WANT WATER PLEASE');page.locator('#messageEditForm button[type=submit]').click()
 assert page.locator('.word-chip').count()==4
 page.locator('.word-chip').filter(has_text='WATER').click();page.locator('#wordCorrection').fill('FOOD');page.locator('#wordCorrectionForm button[type=submit]').click()
 assert page.locator('#messageText').inner_text()=='I WANT FOOD PLEASE'
 page.locator('.word-chip').filter(has_text='PLEASE').click();page.locator('#removeChip').click();assert page.locator('#messageText').inner_text()=='I WANT FOOD'
 page.locator('.accessibility-controls>summary').click();page.locator('#textSize').select_option('large');page.locator('#speechRate').select_option('0.8')
 assert page.locator('body').evaluate('(e)=>e.classList.contains("large-text")')
 page.evaluate("document.dispatchEvent(new CustomEvent('handspeak:sentence-state',{detail:{state:'speaking',text:'Speaking…'}}))")
 assert page.locator('#stopSpeechButton').is_enabled();page.locator('#stopSpeechButton').click();assert 'Speech stopped' in page.locator('#sentenceProgress').inner_text()
 page.evaluate("document.dispatchEvent(new CustomEvent('handspeak:camera-match',{detail:{word:'WATER',model:'Default preview'}}))")
 page.locator('#matchWrong').click();page.locator('#expectedWord').fill('PLEASE');page.locator('#feedbackConsent').check();page.locator('#submitMatchFeedback').click()
 page.wait_for_function("document.querySelector('#matchFeedbackStatus').textContent.includes('Submitted')")
 assert len(feedback)==1 and feedback[0]['expected']=='PLEASE'
 page.wait_for_function("document.querySelectorAll('#recordedEvaluationRows tr').length>=4")
 page.locator('.site-header nav a[href="#evaluate"]').click();assert page.locator('#recordedEvaluationRows').is_visible()
 page.locator('.site-header nav a[href="#learn"]').click();assert page.locator('[data-sign-example="go"]').is_hidden()
 page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 page.route('**/api/admin/overview?*',lambda r:r.fulfill(json={'totals':{'users':0,'activeUsers':0,'sessions':0,'evaluations':0},'users':[],'evaluations':[],'database':{'engine':'Test fixture','managementUrl':None}}))
 def overview(route):route.fulfill(json={'vocabulary':catalog['items'],'settings':settings,'videos':['media/signs/hello.mp4'],'feedback':feedback,'llm':{'available':True,'warming':False,'model':'test'},'models':packs})
 page.route('**/api/admin/experience',overview)
 def review(route):feedback[0]['status']=route.request.post_data_json['status'];route.fulfill(json={'ok':True})
 page.route('**/api/admin/match-feedback',review)
 def save(route):
  data=route.request.post_data_json;settings[data['id']]={**data,'label':next(i['label'] for i in catalog['items'] if i['id']==data['id'])};route.fulfill(json={'ok':True})
 page.route('**/api/admin/vocabulary-settings',save)
 page.goto('http://127.0.0.1:8000/admin.html',wait_until='domcontentloaded');page.wait_for_function("document.querySelector('#adminWord').options.length>100")
 page.locator('#adminWord').select_option('hello');page.locator('#adminWordDescription').fill('An edited lesson description.');page.locator('#adminWordHidden').check();page.locator('#adminWordForm button[type=submit]').click()
 page.wait_for_function("document.querySelector('#adminWordStatus').textContent.includes('Saved')")
 assert settings['hello']['hidden'] and settings['hello']['description']=='An edited lesson description.'
 page.locator('#adminWordFeedback button').filter(has_text='Mark reviewed').click();page.wait_for_function("document.querySelector('#adminWordFeedback').textContent.includes('reviewed')")
 assert feedback[0]['status']=='reviewed'
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 assert not errors,errors
 print('PASS: first-use guide, sentence chips/correction/removal, accessible text/speech controls, progress, consented feedback, evaluation counts, hidden lessons, administrator editing/review and mobile width. Mocked APIs; no production data written or camera accuracy tested.')
 b.close()
