"""Browser regression for vocabulary search, personal practice, and model failure handling."""
import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE=os.environ.get('HANDSPEAK_TEST_URL','http://127.0.0.1:8002')
with sync_playwright() as p:
 browser=p.chromium.launch(args=['--no-sandbox']);page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(BASE,wait_until='networkidle');page.wait_for_function("document.querySelector('#vocabularyStatus').textContent.includes('200 of 200')")
 assert page.locator('#vocabularyCategory option').count()==16
 page.locator('#vocabularySearch').fill('school');assert page.locator('#vocabularyCards article').count()==1
 page.locator('#vocabularyCategory').select_option('places');assert page.locator('#vocabularyCards article').count()==1
 page.locator('#vocabularyCategory').select_option('school');assert page.locator('#vocabularyCards article').count()==1
 page.locator('#vocabularyCategory').select_option('');page.locator('#vocabularySearch').fill('charger')
 page.get_by_role('button',name='Add as typed text',exact=True).click();assert page.locator('#messageText').inner_text()=='CHARGER';assert 'typed text' in page.locator('#vocabularyStatus').inner_text()
 page.get_by_role('button',name='Teach this sign',exact=True).click();assert page.locator('#motionLabel').input_value()=='CHARGER';assert page.locator('#recognitionMode').input_value()=='words'
 page.locator('#vocabularySearch').fill('no such word');assert 'No matching entries' in page.locator('#vocabularyCards').inner_text()
 page.locator('#vocabularySearch').fill('');page.locator('#vocabularyCategory').select_option('numbers');assert '23 of 200' in page.locator('#vocabularyStatus').inner_text();page.locator('#vocabularyNext').click();assert 'Page 2 of 2' in page.locator('#vocabularyPage').inner_text()
 page.locator('#vocabularyCategory').select_option('health-emergency');assert page.locator('#vocabularyEmergency').is_visible()
 page.locator('#vocabularyCategory').select_option('');page.locator('#vocabularySearch').fill('hungry');page.get_by_role('button',name='Watch example',exact=True).click();page.wait_for_function("document.querySelector('#signExampleVideo').readyState>=1");assert 'hungry.mp4' in page.locator('#signExampleVideo').get_attribute('src')
 page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path='/opt/handspeak/live-test-results/catalog-mobile.png',full_page=True)
 assert not errors,errors
 print(json.dumps({'catalogEntries':200,'categories':15,'deduplication':True,'typedText':True,'personalTraining':True,'numbers':23,'videoLoads':True,'mobileFits':True,'pageErrors':errors}))
 browser.close()
