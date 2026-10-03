"""Category loading, isolation, restoration, and network-failure browser checks."""
import json,os
from playwright.sync_api import sync_playwright
BASE=os.environ.get('HANDSPEAK_TEST_URL','http://127.0.0.1:8002')
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page();page.set_default_timeout(60000);errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE,wait_until='networkidle')
 index=page.evaluate("fetch('models/motion-categories/index.json').then(r=>r.json())");groups=index['groups'];assert groups
 page.wait_for_function("document.querySelector('#motionModelStatus').textContent.includes('6 pretrained')")
 for group in groups:
  page.locator('#cameraVocabulary').select_option(group['id']);page.wait_for_function("name=>document.querySelector('#vocabularyCameraStatus').textContent.startsWith(name+' preview:')",arg=group['name'])
  assert group['name'] in page.locator('#activeVocabulary').inner_text()
  library=page.locator('#motionLibrary').inner_text();assert all(word in library for word in group['labels']);assert 'OTHER MOVEMENT' not in library;assert page.locator('#expandedWords').is_disabled()
 # Existing example controls restore their own vocabulary after a category selection.
 page.locator('[data-sign-example="hello"]').click();page.locator('#signExamplePractice').click();page.wait_for_function("document.querySelector('#motionModelStatus').textContent.includes('6 pretrained')");assert page.locator('#cameraVocabulary').input_value()=='';assert 'HELLO' in page.locator('#motionLibrary').inner_text()
 first,second=groups[:2];page.locator('#cameraVocabulary').select_option(first['id']);page.wait_for_function("name=>document.querySelector('#vocabularyCameraStatus').textContent.startsWith(name+' preview:')",arg=first['name'])
 pattern='**/'+second['file']+'*';page.route(pattern,lambda r:r.fulfill(status=503,body='unavailable'));page.locator('#cameraVocabulary').select_option(second['id']);page.wait_for_function("document.querySelector('#vocabularyCameraStatus').textContent.includes('previous camera vocabulary')");assert page.locator('#cameraVocabulary').input_value()==first['id'];assert all(word in page.locator('#motionLibrary').inner_text() for word in first['labels']);page.unroute(pattern)
 page.route('**/models/motion-categories/index.json*',lambda r:r.fulfill(status=503,body='unavailable'));page.locator('#vocabularyRetry').click();page.wait_for_function("document.querySelector('#cameraVocabulary').options.length===1&&!document.querySelector('#vocabularyRetry').disabled");assert page.locator('#cameraVocabulary').input_value()=='';assert 'HELLO' in page.locator('#motionLibrary').inner_text()
 page.locator('#vocabularySearch').fill('hungry');page.get_by_role('button',name='Practice at camera',exact=True).click();page.wait_for_function("document.querySelector('#expandedWords').checked");assert 'HUNGRY' in page.locator('#motionLibrary').inner_text()
 page.locator('#vocabularySearch').fill('');page.set_viewport_size({'width':390,'height':844})
 for category in ['numbers','greetings-communication','health-emergency','question-response-words']:
  page.locator('#vocabularyCategory').select_option(category);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),category
 page.locator('#vocabularyCategory').select_option('numbers');page.locator('#vocabularySearch').fill('1000');assert 'THOUSAND' in page.locator('#vocabularyCards').inner_text()
 assert not errors,errors;print(json.dumps({'loadedCategories':len(groups),'defaultRestored':True,'failedDownloadPreservedPrevious':True,'missingIndexFallsBack':True,'legacyPreviewWorks':True,'mobileFits':True,'numericSearch':True,'pageErrors':errors}));b.close()
