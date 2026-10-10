"""Staged UI interactions using the running local server; no camera accuracy test."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json
root=Path(__file__).resolve().parents[2]
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page(viewport={'width':1365,'height':1000});errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)));page.route('https://fonts.googleapis.com/**',lambda r:r.abort())
 def serve(name,mime):
  def handler(route):route.fulfill(body=(root/name).read_text(),content_type=mime)
  return handler
 page.route('**/index.html',serve('index.html','text/html'));page.route('**/experience.css?*',serve('experience.css','text/css'))
 page.goto('http://127.0.0.1:8000/index.html#workspace',wait_until='domcontentloaded')
 page.wait_for_function("!document.querySelector('#expandedWords').disabled")
 page.locator('#recognitionMode').select_option('words')
 assert page.locator('#motionAccept').is_visible()
 assert page.locator('#researchWordsToggle').is_hidden()
 page.locator('.word-settings>summary').click();assert page.locator('#researchWordsToggle').is_visible()
 page.locator('.word-settings>summary').click()
 page.locator('.camera-settings>summary').click();assert page.locator('#faceTrackingToggle').is_visible()
 page.locator('#mirrorPreview').uncheck();page.locator('#mirrorPreview').check();page.locator('.camera-settings>summary').click()
 page.locator('#editMessageButton').click();page.locator('#messageEditor').fill('I WANT WATER PLEASE');page.locator('#messageEditForm button[type=submit]').click()
 assert page.locator('#messageText').inner_text()=='I WANT WATER PLEASE'
 assert page.locator('#interpretButton').is_visible()
 page.locator('.output-card details').filter(has=page.locator('[data-typed-word="I"]')).locator('summary').click()
 page.locator('[data-typed-word="I"]').click();assert page.locator('#messageText').inner_text().endswith('I')
 page.locator('.output-card details').filter(has=page.locator('[data-typed-word="I"]')).locator('summary').click()
 page.locator('.practice-disclosure>summary').click();page.locator('#practiceWord').select_option('hello');page.locator('#preparePractice').click()
 assert page.locator('#cameraLesson').is_visible()
 page.screenshot(path='/tmp/handspeak-calm-desktop.png',full_page=True)
 page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 page.screenshot(path='/tmp/handspeak-calm-mobile.png',full_page=True)
 assert not errors,errors
 print('PASS: disclosures, match review button, camera settings, draft editing, typed words, LLM access, practice docking, mobile width; no camera recognition test.')
 b.close()
