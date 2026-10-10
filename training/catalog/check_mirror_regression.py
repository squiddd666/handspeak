"""Replay known failures after the development-only mirror consistency screen."""
import json
from pathlib import Path
import numpy as np
import torch
from body_tip_features import features
from motion_window import align_window
from calibrate_word_thresholds import predictions, sha, write
from train_motion_residual import MotionNet, batch
from check_framing_consistency import agreement
ROOT=Path('/opt/handspeak-training/vocabulary-expansion-framing-calibrated')
REPORT=Path('/opt/handspeak/repository/reports/vocabulary-expansion/framing-calibrated')

def main():
    screen=json.loads((REPORT/'mirror-consistency.json').read_text())
    p=json.loads((ROOT/'protocol.json').read_text())
    if not screen['passesDevelopmentScreen'] or sha(ROOT/'frozen.pt')!=screen['checkpointSha256']:raise ValueError('Development screen failed or model changed')
    saved=torch.load(ROOT/'frozen.pt',weights_only=True);torch.set_num_threads(1)
    model=MotionNet(len(p['outputLabels']),torch.zeros(175),torch.ones(175)).eval();model.load_state_dict(saved['states'][0]);batch.trainer.LABELS=p['labels'];results={}
    for name,manifest,frames in [('signs','vocabulary-expansion-framing-fresh/test-manifest.json','vocabulary-expansion-framing-fresh/frames'),('ordinary','ordinary-movement-fresh22/manifest.json','framing-ordinary-fresh22/frames')]:
        base=ROOT.parent;rows=[]
        for r in json.loads((base/manifest).read_text()):
            row=json.loads((base/frames/(r['sha256']+'.json')).read_text())
            if row['sha256']!=r['sha256'] or sha(r['file'])!=r['sha256']:raise ValueError('Media changed')
            rows.append(align_window(dict(row,body=[None]*len(row['rawFrames']))))
        outputs=[]
        for view in (rows,[batch.trainer.encoding.mirrored(r) for r in rows]):
            with torch.no_grad():scores=model(torch.tensor(np.stack([features(r) for r in view]))).softmax(1).numpy()
            outputs.append(predictions(view,scores,p))
        pred=agreement(*outputs);m=batch.trainer.metrics(rows,pred)
        results[name]=dict(metrics=m,predictions=[dict(sha256=r['sha256'],expected=r['label'],predicted=v) for r,v in zip(rows,pred)])
        print(name,json.dumps({k:v for k,v in m.items() if k!='perWord'}),flush=True)
    write(REPORT/'mirror-regression.json',dict(checkpointSha256=p['checkpointSha256'],scope='Known recording regression only, not fresh independent accuracy',passesRegressionScreen=batch.trainer.gate(results['signs']['metrics']) and results['ordinary']['metrics']['negativeFalse']==0,results=results,deployed=False))

if __name__=='__main__':main()
