"""Broad negative coverage; select recall improvements under paired validation error limits."""
import sys,json,hashlib,itertools
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import fit
ROOT=Path('/opt/handspeak-training/vocabulary-v9');ROOT.mkdir(exist_ok=True);fit.ROOT=ROOT
if __name__=='__main__':
 dev=json.loads(Path('/opt/handspeak-training/vocabulary-v8/development-features.json').read_text());old=json.loads(Path('/opt/handspeak-training/accuracy-v4/development-features.json').read_text());catalog=json.loads((fit.SITE/'models/motion-vocabulary.json').read_text());prior=Path('/opt/handspeak-training/vocabulary-v7/models');out=ROOT/'models';out.mkdir(exist_ok=True);index=[];reports={}
 for group in catalog['categories']:
  oldpath=prior/(group['id']+'.json')
  if not oldpath.exists():continue
  baseline=json.loads(oldpath.read_text());wanted=[i['label'] for i in catalog['items'] if group['id'] in i['categories'] and i['sourceVersion']=='v1_0'];train=[r for r in dev if r['split']=='train' and r.get('sequence') and r['label'] in wanted];labels=[l for l in wanted if sum(r['label']==l for r in train)>=3];train=[r for r in train if r['label'] in labels]
  negatives=fit.balanced([r for r in old if r['split']=='train' and r.get('sequence') and r['label'] not in wanted],18)+fit.balanced([r for r in dev if r['split']=='train' and r.get('sequence') and r['label'] not in wanted],96)
  refs=[{'label':r['label'],'sequence':r['sequence']} for r in train]+[{'label':'OTHER MOVEMENT','sequence':r['sequence']} for r in negatives];val=[r for r in dev if r['split']=='val']+fit.balanced([r for r in old if r['split']=='val' and r['label'] not in wanted],18)
  bm=fit.metrics(val,fit.outputs(fit.matrix(val,baseline['samples'],group['id']+'-baseline-validation'),baseline['samples'],baseline['parameters'],baseline['labels']),wanted);mat=fit.matrix(val,refs,group['id']+'-candidate-validation');best=None
  for limit,ratio,votes in itertools.product([.15,.2,.3,.4,.5,.65,.8,1.0,1.2],[1.,1.1,1.3,1.5],[1,2]):
   params=dict(maxDistance=limit,minRatio=ratio,minVotes=votes,mirror=True,strongRatio=2);m=fit.metrics(val,fit.outputs(mat,refs,params,labels),wanted)
   if m['correct']<=bm['correct'] or m['wrong']>bm['wrong'] or m['negativeFalse']>bm['negativeFalse']:continue
   score=(-m['correct'],m['wrong']+m['negativeFalse'])
   if best is None or score<best[0]:best=(score,params,m)
  if best:
   model={**baseline,'labels':labels,'samples':refs,'parameters':best[1]};vm=best[2]
  else:model=baseline;vm=bm
  path=out/oldpath.name;path.write_text(json.dumps(model,separators=(',',':')));digest=hashlib.sha256(path.read_bytes()).hexdigest();reports[group['id']]={'baselineValidation':bm,'validation':vm,'eligible':bool(best),'negativeTrainingLabels':sorted({r['label'] for r in negatives}),'positiveReferences':len(train),'negativeReferences':len(negatives),'sha256':digest};index.append({'id':group['id'],'name':group['name'],'labels':model['labels'],'file':'models/motion-categories/'+path.name,'sha256':digest,'validation':vm,'validationEligible':bool(best)});print(group['id'],bm,'->',vm,'eligible',bool(best),flush=True)
 (ROOT/'validation-report.json').write_text(json.dumps(reports,indent=2));(ROOT/'frozen-index.json').write_text(json.dumps({'version':1,'groups':index},indent=2))
