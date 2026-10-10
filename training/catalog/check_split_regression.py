"""Known-recording regression screen; never describes these clips as a fresh test."""
import json
from pathlib import Path
import numpy as np
import torch
from body_tip_features import features
from motion_window import align_window
from train_motion_residual import MotionNet,batch
from calibrate_word_thresholds import predictions,sha,write
ROOT=Path('/opt/handspeak-training/vocabulary-expansion-split-ordinary-frozen')
REPORT=Path('/opt/handspeak/repository/reports/vocabulary-expansion/split-ordinary-frozen')
def main():
    p=json.loads((ROOT/'protocol.json').read_text())
    if sha(ROOT/'frozen.pt')!=p['checkpointSha256']:raise ValueError('Frozen model changed')
    saved=torch.load(ROOT/'frozen.pt',weights_only=True);torch.set_num_threads(1);net=MotionNet(len(p['outputLabels']),torch.zeros(175),torch.ones(175)).eval();net.load_state_dict(saved['states'][0]);batch.trainer.LABELS=p['labels'];output={}
    sources=[('signs','vocabulary-expansion-framing-fresh/test-manifest.json','vocabulary-expansion-framing-fresh/frames'),('ordinary','ordinary-movement-fresh22/manifest.json','framing-ordinary-fresh22/frames')]
    for name,manifest,frames in sources:
        directory=Path('/opt/handspeak-training');entries=json.loads((directory/manifest).read_text());rows=[]
        for r in entries:
            row=json.loads((directory/frames/(r['sha256']+'.json')).read_text())
            if row['sha256']!=r['sha256'] or sha(r['file'])!=r['sha256']:raise ValueError('Regression media changed')
            rows.append(row)
        encoded=[features(align_window(dict(r,body=[None]*len(r['rawFrames'])))) for r in rows]
        with torch.no_grad():scores=net(torch.tensor(np.stack(encoded))).softmax(1).numpy()
        pred=predictions(rows,scores,p);metrics=batch.trainer.metrics(rows,pred)
        output[name]=dict(metrics=metrics,predictions=[dict(sha256=r['sha256'],expected=r['label'],predicted=v) for r,v in zip(rows,pred)])
        print(name,json.dumps({k:v for k,v in metrics.items() if k!='perWord'}),flush=True)
    result=dict(checkpointSha256=p['checkpointSha256'],scope='Regression on previously scored sign and ordinary recordings. Not independent accuracy; fresh tests still required.',passesRegressionScreen=batch.trainer.gate(output['signs']['metrics']) and output['ordinary']['metrics']['negativeFalse']==0,results=output,deployed=False)
    write(ROOT/'regression.json',result);write(REPORT/'regression.json',result)
if __name__=='__main__':main()
