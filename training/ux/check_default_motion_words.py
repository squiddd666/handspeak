from pathlib import Path
from playwright.sync_api import sync_playwright
import os
root=Path('/opt/handspeak/repository');live=os.environ.get('CHECK_LIVE')=='1'
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.route('https://fonts.googleapis.com/**',lambda r:r.abort())
 if not live:
  page.route('https://handspeak.cvsu.dev/',lambda r:r.fulfill(body=(root/'index.html').read_text(),content_type='text/html'))
  for name in ['app.js','vocabulary-library.js']:page.route('**/'+name+'?*',lambda r:r.fulfill(body=(root/r.request.url.split('/')[-1].split('?')[0]).read_text(),content_type='text/javascript'))
 for reload in [False,True]:
  if reload:page.reload(wait_until='domcontentloaded')
  else:page.goto('https://handspeak.cvsu.dev/#workspace',wait_until='domcontentloaded')
  page.wait_for_function("document.querySelector('#motionModelStatus').textContent.includes('+ 7 preview words')")
  page.wait_for_function("document.querySelector('#activeVocabulary').textContent.includes('13 words')")
  assert page.locator('#expandedWords').is_checked();assert not page.locator('#researchWordsToggle').is_checked()
 page.locator('#recognitionMode').select_option('words')
 for word in ['hello','water','finish']:
  page.locator('#practiceWord').select_option(word);page.locator('#preparePractice').click();assert page.locator('#expandedWords').is_checked(),word
 page.uncheck('#expandedWords');assert '13 words' not in page.locator('#activeVocabulary').inner_text()
 assert not errors,errors;print('PASS: 13 motion words enabled on fresh load and refresh, retained across practice selection, manual disable works, server preview remains opt-in.');b.close()
