"""Android browser emulation with a real CPU detector and injected GPU failure.
Not a physical Android device test or a word-accuracy measurement.
"""
import json,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
LIVE='--live' in sys.argv
with sync_playwright() as p:
 browser=p.chromium.launch(args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':393,'height':851},is_mobile=True,has_touch=True,user_agent='Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36')
 page.set_default_timeout(90000);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.route('https://fonts.googleapis.com/**',lambda r:r.abort())
 if not LIVE:
  page.route('**/index.html*',lambda r:r.fulfill(body=(ROOT/'index.html').read_text(),content_type='text/html'))
  for filename in ['app.js','temporal-camera.js']:
   page.route('**/'+filename+'?*',lambda r:r.fulfill(body=(ROOT/r.request.url.split('/')[-1].split('?')[0]).read_text(),content_type='text/javascript'))
 page.route('**/camera-performance.js?*',lambda r:r.fulfill(body="export const preferredVisionDelegate=()=> 'GPU';",content_type='text/javascript'))
 page.add_init_script('''localStorage.setItem('handspeak-tutorial-seen','1');window.audit={attempts:[],tracked:0};navigator.mediaDevices.getUserMedia=async()=>{const c=document.createElement('canvas');c.width=480;c.height=640;const ctx=c.getContext('2d');const v=document.createElement('video');v.muted=true;v.playsInline=true;v.loop=true;v.src='/media/signs/hello.mp4';await v.play();window.sourceVideo=v;setInterval(()=>ctx.drawImage(v,0,0,c.width,c.height),33);return c.captureStream(30);};''')
 page.goto('https://handspeak.cvsu.dev/index.html#workspace',wait_until='domcontentloaded')
 page.wait_for_function("document.querySelector('#motionModelStatus').textContent.includes('pretrained')")
 page.locator('#faceTrackingToggle').evaluate("e=>{for(let p=e.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;}")
 page.uncheck('#faceTrackingToggle');page.select_option('#recognitionMode','words')
 page.evaluate('''async()=>{const vision=await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/+esm');const create=vision.HandLandmarker.createFromOptions.bind(vision.HandLandmarker);vision.HandLandmarker.createFromOptions=async(files,options)=>{audit.attempts.push(options.baseOptions.delegate);if(options.baseOptions.delegate==='GPU')return {detectForVideo(){throw Error('Injected Android GPU context failure')},close(){}};const model=await create(files,options),detect=model.detectForVideo.bind(model);model.detectForVideo=(v,t)=>{const result=detect(v,t);if(result.landmarks.length)audit.tracked++;return result;};return model;};}''')
 page.click('#cameraButton');page.wait_for_function('audit.tracked>=5',timeout=90000)
 page.locator('#copyCameraDiagnostics').evaluate("e=>{for(let p=e.parentElement;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;}")
 page.click('#copyCameraDiagnostics');diagnostics=json.loads(page.locator('#cameraDiagnostics').inner_text())
 assert diagnostics['delegate']=='CPU' and diagnostics['trackerState']=='ready',diagnostics
 assert diagnostics['usableHands']>0,diagnostics
 assert page.evaluate('audit.attempts')==['GPU','CPU']
 page.click('#cameraButton');assert not errors,errors
 result={'deployedAssets':LIVE,'emulation':'Android Chrome, portrait viewport','injectedGpuFailure':True,'realCpuDetectorRecovered':True,'trackedFrames':page.evaluate('audit.tracked'),'diagnostics':diagnostics,'pageErrors':errors,'limitation':'Desktop Chromium emulation with a recorded video; physical Android compatibility and word accuracy are not established.'}
 report=ROOT/('reports/android-tracking-live-check.json' if LIVE else 'reports/android-tracking-check.json');report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 browser.close()
