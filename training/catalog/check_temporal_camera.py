"""Private real-time browser prototype using a training clip, not release accuracy."""
import argparse
import base64
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import imageio_ffmpeg
import threading

import torch
from playwright.sync_api import sync_playwright
import run_dynamic_pose_training as extractor

REPO=Path(__file__).resolve().parents[2]
MODEL=Path('/opt/handspeak-training/vocabulary-expansion-focused-release')
ROOT=Path('/opt/handspeak-training/temporal-camera-prototype')


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass


def main():
    global MODEL
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--label',default='CALL');parser.add_argument('--mirror',action='store_true');parser.add_argument('--warm-playback',action='store_true');parser.add_argument('--native-aspect',action='store_true')
    parser.add_argument('--model-dir',type=Path,default=MODEL)
    parser.add_argument('--report',type=Path,default=REPO/'reports/vocabulary-expansion/camera-prototype')
    parser.add_argument('--delegate',choices=['CPU','GPU'],default='CPU')
    parser.add_argument('--image-data',action='store_true')
    parser.add_argument('--buffered',action='store_true')
    parser.add_argument('--capture-interval',type=int,choices=[30,60],default=30)
    parser.add_argument('--recorded-mode',action='store_true')
    parser.add_argument('--camera-format',action='store_true',help='Decode a 960x720, 30 fps letterboxed OBS-like derivative')
    args=parser.parse_args();MODEL=args.model_dir.resolve()
    protocol=json.loads((MODEL/'protocol.json').read_text())
    if args.label not in protocol['labels']: raise ValueError('Only candidate labels allowed')
    if extractor.digest(MODEL/'frozen.pt')!=protocol['checkpointSha256']: raise ValueError('Frozen checkpoint changed')
    source=json.loads(Path('/opt/handspeak-training/vocabulary-expansion-priority-data-v2/protocol.json').read_text())
    data=json.loads(Path(source['source']).read_text())
    row=next(r for r in data if r['split']=='train' and r['label']==args.label and r['sequence'] is not None)
    del data
    ROOT.mkdir(parents=True,exist_ok=True)
    for name in ('gesture-model.js','motion-model.js','automatic-motion.js'):shutil.copyfile(REPO/name,ROOT/name)
    for name in ('temporal-browser.js','temporal-window-browser.js','temporal-camera-prototype.js','temporal-camera-worker.js'):
        shutil.copyfile(REPO/'training/accuracy'/name,ROOT/name)
    (ROOT/'residual-runtime.js').write_text("import {temporalFeatures} from './temporal-browser.js';\n"+(REPO/'training/accuracy/motion-residual-browser.js').read_text())
    shutil.copyfile(extractor.HAND_MODEL,ROOT/'hand.task')
    if args.camera_format:
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-i',row['file'],'-vf','scale=960:720:force_original_aspect_ratio=decrease,pad=960:720:(ow-iw)/2:(oh-ih)/2,fps=30','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',str(ROOT/'clip.mp4')],check=True)
    else: shutil.copyfile(row['file'],ROOT/'clip.mp4')
    saved=torch.load(MODEL/'frozen.pt',weights_only=True)
    feature_mode=protocol.get('featureMode','hands-and-body')
    if feature_mode not in ('hands-and-body','hands-only'):raise ValueError('Unknown feature mode')
    payload=dict(labels=protocol['labels'],outputLabels=protocol['outputLabels'],threshold=protocol['threshold'],margin=protocol['margin'],featureMode=feature_mode,handDelegate=args.delegate,weights=[{k:v.tolist() for k,v in s.items()} for s in saved['states']])
    (ROOT/'model.json').write_text(json.dumps(payload))
    (ROOT/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Private temporal camera diagnostic</title><video muted playsinline></video><canvas width="640" height="480"></canvas>'''+f'<script>window.nativeAspect={json.dumps(args.native_aspect)};window.imageDataInput={json.dumps(args.image_data)};window.bufferedInput={json.dumps(args.buffered)};window.captureInterval={args.capture_interval}</script>'+'''<script type="module" src="./temporal-camera-prototype.js"></script>''')
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(ROOT)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(args=['--no-sandbox','--autoplay-policy=no-user-gesture-required']+(['--use-angle=swiftshader','--enable-unsafe-swiftshader'] if args.delegate=='GPU' else []))
            page=browser.new_page();page.set_default_timeout(120000);page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}',wait_until='domcontentloaded')
            page.wait_for_function('window.ready!==undefined');page.evaluate('async()=>await window.ready')
            preflight=page.evaluate('async mirror=>await window.runClip("./clip.mp4",mirror)',args.mirror) if args.warm_playback and not args.recorded_mode else None
            result=(page.evaluate('async()=>await window.runRecordedClip("./clip.mp4")') if args.recorded_mode else page.evaluate('async mirror=>await window.runClip("./clip.mp4",mirror)',args.mirror))
            result['preflightPlayback']=preflight
            if args.recorded_mode:
                (ROOT/'recorded-mid.png').write_bytes(base64.b64decode(page.evaluate('window.recordedMidFrame').split(',',1)[1]))
            result.update(expected=args.label,sourceSha256=row['sha256'],checkpointSha256=protocol['checkpointSha256'],pageErrors=errors,
                          scope='Single training recording played at wall-clock speed in an isolated browser prototype. GPU option uses software SwiftShader on this server. No face tracker, production integration, independent accuracy, or physical webcam claim.',featureMode=feature_mode,delegate=args.delegate,nativeAspect=args.native_aspect,deployed=False)
            output=args.report;output.mkdir(parents=True,exist_ok=True)
            result['imageDataInput']=args.image_data
            result['cameraFormat']=args.camera_format
            result['buffered']=args.buffered
            result['captureInterval']=args.capture_interval
            result['playbackSha256']=extractor.digest(ROOT/'clip.mp4')
            if args.recorded_mode:result['scope']='Offline browser video decoding and fresh landmark extraction on one training clip. Not real-time camera or independent accuracy.'
            (output/(args.label+('-native' if args.native_aspect else '')+('-mirror' if args.mirror else '')+('-gpu' if args.delegate=='GPU' else '')+('-pixels' if args.image_data else '')+('-recorded' if args.recorded_mode else '')+('-obs' if args.camera_format else '')+('-buffered' if args.buffered else '')+('-60ms' if args.capture_interval==60 else '')+'.json')).write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(result),flush=True);browser.close()
    finally:server.shutdown();server.server_close()


if __name__=='__main__':main()
