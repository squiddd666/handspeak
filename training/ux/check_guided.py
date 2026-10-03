"""Browser checks for guided navigation, model selection, and privacy opt-in."""
import os,json
from playwright.sync_api import sync_playwright
base=os.environ.get('HANDSPEAK_TEST_URL','http://127.0.0.1:8005')
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(e.stack))
 page.route('https://fonts.googleapis.com/**',lambda r:r.abort())
 if '127.0.0.1' in base:page.route(base+'/api/**',lambda r:r.fulfill(response=r.fetch(url='https://handspeak.cvsu.dev'+r.request.url.split(':8005')[1])))
 page.goto(base,wait_until='domcontentloaded');page.wait_for_function("document.querySelector('#vocabularyStatus').textContent.includes('201 of 201')")
 assert page.locator('#home').is_visible();assert page.locator('#workspace').is_hidden()
 page.locator('nav a[href="#workspace"]').click()
 page.locator('#practiceWord').select_option('name');page.locator('#preparePractice').click()
 assert page.locator('#cameraLesson').is_visible();assert page.locator('#signExampleEmbed').is_visible()
 assert not page.locator('#researchWordsToggle').is_checked(),'Preparation must not opt into server processing'
 assert 'Automatic server capture' in page.locator('#practiceInstructions').inner_text()
 assert 'Automatic server capture' in page.locator('#signExampleMode').inner_text()
 assert page.locator('#researchWords').is_visible()
 page.locator('#practiceWord').select_option('hello');page.locator('#preparePractice').click()
 assert page.locator('#recognitionMode').input_value()=='words'
 assert page.locator('#expandedWords').is_checked()
 assert page.locator('#signExampleVideo').is_visible()
 page.locator('#practiceWord').select_option('water');page.locator('#preparePractice').click()
 page.wait_for_function("document.querySelector('#expandedWords').checked")
 page.locator('nav a[href="#learn"]').click();assert page.locator('#workspace').is_hidden();assert page.locator('#sign-examples').is_visible()
 assert page.locator('#signGrid .sign-card').count()==8
 page.locator('[data-sign-example=love]').click();page.locator('#signExamplePractice').click()
 assert page.locator('#workspace').is_visible();assert page.locator('#researchWordsToggle').is_checked()
 page.locator('nav a[href="#evaluate"]').click();assert page.locator('#measuredResults').is_visible();assert page.locator('#measuredResults tbody tr').count()==5
 page.locator('nav a[href="#history"]').click();assert page.locator('#history').is_visible();assert page.locator('#evaluate').is_hidden()
 page.go_back();assert page.locator('#evaluate').is_visible()
 page.locator('nav a[href="#workspace"]').click();assert page.locator('#interpretTitle').is_visible()
 page.locator('[data-typed-word=I]').click();page.locator('[data-typed-word=AM]').click();page.locator('nav a[href="#learn"]').click();page.locator('nav a[href="#workspace"]').click();assert page.locator('#messageText').inner_text()=='I AM'
 page.set_viewport_size({'width':390,'height':844})
 for name in ['home','workspace','learn','evaluate','ai-studio','history','about']:
  page.locator('nav a[href="#'+name+'"]').click();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),name
 page.screenshot(path='/tmp/guided-mobile.png')
 page.goto(base+'/#sign-examples',wait_until='domcontentloaded');assert page.locator('#sign-examples').is_visible()
 assert not errors,errors
 print(json.dumps({'navigation':True,'wordSelection':True,'explicitServerOptIn':True,'lessonsAtCamera':True,'evaluationTable':True,'mobileViews':True,'deepLinks':True,'pageErrors':errors}))
 b.close()
