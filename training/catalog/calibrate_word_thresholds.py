"""Select stricter per-word cutoffs using development clips only, before fresh tests."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
import torch
from camera_framing import scaled
from body_tip_features import features
from train_motion_residual import MotionNet
import train_expansion_batch as batch
SOURCE=Path('/opt/handspeak-training/vocabulary-expansion-framing-rejection')
ROOT=Path('/opt/handspeak-training/vocabulary-expansion-framing-calibrated')
REPORT=Path('/opt/handspeak/repository/reports/vocabulary-expansion/framing-calibrated')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,indent=2)+'\n')
def predictions(rows,probs,p):
    output=[]
    for row,scores in zip(rows,probs):
        order=np.argsort(scores);winner,second=order[-1],order[-2];label=p['outputLabels'][winner]
        output.append(label if row['sequence'] is not None and label in p['labels'] and scores[winner]>=p['thresholdByLabel'][label] and scores[winner]-scores[second]>=p['margin'] else None)
    return output

def main():
    if (ROOT/'protocol.json').exists():raise ValueError('Calibration is frozen; use a new experiment directory')
    base=json.loads((SOURCE/'protocol.json').read_text());result=json.loads((SOURCE/'validation.json').read_text())
    if sha(base['source'])!=base['sourceSha256'] or sha(SOURCE/'motion-private.pt')!=result['checkpointSha256']:raise ValueError('Parent inputs changed')
    p=dict(labels=base['labels'],outputLabels=base['outputLabels'],threshold=result['selected']['threshold'],margin=result['selected']['margin'],featureMode='hands-only',checkpointSha256=result['checkpointSha256'],developmentSha256=base['sourceSha256'])
    specification=dict(parentCheckpointSha256=p['checkpointSha256'],developmentSha256=p['developmentSha256'],scales=[1,.5625,1.3],thresholdGrid=[.8,.85,.9,.95,.98,.995,1.],rule='For each word, choose the smallest grid cutoff no lower than the parent global threshold with zero incoming wrong/negative suggestions and at least one correct per framing condition. Keep every target. Failure remains a failure.',scope='Reused development calibration only; not independent accuracy; scaled landmarks retain original visibility mask',implementations={str(Path(__file__)):sha(__file__)},deployed=False)
    write(ROOT/'calibration-plan.json',specification)
    data=json.loads(Path(base['source']).read_text());val=[r for r in data if r['split']=='val'];del data
    rows=[scaled(r,factor) for factor in specification['scales'] for r in val]
    saved=torch.load(SOURCE/'motion-private.pt',weights_only=True)
    if len(saved['states'])!=1:raise ValueError('Expected one frozen member')
    net=MotionNet(len(p['outputLabels']),torch.zeros(175),torch.ones(175)).eval();net.load_state_dict(saved['states'][0]);torch.set_num_threads(1)
    with torch.no_grad():probs=net(torch.tensor(np.stack([features(r) for r in rows]))).softmax(1).numpy()
    winners=probs.argmax(1);p['thresholdByLabel']={};details={}
    for label in p['labels']:
        index=p['outputLabels'].index(label);chosen=1.;passed=False
        for threshold in specification['thresholdGrid']:
            if threshold<p['threshold']:continue
            accepted=[r['sequence'] is not None and winners[i]==index and probs[i,index]>=threshold and probs[i,index]-np.partition(probs[i],-2)[-2]>=p['margin'] for i,r in enumerate(rows)]
            wrong=sum(yes and r['label']!=label for yes,r in zip(accepted,rows))
            coverage=[sum(accepted[j*len(val)+i] and r['label']==label for i,r in enumerate(val)) for j in range(3)]
            if wrong==0 and min(coverage)>0:chosen=threshold;passed=True;break
        p['thresholdByLabel'][label]=chosen;details[label]=dict(threshold=chosen,passes=passed)
    batch.trainer.LABELS=p['labels'];pred=predictions(rows,probs,p);metrics=[]
    for j,factor in enumerate(specification['scales']):metrics.append(dict(scale=factor,metrics=batch.trainer.metrics(val,pred[j*len(val):(j+1)*len(val)])))
    p['calibrationPlanSha256']=sha(ROOT/'calibration-plan.json')
    p['source']=base['source'];p['sourceSha256']=base['sourceSha256'];p['calibrationScope']=specification['scope']
    output=dict(passesDevelopmentScreen=all(x['passes'] for x in details.values()) and all(batch.trainer.gate(x['metrics']) for x in metrics),perWord=details,framingValidation=metrics,checkpointSha256=p['checkpointSha256'],deployed=False)
    shutil.copyfile(SOURCE/'motion-private.pt',ROOT/'frozen.pt');shutil.copyfile(__file__,ROOT/Path(__file__).name)
    write(ROOT/'protocol.json',p);write(ROOT/'validation.json',output);write(REPORT/'validation.json',output);write(REPORT/'protocol.json',p)
    print(json.dumps(output),flush=True)
if __name__=='__main__':main()
