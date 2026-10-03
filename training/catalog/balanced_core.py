"""Six-word follow-up: maximize validation recall without exceeding original error counts."""
import sys,json,itertools,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import fit
ROOT=Path('/opt/handspeak-training/vocabulary-v9');fit.ROOT=ROOT
if __name__=='__main__':
 labels=['HELLO','THANK YOU','PLEASE','YES','NO','FINISH'];old=json.loads(Path('/opt/handspeak-training/accuracy-v4/development-features.json').read_text());new=json.loads(Path('/opt/handspeak-training/vocabulary-v8/development-features.json').read_text());baseline=json.loads((fit.SITE/'models/asl-words.json').read_text())
 train=fit.balanced([r for r in old if r['split']=='train' and r.get('sequence') and r['label'] in labels],144);neg=fit.balanced([r for r in old if r['split']=='train' and r.get('sequence') and r['label'] not in labels],18)+fit.balanced([r for r in new if r['split']=='train' and r.get('sequence')],96);refs=[{'label':r['label'],'sequence':r['sequence']} for r in train]+[{'label':'OTHER MOVEMENT','sequence':r['sequence']} for r in neg];val=[r for r in old+new if r['split']=='val']
 bm=fit.metrics(val,fit.outputs(fit.matrix(val,baseline['samples'],'core-baseline-validation'),baseline['samples'],baseline['parameters'],labels),labels);mat=fit.matrix(val,refs,'core-candidate-validation');best=None
 for limit,ratio,votes in itertools.product([.2,.3,.4,.5,.65,.8,1.,1.2],[1.,1.1,1.3,1.5],[1,2]):
  params=dict(maxDistance=limit,minRatio=ratio,minVotes=votes,mirror=True,strongRatio=2);m=fit.metrics(val,fit.outputs(mat,refs,params,labels),labels)
  if m['correct']<=bm['correct'] or m['wrong']>bm['wrong'] or m['negativeFalse']>bm['negativeFalse']:continue
  score=(-m['correct'],m['wrong']+m['negativeFalse'])
  if best is None or score<best[0]:best=(score,params,m)
 report={'baselineValidation':bm,'eligible':bool(best),'selectedValidation':best[2] if best else None,'parameters':best[1] if best else None}
 if best:
  model={**baseline,'labels':labels,'samples':refs,'parameters':best[1]};path=ROOT/'core.json';path.write_text(json.dumps(model,separators=(',',':')));report['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
 (ROOT/'core-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
