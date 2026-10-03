from pathlib import Path
from playwright.sync_api import sync_playwright
import os
root=Path('/opt/handspeak/repository');live=os.environ.get('CHECK_LIVE')=='1'
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.route('https://fonts.googleapis.com/**',lambda r:r.abort())
 if not live:
  page.route('https://handspeak.cvsu.dev/',lambda r:r.fulfill(body=(root/'index.html').read_text(),content_type='text/html'))
  for name in ['app.js','vocabulary-library.js']:page.route('**/'+name+'?*',lambda r:r.fulfill(body=(root/r.request.url.split('/')[-1].split('?')[0]).read_text(),content_type='text/javascript'))
 page.goto('https://handspeak.cvsu.dev/#workspace',wait_until='domcontentloaded');page.wait_for_function("!document.querySelector('#expandedWords').disabled&&document.querySelector('#motionModelStatus').textContent.includes('6 pretrained')")
 for word in ['water','please','finish']:
  page.locator('#practiceWord').select_option(word);page.locator('#preparePractice').click();page.wait_for_function("document.querySelector('#activeVocabulary').textContent.includes('extra-word preview')")
  assert page.locator('#expandedWords').is_checked(),word
  assert not page.locator('#researchWordsToggle').is_checked(),word
  assert '+ 7 preview words' in page.locator('#motionModelStatus').inner_text(),word
 page.uncheck('#expandedWords');page.locator('#practiceWord').select_option('finish');page.locator('#preparePractice').click();assert not page.locator('#expandedWords').is_checked()
 assert not errors,errors;print('PASS: WATER -> PLEASE -> FINISH retains extra-word model; explicit opt-out retained; no page errors.');b.close()
