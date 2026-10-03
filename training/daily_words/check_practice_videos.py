"""Player selection, local playback, attribution and camera handoff checks."""
import os,json
from playwright.sync_api import sync_playwright
BASE=os.environ.get('HANDSPEAK_TEST_URL','http://127.0.0.1:8005')
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page();errors=[];page.on('pageerror',lambda e:errors.append(e.stack))
 page.route('https://fonts.googleapis.com/**',lambda r:r.abort())
 page.goto(BASE,wait_until='domcontentloaded');page.wait_for_function("document.querySelector('#vocabularyStatus').textContent.includes('201 of 201')")
 assert page.locator('[data-sign-example]').count()==18
 for word,videoid in [('name','GbeC9TFuSX4'),('want','IRUlCZ9jRjM'),('love','DAZB0eVf5t0')]:
  page.locator(f'[data-sign-example={word}]').click();assert page.locator('#signExampleEmbed').is_visible();assert videoid in page.locator('#signExampleEmbed').get_attribute('src');assert page.locator('#signExampleVideo').is_hidden();assert page.locator('.example-playback').is_hidden();assert page.locator('#signExampleLesson').get_attribute('href').endswith(word+'.htm')
  page.locator('#signExamplePractice').click();assert page.locator('#researchWordsToggle').is_checked()
 for word in ['home','have','hello']:
  page.locator(f'[data-sign-example={word}]').click();assert page.locator('#signExampleEmbed').is_hidden();assert page.locator('#signExampleEmbed').get_attribute('src') is None
  page.wait_for_function("document.querySelector('#signExampleVideo').readyState>=2")
  page.locator('#signExampleSpeed').select_option('0.5');page.locator('#signExampleReplay').click();page.wait_for_function("document.querySelector('#signExampleVideo').currentTime>0");assert page.locator('#signExampleVideo').evaluate('(v)=>v.playbackRate')==.5
 page.locator('[data-daily-word=NAME] [data-daily-video]').click();assert 'GbeC9TFuSX4' in page.locator('#signExampleEmbed').get_attribute('src')
 page.locator('#vocabularySearch').fill('LOVE');page.locator('#vocabularyFilter').select_option('video');page.locator('#vocabularyCards').get_by_role('button',name='Watch example').click();assert 'DAZB0eVf5t0' in page.locator('#signExampleEmbed').get_attribute('src')
 page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 assert not errors,errors
 print(json.dumps({'wordButtons':18,'embeddedLessons':3,'localPlayback':True,'dailyAndCatalogLinks':True,'cameraPreviewHandoff':True,'mobileFits':True,'pageErrors':errors}))
 b.close()
