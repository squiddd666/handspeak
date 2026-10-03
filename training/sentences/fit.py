import sys,json,itertools,hashlib
from pathlib import Path
import numpy as np
sys.path[:0]=['/opt/handspeak/repository/training/vocabulary','/opt/handspeak/repository/training','/opt/handspeak/repository/training/accuracy']
import fit_expansion as fit
from temporal import nuisance
from dtw import encode
ROOT=Path('/opt/handspeak-training/vocabulary-v6');SITE=Path('/opt/handspeak/repository');NEW=['FOOD','HUNGRY','LIKE','GO'];fit.ROOT=ROOT

def old_predictions(mat,old,extra):
 b=fit.outputs(mat[:,:len(old['samples'])],old['samples'],old['parameters'])
 x=fit.outputs(mat[:,:len(old['samples'])+len(extra['samples'])],old['samples']+extra['samples'],extra['parameters'])
 return [a or (p if p in extra['labels'] else None) for a,p in zip(b,x)]
def metrics(rows,out):
 result={}
 for name,ix in [('new',[i for i,r in enumerate(rows) if r['label'] in NEW]),('existing',[i for i,r in enumerate(rows) if r['kind']=='supported' and r['label'] not in NEW]),('negative',[i for i,r in enumerate(rows) if r['kind']!='supported'])]:
  result[name]=dict(total=len(ix),correct=sum(out[i]==rows[i]['label'] for i in ix),wrong=sum(out[i]!=None and out[i]!=rows[i]['label'] for i in ix))
 return result
if __name__=='__main__':
 old=json.loads((SITE/'models/asl-words.json').read_text());extra=json.loads((SITE/'models/asl-extra-words.json').read_text());(ROOT/'previous-extra.json').write_text(json.dumps(extra))
 dev=json.loads((ROOT/'development-features.json').read_text());prev=json.loads(Path('/opt/handspeak-training/accuracy-v4/development-features.json').read_text());v5=json.loads(Path('/opt/handspeak-training/vocabulary-v5/development-features.json').read_text())
 # v5 contains all three prior preview labels; use its validation and unsupported clips once.
 rows=[r for r in prev if r['split']=='val' and r['kind']=='supported']+[r for r in v5+dev if r['split']=='val'];rows+=nuisance(rows,24,902);encode(rows)
 train=[r for r in dev if r['split']=='train' and r['sequence']];assert all(sum(r['label']==l for r in train)>=3 for l in NEW)
 splits={s:{r['participant'] for r in dev+prev+v5 if r['split']==s} for s in ['train','val']};assert not splits['train']&splits['val']
 refs=old['samples']+extra['samples']+[dict(label=r['label'],sequence=r['sequence']) for r in train]
 mat=fit.matrix(rows,refs,'validation');base=old_predictions(mat,old,extra);best=None
 for limit,ratio,votes in itertools.product([.3,.4,.5,.65,.8,1,1.2],[1,1.1,1.3],[1,2]):
  params=dict(maxDistance=limit,minRatio=ratio,minVotes=votes,mirror=True,strongRatio=1.5)
  raw=fit.outputs(mat,refs,params);out=[p if p in NEW else b for b,p in zip(base,raw)];m=metrics(rows,out);per={l:sum(r['label']==l and a==l for r,a in zip(rows,out)) for l in NEW}
  score=(-sum(v>0 for v in per.values()),4*m['existing']['wrong']+m['new']['wrong']+2*m['negative']['wrong']-2*m['new']['correct'])
  if best is None or score<best[0]:best=(score,params,m,per)
 model={**extra,'labels':extra['labels']+NEW,'samples':refs[len(old['samples']):],'parameters':best[1],'baselineExtra':extra,'newLabels':NEW,'status':'optional-preview-only'}
 (ROOT/'candidate.json').write_text(json.dumps(model,separators=(',',':')))
 (ROOT/'frozen.json').write_text(json.dumps({'sha256':hashlib.sha256((ROOT/'candidate.json').read_bytes()).hexdigest(),'parameters':best[1]}))
 report=dict(protocol='Validation only; signer partitions disjoint. In opt-in preview, a joint-model match to a new label takes priority; otherwise use the previous nine-word preview. Select validation coverage, then error penalty.',baseline=metrics(rows,base),expanded=best[2],perWord=best[3],parameters=best[1],training={l:sum(r['label']==l for r in train) for l in NEW})
 (ROOT/'validation-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
