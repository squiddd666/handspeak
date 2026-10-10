"""Actual main-app camera path using private video and an isolated SQLite database."""
import argparse
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from playwright.sync_api import sync_playwright
REPO=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--word',required=True);parser.add_argument('--mirror',action='store_true');args=parser.parse_args();slug=args.word.lower()
    model_path=Path('/opt/handspeak-staging/single-word-20261010')/slug/'models/motion-categories'/f'single-{slug}.json'
    model=model_path.read_bytes();import hashlib
    digest=hashlib.sha256(model).hexdigest()
    fixture=Path('/opt/handspeak-training/preview-camera-fixtures')/(args.word+'.mp4')
    if not fixture.exists():raise ValueError('Create an explicit reviewed camera fixture first')
    with tempfile.TemporaryDirectory(prefix='handspeak-single-camera-') as data:
        os.environ.pop('HANDSPEAK_MYSQL_CONFIG',None);os.environ['HANDSPEAK_DATA_DIR']=data
        sys.path.insert(0,str(REPO));import server as application
        assert application.DB_PATH.parent==Path(data) and not application.MYSQL_CONFIG
        application.initialize_database()
        class Quiet(application.HandSpeakHandler):
            def log_message(self,*args):pass
        http=ThreadingHTTPServer(('127.0.0.1',0),Quiet);threading.Thread(target=http.serve_forever,daemon=True).start()
        url=f'http://127.0.0.1:{http.server_port}'
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(args=['--no-sandbox','--autoplay-policy=no-user-gesture-required']);context=browser.new_context(permissions=['camera'])
                context.add_init_script('''
                 navigator.mediaDevices.getUserMedia=async()=>{
                  const c=document.createElement('canvas');c.width=640;c.height=480;const ctx=c.getContext('2d',{willReadFrequently:true}),v=document.createElement('video');v.muted=true;v.playsInline=true;let active=false,last=-Infinity;
                  function draw(now){if(now-last<32){requestAnimationFrame(draw);return;}last=now;ctx.setTransform(1,0,0,1,0,0);ctx.fillStyle='black';ctx.fillRect(0,0,640,480);if(active&&!v.ended){if(window.fixtureMirror)ctx.setTransform(-1,0,0,1,640,0);ctx.drawImage(v,0,0,640,480);}requestAnimationFrame(draw);}requestAnimationFrame(draw);
                  window.playFixture=async()=>{const blob=URL.createObjectURL(await(await fetch('/__private_fixture.mp4')).blob());v.src=blob;await new Promise(r=>v.onloadeddata=r);active=true;await v.play();await new Promise(r=>v.onended=r);active=false;URL.revokeObjectURL(blob);};
                  return c.captureStream(30);
                 };
                ''')
                page=context.new_page();page.set_default_timeout(120000);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                pack=dict(id='single-'+slug,name=args.word,labels=[args.word],file='models/motion-categories/single-'+slug+'.json',sha256=digest)
                page.route('**/models/motion-categories/index.json*',lambda r:r.fulfill(status=200,content_type='application/json',body=json.dumps(dict(version=1,groups=[pack]))))
                page.route('**/'+pack['file']+'*',lambda r:r.fulfill(status=200,content_type='application/json',body=model))
                page.route('**/__private_fixture.mp4',lambda r:r.fulfill(status=200,content_type='video/mp4',body=fixture.read_bytes()))
                page.goto(url);page.wait_for_function("document.querySelector('#motionModelStatus').textContent.includes('6 pretrained')")
                page.locator('.site-header nav a[href="#learn"]').click();page.select_option('#cameraVocabulary',pack['id']);page.wait_for_function("word=>document.querySelector('#motionLibrary').textContent===word",arg=args.word)
                page.locator('#faceTrackingToggle').uncheck();page.locator('#automaticWords').check()
                page.evaluate("document.querySelector('#sentenceAutoAdd').checked=false");page.evaluate('(v)=>window.fixtureMirror=v',args.mirror)
                page.click('#cameraButton');page.wait_for_function('Boolean(document.querySelector("video").srcObject)&&typeof window.playFixture==="function"')
                # Let the actual hand detector finish loading and process blank camera frames.
                page.wait_for_function("document.querySelector('#cameraDiagnostics').textContent.includes('processedFps')")
                page.wait_for_timeout(1500)
                results=[]
                for repetition in range(2):
                    page.evaluate('()=>window.playFixture()');page.wait_for_timeout(6000)
                    text=page.locator('#cameraDiagnostics').text_content();diagnostic=json.loads(text)
                    results.append(dict(repetition=repetition+1,diagnostic=diagnostic,feedback=page.locator('#motionCaptureStatus').text_content()))
                page.click('#cameraButton');browser.close()
            result=dict(word=args.word,mirror=args.mirror,scope='Training video played through the actual main-app getUserMedia/detector/capture/classifier path. Isolated database. Not independent accuracy, physical camera or new-person evidence. Face tracking off.',fixtureSha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),modelSha256=digest,results=results,pageErrors=errors,deployed=False)
            report=REPO/'reports/vocabulary-expansion/single-word'/slug/('main-camera-mirror.json' if args.mirror else 'main-camera.json');report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
            assert not errors,errors
        finally:http.shutdown();http.server_close()
if __name__=='__main__':main()
