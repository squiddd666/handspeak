"""Check recorded accuracy labels using controlled matches; does not test camera accuracy."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json
root=Path(__file__).resolve().parents[2]
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page();errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.route('https://fonts.googleapis.com/**',lambda r:r.abort())
 def serve(name,mime):
  def handler(route):
   content=(root/name).read_text()
   if name=='app.js':content+='\nwindow.__testWordResult=setWordCameraResult;\nwindow.__testVocabulary=vocabularyLibrary;'
   route.fulfill(body=content,content_type=mime)
  return handler
 for name in ['app.js','motion-studio.js','vocabulary-library.js','motion-accuracy.js']:
  page.route('**/'+name+'?*',serve(name,'text/javascript'))
 page.route('**/models/motion-word-accuracy.json',lambda route:route.fulfill(body=(root/'models/motion-word-accuracy.json').read_text(),content_type='application/json'))
 page.route('**/index.html',serve('index.html','text/html'))
 page.goto('http://127.0.0.1:8000/index.html#workspace',wait_until='domcontentloaded')
 page.wait_for_function("window.__testWordResult && !document.querySelector('#expandedWords').disabled && document.querySelector('#motionWordAccuracy').textContent.includes('HELLO')")
 def match(label,daily=False):page.evaluate('(args)=>__testWordResult(args[0],"Possible match — verify before adding",args[1])',[label,daily])
 page.locator('#recognitionMode').select_option('words')
 match('HELLO');assert '91.7% (11/12 clips)' in page.locator('#liveWordAccuracy').inner_text()
 match('WATER');assert 'Not measured' in page.locator('#liveWordAccuracy').inner_text()
 page.locator('#expandedWords').evaluate("e=>{e.checked=true;e.dispatchEvent(new Event('change'))}");match('WATER');assert page.locator('#liveWordAccuracy').inner_text()=='Recorded accuracy: 62.5% (5/8 clips)'
 match('WANT',True);assert '68.2% (15/22 clips)' in page.locator('#liveWordAccuracy').inner_text()
 page.locator('#cameraVocabulary').select_option('single-fish',force=True);page.wait_for_function("document.querySelector('#activeVocabulary').textContent.includes('FISH')")
 match('FISH');assert '75% (3/4 clips)' in page.locator('#liveWordAccuracy').inner_text()
 match('CHARGER');assert 'Not measured' in page.locator('#liveWordAccuracy').inner_text()
 match('No reliable match');assert page.locator('#liveWordAccuracy').is_hidden()
 match('FISH');page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 assert not errors,errors
 print('PASS: WATER, active expanded/default models, daily preview, FISH, missing metrics, no match, mobile fit; controlled results, no camera accuracy claim.')
 b.close()
