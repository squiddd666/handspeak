"""Fit category-specific previews on validation only; keep default vocabulary unchanged."""
import sys,json,itertools,hashlib,os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import numpy as np
sys.path[:0]=['/opt/handspeak/repository/training','/opt/handspeak/repository/training/accuracy']
from fit_words import distance,mirror,predict
ROOT=Path(os.environ.get('HANDSPEAK_EXPERIMENT_DIR','/opt/handspeak-training/vocabulary-v7'));SITE=Path('/opt/handspeak/repository');OTHER='OTHER MOVEMENT'
def balanced(rows,limit):
 groups={}
 for row in rows:groups.setdefault(row['label'],[]).append(row)
 result=[];offset=0
 while len(result)<limit:
  batch=[values[offset] for values in groups.values() if len(values)>offset]
  if not batch:break
  result.extend(batch[:limit-len(result)]);offset+=1
 return result
def init(refs):
 global REFS
 REFS=[np.array(r['sequence']) for r in refs]
def one(row):
 if row.get('sequence') is None:return [float('inf')]*len(REFS)
 a=np.array(row['sequence']);b=mirror(a);return [min(distance(a,r),distance(b,r)) for r in REFS]
def matrix(rows,refs,name):
 path=ROOT/(name+'.npy')
 signature=hashlib.sha256(json.dumps([(r.get('sha256'),r.get('sequence')) for r in rows]+refs,sort_keys=True).encode()).hexdigest();sp=path.with_suffix('.sha256')
 if path.exists() and sp.exists() and sp.read_text()==signature:return np.load(path)
 with ProcessPoolExecutor(max_workers=3,initializer=init,initargs=(refs,)) as pool:mat=np.array(list(pool.map(one,rows)))
 np.save(path,mat);sp.write_text(signature);return mat
def outputs(mat,refs,p,labels):
 with np.errstate(invalid='ignore'):out=predict(mat,refs,p)
 return [v if v in labels else None for v in out]
def metrics(rows,out,labels):
 positive=[i for i,r in enumerate(rows) if r['label'] in labels];negative=[i for i,r in enumerate(rows) if r['label'] not in labels]
 return dict(total=len(positive),correct=sum(out[i]==rows[i]['label'] for i in positive),wrong=sum(out[i] is not None and out[i]!=rows[i]['label'] for i in positive),missed=sum(out[i] is None for i in positive),negativeTotal=len(negative),negativeFalse=sum(out[i] is not None for i in negative))
if __name__=='__main__':
 dev=json.loads((ROOT/'development-features.json').read_text());catalog=json.loads((SITE/'models/motion-vocabulary.json').read_text());old=json.loads(Path('/opt/handspeak-training/accuracy-v4/development-features.json').read_text());outdir=ROOT/'models';outdir.mkdir(exist_ok=True);index=[];reports={}
 for group in catalog['categories']:
  wanted=[r['label'] for r in catalog['items'] if group['id'] in r['categories']];train=[r for r in dev if r['split']=='train' and r.get('sequence') and r['label'] in wanted];counts={l:sum(r['label']==l for r in train) for l in wanted};labels=[l for l in wanted if counts[l]>=3]
  if not labels:continue
  train=[r for r in train if r['label'] in labels]
  # Explicit diverse negative training examples; never train on validation/test clips.
  negatives=balanced([r for r in old if r['split']=='train' and r.get('sequence') and r['label'] not in labels],18)+balanced([r for r in dev if r['split']=='train' and r.get('sequence') and r['label'] not in wanted],18)
  refs=[dict(label=r['label'],sequence=r['sequence']) for r in train]+[dict(label=OTHER,sequence=r['sequence']) for r in negatives]
  rows=[r for r in dev if r['split']=='val' and r['label'] in wanted]+balanced([r for r in old if r['split']=='val' and r['label'] not in labels],18)+balanced([r for r in dev if r['split']=='val' and r['label'] not in wanted],18)
  mat=matrix(rows,refs,group['id']+'-validation');best=None
  for limit,ratio,votes in itertools.product([.2,.35,.5,.65,.8,1.0],[1.1,1.3,1.5],[1,2]):
   p=dict(maxDistance=limit,minRatio=ratio,minVotes=votes,mirror=True,strongRatio=2);pred=outputs(mat,refs,p,labels);m=metrics(rows,pred,labels);score=(4*m['wrong']+4*m['negativeFalse']+m['missed'],m['wrong']+m['negativeFalse'],-m['correct'])
   if best is None or score<best[0]:best=(score,p,m)
  model=dict(version=1,encoding='two-hand-motion-v3',status='category-preview',labels=labels,samples=refs,parameters=best[1],attribution='PopSign ASL v1.0, Georgia Tech and DPAN, CC BY 4.0. Converted to hand-landmark sequences.',category=group['id'])
  path=outdir/(group['id']+'.json');path.write_text(json.dumps(model,separators=(',',':')));sha=hashlib.sha256(path.read_bytes()).hexdigest()
  report=dict(validation=best[2],counts=counts,modelSha256=sha,parameters=best[1],trainingSources=[{k:r[k] for k in ['label','source','member','sha256','participant','split']} for r in train+negatives]);reports[group['id']]=report
  index.append(dict(id=group['id'],name=group['name'],labels=labels,file='models/motion-categories/'+path.name,sha256=sha,validation=best[2]))
  print(group['name'],json.dumps(best[2]),flush=True)
 (ROOT/'validation-report.json').write_text(json.dumps(reports,indent=2));(ROOT/'frozen-index.json').write_text(json.dumps({'version':1,'groups':index},indent=2));print('Frozen categories',len(index),flush=True)
