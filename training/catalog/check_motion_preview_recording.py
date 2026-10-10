"""Feed original training videos through canvas.captureStream into the real preview.

This exercises browser camera timing, not independent sign accuracy or a physical camera.
Raw video remains private and is served only on loopback for the duration of this check.
"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import imageio_ffmpeg
from playwright.sync_api import sync_playwright

REPO=Path(__file__).resolve().parents[2]
ROOT=Path('/opt/handspeak-training/preview-camera-fixtures')
class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
    def translate_path(self,path):
        if path.startswith('/__fixture/'):
            name=path.split('?')[0].split('/')[-1]
            if name in self.server.fixtures:return str(ROOT/name)
        return super().translate_path(path)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels',default='CALL,HOME,HUNGRY,NIGHT')
    parser.add_argument('--mirror',action='store_true')
    args=parser.parse_args();labels=args.labels.split(',')
    source=json.loads(Path('/opt/handspeak-training/vocabulary-expansion-priority-data-v2/protocol.json').read_text())
    data=json.loads(Path(source['source']).read_text());ROOT.mkdir(exist_ok=True)
    clips=[]
    for label in labels:
        row=next(r for r in data if r['split']=='train' and r['label']==label and r['sequence'] is not None)
        name=label+'.mp4';target=ROOT/name
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-i',row['file'],'-vf','scale=960:720:force_original_aspect_ratio=decrease,pad=960:720:(ow-iw)/2:(oh-ih)/2,fps=30','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',str(target)],check=True)
        clips.append(dict(label=label,file=name,sourceSha256=row['sha256'],playbackSha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    del data
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(REPO)));server.fixtures={c['file'] for c in clips}
    threading.Thread(target=server.serve_forever,daemon=True).start()
    results=[];errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(args=['--no-sandbox','--autoplay-policy=no-user-gesture-required'])
            context=browser.new_context(permissions=['camera'])
            context.add_init_script('''
              navigator.mediaDevices.getUserMedia=async()=>{
                const canvas=document.createElement('canvas');canvas.width=960;canvas.height=720;
                const ctx=canvas.getContext('2d',{willReadFrequently:true}),video=document.createElement('video');video.muted=true;video.playsInline=true;
                let active=false,lastDraw=-Infinity;
                function draw(now){if(now-lastDraw<32){requestAnimationFrame(draw);return;}lastDraw=now;ctx.setTransform(1,0,0,1,0,0);ctx.fillStyle='black';ctx.fillRect(0,0,960,720);if(active&&!video.ended){if(window.fixtureMirror)ctx.setTransform(-1,0,0,1,960,0);ctx.drawImage(video,0,0,960,720);}requestAnimationFrame(draw);}requestAnimationFrame(draw);
                window.playFixture=async(url)=>{const blob=URL.createObjectURL(await(await fetch(url)).blob());video.src=blob;await new Promise(resolve=>video.onloadeddata=resolve);active=true;await video.play();await new Promise(resolve=>video.onended=resolve);active=false;URL.revokeObjectURL(blob);};
                return canvas.captureStream(30);
              };
            ''')
            page=context.new_page();page.set_default_timeout(120000);page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(f'http://127.0.0.1:{server.server_port}/motion-preview/index.html')
            page.wait_for_function('!document.querySelector("#start").disabled');page.click('#start')
            page.wait_for_function('document.querySelector("#metrics").textContent.includes("processed frames")')
            page.evaluate('(mirror)=>window.fixtureMirror=mirror',args.mirror)
            for clip in clips:
                page.select_option('#expected',clip['label'])
                page.evaluate('url=>window.playFixture(url)','/__fixture/'+clip['file'])
                page.wait_for_timeout(6000);page.click('#copy')
                report=json.loads(page.input_value('#report'))
                result=dict(**clip,mirror=args.mirror,report=report)
                results.append(result);print(json.dumps(dict(label=clip['label'],events=report['events'],lagMs=report['lagMs'],overloads=report['overloads'])),flush=True)
            page.click('#stop');browser.close()
        output=REPO/'reports/vocabulary-expansion/motion-preview';output.mkdir(exist_ok=True)
        (output/('camera-recordings'+('-mirror' if args.mirror else '')+'.json')).write_text(json.dumps(dict(scope='Training recordings fed through the real preview getUserMedia interface using a browser-generated stream. Not independent accuracy or physical camera evidence.',results=results,pageErrors=errors),indent=2)+'\n')
        assert not errors,errors
    finally:server.shutdown();server.server_close()
if __name__=='__main__':main()
