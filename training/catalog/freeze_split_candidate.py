"""Freeze a completed split-rejection model only after replaying all development gates."""
import json
from pathlib import Path
import shutil
import numpy as np
import torch
from body_tip_features import features
from camera_framing import scaled
from train_motion_residual import MotionNet,batch
from calibrate_word_thresholds import predictions,sha,write
SOURCE=Path('/opt/handspeak-training/vocabulary-expansion-split-ordinary-rejection')
ROOT=Path('/opt/handspeak-training/vocabulary-expansion-split-ordinary-frozen')
REPORT=Path('/opt/handspeak/repository/reports/vocabulary-expansion/split-ordinary-frozen')
def main():
    if (ROOT/'protocol.json').exists():raise ValueError('Frozen candidate already exists')
    source=json.loads((SOURCE/'protocol.json').read_text());result=json.loads((SOURCE/'validation.json').read_text())
    if not result['passesValidation']:raise ValueError('Development gates failed')
    if sha(source['source'])!=source['sourceSha256'] or sha(SOURCE/'motion-private.pt')!=result['checkpointSha256']:raise ValueError('Training inputs changed')
    p=dict(labels=source['labels'],outputLabels=source['outputLabels'],threshold=result['selected']['threshold'],margin=result['selected']['margin'],featureMode='hands-only',checkpointSha256=result['checkpointSha256'],source=source['source'],sourceSha256=source['sourceSha256'],developmentSha256=source['sourceSha256'],thresholdByLabel={label:result['selected']['threshold'] for label in source['labels']},selection='Completed multiscale training with separate ordinary-action rejection labels; one global validation-selected cutoff',trainingProtocolSha256=sha(SOURCE/'fine-tune-protocol.json'),trainingResultSha256=sha(SOURCE/'validation.json'))
    data=json.loads(Path(p['source']).read_text());val=[r for r in data if r['split']=='val'];del data
    saved=torch.load(SOURCE/'motion-private.pt',weights_only=True);net=MotionNet(len(p['outputLabels']),torch.zeros(175),torch.ones(175)).eval();net.load_state_dict(saved['states'][0]);torch.set_num_threads(1);batch.trainer.LABELS=p['labels'];screens=[]
    for factor in [1,.5625,1.3]:
        rows=[scaled(r,factor) for r in val]
        with torch.no_grad():probs=net(torch.tensor(np.stack([features(r) for r in rows]))).softmax(1).numpy()
        screens.append(dict(scale=factor,metrics=batch.trainer.metrics(rows,predictions(rows,probs,p))))
    if screens!=result['selected']['framingValidation'] or not all(batch.trainer.gate(s['metrics']) for s in screens):raise ValueError('Development replay failed')
    ROOT.mkdir(parents=True,exist_ok=True);shutil.copyfile(SOURCE/'motion-private.pt',ROOT/'frozen.pt');shutil.copyfile(__file__,ROOT/Path(__file__).name)
    write(ROOT/'protocol.json',p);write(REPORT/'protocol.json',p)
    screen=dict(passesDevelopmentScreen=True,framingValidation=screens,checkpointSha256=p['checkpointSha256'],deployed=False)
    write(ROOT/'validation.json',screen);write(REPORT/'validation.json',screen);print(json.dumps(screen),flush=True)
if __name__=='__main__':main()
