"""UI readiness checks only; synthetic personal samples are not accuracy evidence."""
import json,os
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE=os.environ.get('HANDSPEAK_TEST_URL','http://127.0.0.1:8002')
ROOT=Path(__file__).resolve().parents[2]
samples=json.loads((ROOT/'models/asl-words.json').read_text())['samples'][:3]
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(BASE,wait_until='networkidle')
 cards=page.locator('[data-daily-word]');assert cards.count()==5
 assert [cards.nth(i).get_attribute('data-daily-word') for i in range(5)]==['NAME','HOME','HAVE','WANT','LOVE']
 assert page.locator('[data-daily-practice]:disabled').count()==5
 page.locator('[data-daily-word="NAME"] [data-daily-teach]').click()
 assert page.locator('#motionLabel').input_value()=='NAME';assert page.locator('#recognitionMode').input_value()=='words'
 assert page.locator('#motionLabel').is_visible()
 page.locator('[data-daily-word="HOME"] [data-daily-video]').click();assert page.locator('#signExampleVideo').get_attribute('src')=='media/signs/home.mp4'
 # Bad records must not unlock a word.
 page.evaluate("localStorage.setItem('handspeak-motion-v3',JSON.stringify(Array(3).fill({label:'NAME',sequence:[]})))")
 page.reload(wait_until='networkidle');assert page.locator('[data-daily-word="NAME"] [data-daily-practice]').is_disabled()
 personal=[{**r,'label':'NAME'} for r in samples]
 page.evaluate("rows=>localStorage.setItem('handspeak-motion-v3',JSON.stringify(rows))",personal)
 page.reload(wait_until='networkidle');assert page.locator('[data-daily-word="NAME"] [data-daily-practice]').is_enabled()
 assert 'accuracy unverified' in page.locator('[data-daily-word="NAME"] [data-daily-status]').inner_text()
 page.locator('[data-daily-word="NAME"] [data-daily-practice]').click();assert page.locator('#recognitionMode').input_value()=='words'
 page.locator('[data-daily-word="NAME"] [data-daily-teach]').click();page.locator('#motionRemove').click()
 assert page.locator('[data-daily-word="NAME"] [data-daily-practice]').is_disabled()
 for width in [390,1280]:
  page.set_viewport_size({'width':width,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 assert not errors,errors
 print(json.dumps({'dailyWords':5,'untrainedDisabled':True,'invalidSamplesRejected':True,'personalReadinessAndRemoval':True,'mobileFit':True,'pageErrors':errors}))
 b.close()
