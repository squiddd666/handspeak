"""Freeze an eight-word candidate after known failures; fresh tests are mandatory."""
import json
from pathlib import Path
import shutil
import numpy as np
import torch
from camera_framing import scaled
from body_tip_features import features
from train_motion_residual import MotionNet,batch
from calibrate_word_thresholds import predictions,sha,write
SOURCE=Path('/opt/handspeak-training/vocabulary-expansion-windowed-ordinary-frozen')
ROOT=Path('/opt/handspeak-training/vocabulary-expansion-novel-eight-frozen')
REPORT=Path('/opt/handspeak/repository/reports/vocabulary-expansion/novel-eight')
LABELS=['CALL','FIND','FISH','MORNING','NIGHT','PAIN','SEE','SICK']

def main():
    if (ROOT/'protocol.json').exists():raise ValueError('Candidate already frozen')
    p=json.loads((SOURCE/'protocol.json').read_text())
    if sha(SOURCE/'frozen.pt')!=p['checkpointSha256'] or sha(p['source'])!=p['sourceSha256']:raise ValueError('Inputs changed')
    p.update(labels=LABELS,thresholdByLabel={label:p['thresholdByLabel'][label] for label in LABELS},
             selection='Exclude existing main-site HOME, HAVE and HUNGRY; release candidates are eight new words only. Selection occurred AFTER viewing previous regression failures; those recordings are not independent release evidence. Fresh recordings required.',
             rule='Full original output competition remains. Excluded winners are rejected; no renormalization, fallback or threshold change.',
             selectionImplementationSha256=sha(__file__),parentProtocolSha256=sha(SOURCE/'protocol.json'))
    write(ROOT/'selection-plan.json',p)
    data=json.loads(Path(p['source']).read_text());rows=[r for r in data if r['split']=='val'];del data
    saved=torch.load(SOURCE/'frozen.pt',weights_only=True);torch.set_num_threads(1);batch.trainer.LABELS=LABELS
    net=MotionNet(len(p['outputLabels']),torch.zeros(175),torch.ones(175)).eval();net.load_state_dict(saved['states'][0]);screens=[]
    for factor in [1,.5625,1.3]:
        view=[scaled(r,factor) for r in rows]
        with torch.no_grad():probs=net(torch.tensor(np.stack([features(r) for r in view]))).softmax(1).numpy()
        screens.append(dict(scale=factor,metrics=batch.trainer.metrics(rows,predictions(view,probs,p))))
    passed=all(batch.trainer.gate(r['metrics']) for r in screens)
    screen=dict(passesDevelopmentScreen=passed,framingValidation=screens,checkpointSha256=p['checkpointSha256'],deployed=False)
    write(ROOT/'validation.json',screen);write(REPORT/'validation.json',screen)
    if not passed:raise ValueError('Reduced vocabulary still fails development screen')
    shutil.copyfile(SOURCE/'frozen.pt',ROOT/'frozen.pt');shutil.copyfile(__file__,ROOT/Path(__file__).name)
    write(ROOT/'protocol.json',p);write(REPORT/'protocol.json',p)
    print(json.dumps(screen),flush=True)
if __name__=='__main__':main()
