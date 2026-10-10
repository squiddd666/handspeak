"""Evaluate known ordinary recordings and real-timestamp windows without tuning."""
import argparse
import json
from pathlib import Path
import numpy as np
import quickjs
import torch
from ordinary_windows import window_rows
from motion_window import align_window
from body_tip_features import features
from calibrate_word_thresholds import predictions, sha, write
from train_motion_residual import MotionNet
REPO=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--media-root',type=Path,default=Path('/opt/handspeak-training/ordinary-movement-fresh22'))
    parser.add_argument('--frames-root',type=Path,default=Path('/opt/handspeak-training/framing-ordinary-fresh22/frames'))
    parser.add_argument('--output-name',default='ordinary-window-regression.json')
    args=parser.parse_args()
    p=json.loads((args.candidate/'protocol.json').read_text())
    if sha(args.candidate/'frozen.pt')!=p['checkpointSha256']:raise ValueError('Model changed')
    base=Path('/opt/handspeak-training')
    manifest=args.media_root/'manifest.json'
    rows=json.loads(manifest.read_text())
    js=quickjs.Context()
    for name in ('gesture-model.js','motion-model.js'):
        js.eval((REPO/name).read_text().replace('export ',''))
    samples=[]
    for r in rows:
        row=json.loads((args.frames_root/(r['sha256']+'.json')).read_text())
        if sha(r['file'])!=r['sha256'] or row['sha256']!=r['sha256']:raise ValueError('Source changed')
        row=dict(row,body=[None]*len(row['rawFrames']),exampleId=r['sha256'])
        samples.append(align_window(row))
        for window in window_rows(row):
            window['sequence']=json.loads(js.eval('JSON.stringify(encodeMotion('+json.dumps(window['rawFrames'])+','+str(window['imageAspect'])+'))'))
            samples.append(align_window(window))
    saved=torch.load(args.candidate/'frozen.pt',weights_only=True)
    if saved['outputLabels']!=p['outputLabels'] or len(saved['states'])!=1:raise ValueError('Unsupported model')
    torch.set_num_threads(1);model=MotionNet(len(p['outputLabels']),torch.zeros(175),torch.ones(175)).eval();model.load_state_dict(saved['states'][0])
    with torch.no_grad():scores=model(torch.tensor(np.stack([features(r) for r in samples]))).softmax(1).numpy()
    pred=predictions(samples,scores,p)
    coverage={action:len({r['sha256'] for r in samples if r['action']==action and r.get('windowMs') and r['sequence'] is not None}) for action in sorted({r['action'] for r in samples})}
    result=dict(scope='Known-recording regression with correlated timestamp windows, not independent accuracy or real-time segmentation',checkpointSha256=p['checkpointSha256'],manifestSha256=sha(manifest),implementationSha256=sha(__file__),
                recordings=len(rows),examplesIncludingWindows=len(samples),usableWindows=sum(bool(r.get('windowMs')) and r['sequence'] is not None for r in samples),
                usableWindowRecordingsPerAction=coverage,falseSuggestions=sum(v is not None for v in pred),passesRegression=not any(pred) and all(coverage.values()),deployed=False,
                predictions=[dict(sha256=r['sha256'],exampleId=r['exampleId'],action=r['action'],windowMs=r.get('windowMs'),usable=r['sequence'] is not None,predicted=v) for r,v in zip(samples,pred)])
    write(args.report/args.output_name,result)
    print(json.dumps({k:v for k,v in result.items() if k!='predictions'}),flush=True)

if __name__=='__main__':main()
