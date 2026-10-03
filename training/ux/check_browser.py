import os
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(os.environ.get('HANDSPEAK_TEST_URL','http://127.0.0.1:8002'),wait_until='networkidle')
 assert page.locator('nav a').all_text_contents()==['Home','Sign Recognition','Learn','AI Studio','History','Evaluation','About']
 assert page.locator('#supported-vocabulary article').count()==3
 assert page.locator('#ai-studio #interpretButton').count()==1
 assert page.locator('#workspace #motionAccept').count()==1
 assert not page.evaluate("document.body.innerText.includes('100%')")
 assert page.evaluate("Array.from(document.querySelectorAll('[id]')).length===new Set(Array.from(document.querySelectorAll('[id]'),n=>n.id)).size")
 page.screenshot(path='/opt/handspeak/live-test-results/ux-desktop.png')
 page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 assert page.locator('nav a').nth(1).is_visible()
 page.screenshot(path='/opt/handspeak/live-test-results/ux-mobile.png')
 page.locator('#recognitionMode').select_option('words');assert 'Camera off' in page.locator('#recognitionFeedback').inner_text()
 page.locator('#recognitionMode').select_option('letters');page.locator('#demoButton').click();page.wait_for_timeout(1500);assert 'simulated' in page.locator('#recognitionFeedback').inner_text()
 assert not errors,errors
 print('UX browser checks passed: navigation, tiers, feature placement, mobile fit, mode reset, demo labeling; no page errors.')
 b.close()
