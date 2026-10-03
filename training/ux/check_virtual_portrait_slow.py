import json,time
from pathlib import Path
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page();page.set_default_timeout(90000);page.route('https://fonts.googleapis.com/**',lambda r:r.abort())
 page.add_init_script('''window.audit={events:[],frames:[],flip:false};navigator.mediaDevices.getUserMedia=async()=>{const c=document.createElement('canvas');c.width=480;c.height=640;const ctx=c.getContext('2d');window.auditVideo=document.createElement('video');auditVideo.muted=true;auditVideo.playsInline=true;setInterval(()=>{ctx.save();ctx.fillStyle='black';ctx.fillRect(0,0,c.width,c.height);if(audit.flip){ctx.translate(c.width,0);ctx.scale(-1,1);}if(auditVideo.readyState>=2&&!auditVideo.ended)ctx.drawImage(auditVideo,0,0,c.width,c.height);ctx.restore();},33);return c.captureStream(30);};''')
 page.route('**/test-water-please-finish-portrait-slow.mp4',lambda r:r.fulfill(body=Path('/opt/handspeak/repository/media/signs/test-water-please-finish-portrait-slow.mp4').read_bytes(),content_type='video/mp4'))
 page.goto('https://handspeak.cvsu.dev/#workspace',wait_until='domcontentloaded');page.wait_for_function("document.querySelector('#motionModelStatus').textContent.includes('6 pretrained')")
 page.uncheck('#faceTrackingToggle');page.select_option('#recognitionMode','words');page.wait_for_function("!document.querySelector('#expandedWords').disabled");page.check('#expandedWords')
 page.evaluate('''async()=>{const vision=await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/+esm');const original=vision.HandLandmarker.createFromOptions.bind(vision.HandLandmarker);vision.HandLandmarker.createFromOptions=async(files,options)=>{options.baseOptions.delegate='CPU';const detector=await original(files,options),detect=detector.detectForVideo.bind(detector);detector.detectForVideo=(video,t)=>{const start=performance.now(),r=detect(video,t);audit.frames.push({time:auditVideo.currentTime,ms:performance.now()-start,landmarks:r.landmarks,handedness:r.handedness});return r;};return detector;};new MutationObserver(()=>audit.events.push({time:auditVideo.currentTime,text:document.querySelector('#liveLetter').textContent})).observe(document.querySelector('#liveLetter'),{childList:true,subtree:true,characterData:true});}''')
 page.click('#cameraButton');page.wait_for_function("document.querySelector('#cameraStatus').textContent.includes('Live')")
 for flip in [False]:
  page.uncheck('#automaticWords');page.wait_for_timeout(1000)
  page.evaluate('''async flip=>{audit.flip=flip;audit.frames=[];audit.events=[];auditVideo.src='/media/signs/test-water-please-finish-portrait-slow.mp4';await new Promise((r,j)=>{auditVideo.onloadedmetadata=r;auditVideo.onerror=j;});document.querySelector('#automaticWords').checked=true;document.querySelector('#automaticWords').dispatchEvent(new Event('change'));await auditVideo.play();await new Promise(r=>auditVideo.onended=r);await new Promise(r=>setTimeout(r,1500));}''',flip)
  report=page.evaluate('({flip:audit.flip,events:audit.events,frames:audit.frames,status:document.querySelector("#motionCaptureStatus").textContent})')
  Path('/opt/handspeak/repository/reports/virtual-camera/'+('portrait-flipped' if flip else 'portrait-slow-normal')+'.json').write_text(json.dumps(report))
  print(json.dumps({'flip':flip,'events':report['events'],'trackedFrames':sum(bool(f['landmarks']) for f in report['frames']),'frames':len(report['frames']),'status':report['status']}),flush=True)
 b.close()
