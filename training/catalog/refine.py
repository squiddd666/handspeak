"""Validation-only experiment: separate local hand shape from wrist movement.
Previously inspected v7 test data is used only as a regression check after freezing.
"""
import sys,json,hashlib,itertools
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import fit
ROOT=fit.ROOT;OUT=ROOT/'refinement';OUT.mkdir(exist_ok=True)
CONFIGS=[{'wristWeight':.25,'localScale':False},{'wristWeight':.5,'localScale':False},{'wristWeight':.5,'localScale':True},{'wristWeight':1.,'localScale':True}]
def transform(sequence,config):
 if sequence is None:return None
 a=np.array(sequence,dtype=float).copy()
 for offset in [0,64]:
  present=a[:,offset]>0;points=a[:,offset+1:offset+64].reshape(-1,21,3);wrist=points[:,0:1,:].copy();local=points-wrist
  if config['localScale']:
   scale=np.maximum(.2,np.linalg.norm(points[:,5,:2]-points[:,17,:2],axis=1));local/=scale[:,None,None]
  points[:]=local+wrist*config['wristWeight'];points[~present]=0
 return a.tolist()
def converted(rows,c):return [{**r,'sequence':transform(r.get('sequence'),c)} for r in rows]
def score(m):return (4*m['wrong']+4*m['negativeFalse']+m['missed'],m['wrong']+m['negativeFalse'],-m['correct'])
if __name__=='__main__':
 dev=json.loads((ROOT/'development-features.json').read_text());old=json.loads(Path('/opt/handspeak-training/accuracy-v4/development-features.json').read_text());index=json.loads((ROOT/'frozen-index.json').read_text());reports={};newindex=[]
 for group in index['groups']:
  original=json.loads((ROOT/'models'/Path(group['file']).name).read_text());labels=original['labels'];wanted=[i['label'] for i in json.loads((fit.SITE/'models/motion-vocabulary.json').read_text())['items'] if group['id'] in i['categories']]
  rows=[r for r in dev if r['split']=='val' and r['label'] in wanted]+fit.balanced([r for r in old if r['split']=='val' and r['label'] not in labels],18)+fit.balanced([r for r in dev if r['split']=='val' and r['label'] not in wanted],18)
  baseline=group['validation'];best=(score(baseline),None,original['parameters'],baseline);trials=[]
  for number,c in enumerate(CONFIGS):
   refs=converted(original['samples'],c);mat=fit.matrix(converted(rows,c),refs,group['id']+'-refine-'+str(number))
   for limit,ratio,votes in itertools.product([.15,.2,.3,.4,.5,.65,.8],[1.1,1.3,1.5],[1,2]):
    params=dict(maxDistance=limit,minRatio=ratio,minVotes=votes,mirror=True,strongRatio=2);m=fit.metrics(rows,fit.outputs(mat,refs,params,labels),labels)
    # Candidate must improve recall without increasing validation wrong suggestions.
    if m['correct']>baseline['correct'] and m['wrong']<=baseline['wrong'] and m['negativeFalse']<=baseline['negativeFalse'] and score(m)<best[0]:best=(score(m),c,params,m)
   trials.append({'config':c,'bestSoFar':best[3]})
  model={**original,'parameters':best[2],'featureTransform':best[1]};path=OUT/(group['id']+'.json');path.write_text(json.dumps(model,separators=(',',':')));digest=hashlib.sha256(path.read_bytes()).hexdigest()
  reports[group['id']]={'baselineValidation':baseline,'selectedValidation':best[3],'featureTransform':best[1],'parameters':best[2],'sha256':digest,'trials':trials};newindex.append({**group,'sha256':digest,'validation':best[3],'featureTransform':best[1]})
  (OUT/'validation.json').write_text(json.dumps(reports,indent=2));print(group['id'],json.dumps(reports[group['id']]),flush=True)
 (OUT/'frozen-index.json').write_text(json.dumps({'version':1,'groups':newindex},indent=2))
