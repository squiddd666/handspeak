"""Retrain the six default words using development-only reference and metric selection."""
import sys,json,itertools,hashlib
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from refine import fit,converted,CONFIGS,score,OUT,ROOT
if __name__=='__main__':
 labels=['HELLO','THANK YOU','PLEASE','YES','NO','FINISH'];old=json.loads(Path('/opt/handspeak-training/accuracy-v4/development-features.json').read_text());new=json.loads((ROOT/'development-features.json').read_text())
 train=fit.balanced([r for r in old if r['split']=='train' and r.get('sequence') and r['label'] in labels],144)
 negatives=fit.balanced([r for r in old+new if r['split']=='train' and r.get('sequence') and r['label'] not in labels],48)
 refs=[{'label':r['label'],'sequence':r['sequence']} for r in train]+[{'label':'OTHER MOVEMENT','sequence':r['sequence']} for r in negatives]
 val=[r for r in old if r['split']=='val']+fit.balanced([r for r in new if r['split']=='val'],48)
 original=json.loads((fit.SITE/'models/asl-words.json').read_text());baseline=fit.metrics(val,fit.outputs(fit.matrix(val,original['samples'],'core-original-validation'),original['samples'],original['parameters'],labels),labels)
 best=None;trials=[]
 for n,c in enumerate([None]+CONFIGS):
  transformed=converted(refs,c) if c else refs;rows=converted(val,c) if c else val;mat=fit.matrix(rows,transformed,'core-refine-'+str(n))
  for limit,ratio,votes in itertools.product([.15,.2,.3,.4,.5,.65,.8,1.0],[1.0,1.1,1.3,1.5],[1,2]):
   params=dict(maxDistance=limit,minRatio=ratio,minVotes=votes,mirror=True,strongRatio=2);m=fit.metrics(val,fit.outputs(mat,transformed,params,labels),labels)
   if best is None or score(m)<best[0]:best=(score(m),c,params,m)
  trials.append({'config':c,'bestSoFar':best[3]});print('Core',n,'baseline',baseline,'best',best[3],flush=True)
 model={'version':1,'encoding':'two-hand-motion-v3','status':'research-candidate','labels':labels,'samples':refs,'parameters':best[2],'featureTransform':best[1],'attribution':original.get('attribution','PopSign ASL, Georgia Tech and DPAN, CC BY 4.0')}
 path=OUT/'core.json';path.write_text(json.dumps(model,separators=(',',':')))
 (OUT/'core-validation.json').write_text(json.dumps({'baseline':baseline,'selected':best[3],'featureTransform':best[1],'parameters':best[2],'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'trials':trials,'eligibleOnValidation':best[3]['correct']>baseline['correct'] and best[3]['wrong']<=baseline['wrong'] and best[3]['negativeFalse']<=baseline['negativeFalse']},indent=2))
