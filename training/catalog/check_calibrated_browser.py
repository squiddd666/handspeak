"""Compare the actual preview classifier against frozen Python decisions."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import threading
import numpy as np
import torch
from playwright.sync_api import sync_playwright
from camera_framing import scaled
from motion_window import align_window
from body_tip_features import features
from train_motion_residual import MotionNet
from calibrate_word_thresholds import predictions,sha
REPO=Path(__file__).resolve().parents[2]
ROOT=Path('/opt/handspeak-training/vocabulary-expansion-framing-calibrated')
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',type=Path,default=ROOT)
    parser.add_argument('--preview-root',type=Path,default=REPO)
    parser.add_argument('--report',type=Path,default=REPO/'reports/vocabulary-expansion/framing-calibrated/browser-parity.json')
    args=parser.parse_args()
    root=args.candidate;preview=args.preview_root
    p=json.loads((root/'protocol.json').read_text())
    if sha(root/'frozen.pt')!=p['checkpointSha256'] or sha(p['source'])!=p['sourceSha256']:raise ValueError('Frozen input changed')
    data=json.loads(Path(p['source']).read_text());samples={}
    for row in data:
        if row['split']=='val':samples.setdefault((row['label'],row['sequence'] is not None),row)
    rows=[align_window(scaled(r,factor)) for factor in [1,.5625,1.3] for r in samples.values()];del data
    inputs=np.stack([features(r) for r in rows]);saved=torch.load(root/'frozen.pt',weights_only=True);torch.set_num_threads(1)
    net=MotionNet(len(p['outputLabels']),torch.zeros(175),torch.ones(175)).eval();net.load_state_dict(saved['states'][0])
    with torch.no_grad():probs=net(torch.tensor(inputs)).softmax(1).numpy()
    expected=predictions(rows,probs,p)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(preview)));threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(args=['--no-sandbox']);page=browser.new_page();page.goto(f'http://127.0.0.1:{server.server_port}/motion-preview/index.html')
            result=page.evaluate('''async data=>{
              const {classifyRow}=await import('./classifier.js'),{bodyTipFeatures}=await import('./runtime.js'),model=await(await fetch('./model.json')).json();
              let error=0;const timings=[],decisions=[];
              for(let i=0;i<data.rows.length;i++){
                const started=performance.now(),row=data.rows[i],input=bodyTipFeatures(row);
                input.forEach((channel,c)=>channel.forEach((v,t)=>error=Math.max(error,Math.abs(v-data.inputs[i][c][t]))));
                decisions.push(classifyRow(model,row).label);timings.push(performance.now()-started);
              }
              timings.sort((a,b)=>a-b);
              return {checkpointSha256:model.checkpointSha256,samples:decisions.length,maxFeatureError:error,predictionsMatch:decisions.every((v,i)=>v===data.expected[i]),medianMs:timings[Math.floor(timings.length/2)],p95Ms:timings[Math.floor(timings.length*.95)]};
            }''',dict(rows=[{k:r[k] for k in ['rawFrames','body','imageAspect','sequence']} for r in rows],inputs=inputs.tolist(),expected=expected));browser.close()
        assert result['checkpointSha256']==p['checkpointSha256'] and result['predictionsMatch'] and result['maxFeatureError']<1e-5,result
        result.update(scope='Actual preview classifier parity on repeated development framing conditions; timing excludes hand detection. Not independent accuracy.',labelsCovered=len({r['label'] for r in rows}),classifierSha256=sha(preview/'motion-preview/classifier.js'),modelJsonSha256=sha(preview/'motion-preview/model.json'))
        report=args.report;report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    finally:server.shutdown();server.server_close()
if __name__=='__main__':main()
