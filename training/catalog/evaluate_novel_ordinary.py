"""Frozen eight-word candidate against fresh ordinary full clips and windows."""
import concurrent.futures as futures
import json
import multiprocessing
from pathlib import Path
import numpy as np
import quickjs
import torch
import run_dynamic_pose_training as extractor
from ordinary_windows import window_rows
from body_tip_features import features
from motion_window import align_window
from calibrate_word_thresholds import predictions,sha,write
from train_motion_residual import MotionNet
BASE=Path('/opt/handspeak-training')
MODEL=BASE/'vocabulary-expansion-novel-eight-frozen'
MEDIA=BASE/'novel-eight-ordinary'
ROOT=BASE/'novel-eight-ordinary-evaluation'
REPORT=Path('/opt/handspeak/repository/reports/vocabulary-expansion/novel-eight')
REPO=Path(__file__).resolve().parents[2]

def main():
    p=json.loads((MODEL/'protocol.json').read_text());selection=json.loads((MEDIA/'protocol.json').read_text());review=json.loads((MEDIA/'content-review.json').read_text());rows=json.loads((MEDIA/'manifest.json').read_text())
    if sha(MODEL/'frozen.pt')!=p['checkpointSha256'] or selection['modelProtocolSha256']!=sha(MODEL/'protocol.json') or not review['acceptedForOrdinaryActionScreen'] or review['manifestSha256']!=sha(MEDIA/'manifest.json'):raise ValueError('Frozen inputs/review changed')
    data=json.loads(Path(p['source']).read_text());known={r['sha256'] for r in data};del data
    if known & {r['sha256'] for r in rows}:raise ValueError('Development/test content overlap')
    plan=dict(modelProtocolSha256=sha(MODEL/'protocol.json'),checkpointSha256=p['checkpointSha256'],manifestSha256=sha(MEDIA/'manifest.json'),reviewSha256=sha(MEDIA/'content-review.json'),implementations={str(f):sha(f) for f in [Path(__file__),Path(extractor.__file__),REPO/'training/catalog/ordinary_windows.py',REPO/'training/catalog/body_tip_features.py',REPO/'training/catalog/motion_window.py']},rule='Zero full-clip/window suggestions; at least one usable subwindow per action. All recordings retained, including tracking failures.',deployed=False)
    if (ROOT/'evaluation-protocol.json').exists():raise ValueError('Evaluation already frozen')
    write(ROOT/'evaluation-protocol.json',plan)
    ep=json.loads((BASE/'vocabulary-expansion-dynamic-pose/extraction-protocol.json').read_text());write(ROOT/'extraction-protocol.json',ep);(ROOT/'frames').mkdir(exist_ok=True)
    samples=[]
    with futures.ProcessPoolExecutor(max_workers=1,mp_context=multiprocessing.get_context('spawn')) as pool:
        for path in pool.map(extractor.extract,[(r,str(ROOT),extractor.protocol_digest(ep)) for r in rows]):
            samples.append(json.loads(Path(path).read_text()));print('Extracted',len(samples),'/',len(rows),flush=True)
    js=quickjs.Context()
    for name in ('gesture-model.js','motion-model.js'):js.eval((REPO/name).read_text().replace('export ',''))
    examples=[]
    for row in samples:
        row=dict(row,body=[None]*len(row['rawFrames']),exampleId=row['sha256']);examples.append(align_window(row))
        for w in window_rows(row):
            w['sequence']=json.loads(js.eval('JSON.stringify(encodeMotion('+json.dumps(w['rawFrames'])+','+str(w['imageAspect'])+'))'));examples.append(align_window(w))
    saved=torch.load(MODEL/'frozen.pt',weights_only=True);torch.set_num_threads(1);net=MotionNet(len(p['outputLabels']),torch.zeros(175),torch.ones(175)).eval();net.load_state_dict(saved['states'][0])
    with torch.no_grad():scores=net(torch.tensor(np.stack([features(r) for r in examples]))).softmax(1).numpy()
    pred=predictions(examples,scores,p);coverage={a:len({r['sha256'] for r in examples if r['action']==a and r.get('windowMs') and r['sequence'] is not None}) for a in sorted({r['action'] for r in rows})}
    if any(sha(f)!=h for f,h in plan['implementations'].items()) or sha(MODEL/'frozen.pt')!=p['checkpointSha256']:raise ValueError('Frozen inputs changed')
    result=dict(scope='Fresh recordings from predefined ordinary-action groups, not verified new people or real-time camera accuracy. Subwindows are correlated.',checkpointSha256=p['checkpointSha256'],recordings=len(rows),examplesIncludingWindows=len(examples),usableWindowRecordingsPerAction=coverage,falseSuggestions=sum(v is not None for v in pred),passesOrdinaryScreen=not any(pred) and all(coverage.values()),deployed=False,predictions=[dict(sha256=r['sha256'],exampleId=r['exampleId'],action=r['action'],windowMs=r.get('windowMs'),usable=r['sequence'] is not None,predicted=v) for r,v in zip(examples,pred)])
    write(ROOT/'results.json',result);write(REPORT/'ordinary-results.json',result);write(REPORT/'ordinary-protocol.json',plan);print(json.dumps({k:v for k,v in result.items() if k!='predictions'}),flush=True)
if __name__=='__main__':main()
