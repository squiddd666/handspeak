"""Check the staged guest interface and separate administrator entry."""
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[2]
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page(viewport={'width':390,'height':844});errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)));page.route('https://fonts.googleapis.com/**',lambda r:r.abort())
 def serve(name,mime):
  def handler(route):route.fulfill(body=(root/name).read_text(),content_type=mime)
  return handler
 for name in ['index.html','account.html','admin.html']:page.route('**/'+name+'*',serve(name,'text/html'))
 for name in ['auth.js','guest-session.js']:page.route('**/'+name+'?*',serve(name,'text/javascript'))
 page.goto('http://127.0.0.1:8000/index.html#workspace',wait_until='domcontentloaded')
 page.wait_for_function("document.querySelector('#interpretStatus').textContent.includes('ready')")
 assert page.locator('#accountButton').count()==0 and page.locator('#accountDialog').count()==0
 assert page.locator('#contrastButton').is_visible()
 page.locator('#editMessageButton').click();page.locator('#messageEditor').fill('WATER PLEASE');page.locator('#messageEditForm button[type=submit]').click()
 assert page.locator('#messageText').inner_text()=='WATER PLEASE'
 page.locator('.site-header nav a[href="#history"]').click();assert page.locator('#historyPrivacy').is_visible()
 assert 'cookie' in page.locator('#historyPrivacy').inner_text()
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 page.goto('http://127.0.0.1:8000/index.html?signin=1',wait_until='domcontentloaded')
 page.wait_for_url('**/account.html?signin=1')
 assert page.locator('#accountDialog').is_visible()
 assert page.locator('#accountSwitch').is_hidden()
 page.locator('#accountClose').click()
 assert page.locator('header a[href="admin.html"]').is_visible()
 assert not errors,errors
 print('PASS: no public account UI, contrast, draft editing, guest history, mobile width, old administrator link redirect, separate login, registration prompt hidden. No production data written.')
 b.close()
