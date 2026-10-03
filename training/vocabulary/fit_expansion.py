import sys,json,itertools,hashlib
from pathlib import Path
import numpy as np
from concurrent.futures import ProcessPoolExecutor
sys.path[:0]=['/opt/handspeak/repository/training','/opt/handspeak/repository/training/accuracy']
from fit_words import distance,mirror,predict
from temporal import nuisance
from dtw import encode
ROOT=Path('/opt/handspeak-training/vocabulary-v5');NEW=['DRINK','WATER','BOOK'];SITE=Path('/opt/handspeak/repository')
def init(refs):
 global REFS
 REFS=[np.array(r['sequence']) for r in refs]
def one(row):
 if row['sequence'] is None:return [float('inf')]*len(REFS)
 a=np.array(row['sequence']);m=mirror(a);return [min(distance(a,b),distance(m,b)) for b in REFS]
def matrix(rows,refs,name):
 path=ROOT/(name+'.npy')
 if path.exists():return np.load(path)
 with ProcessPoolExecutor(max_workers=3,initializer=init,initargs=(refs,)) as pool:m=np.array(list(pool.map(one,rows)))
 np.save(path,m);return m
def outputs(mat,refs,p):
 with np.errstate(invalid='ignore'):return predict(mat,refs,p)
def stats(rows,pred):
 return {group:{'total':len(ix),'correct':sum(pred[i]==rows[i]['label'] for i in ix),'wrong':sum(pred[i] is not None and pred[i]!=rows[i]['label'] for i in ix)} for group,ix in [('existing',[i for i,r in enumerate(rows) if r['label'] not in NEW and r['kind']=='supported']),('new',[i for i,r in enumerate(rows) if r['label'] in NEW]),('negative',[i for i,r in enumerate(rows) if r['kind']!='supported'])]}
if __name__=='__main__':
 old=json.loads((SITE/'models/asl-words.json').read_text());dev=json.loads((ROOT/'development-features.json').read_text());prev=json.loads(Path('/opt/handspeak-training/accuracy-v4/development-features.json').read_text());refs=old['samples']+[dict(label=r['label'],sequence=r['sequence']) for r in dev if r['split']=='train' and r['sequence']]
 rows=[r for r in prev if r['split']=='val' and r['kind']=='supported']+[r for r in dev if r['split']=='val'];rows+=nuisance(rows,24,789);encode(rows)
 signers={s:{r['participant'] for r in dev+prev if r['split']==s} for s in ['train','val']};assert not signers['train']&signers['val']
 mat=matrix(rows,refs,'validation');base=outputs(mat[:,:len(old['samples'])],old['samples'],old['parameters']);baseline=stats(rows,base);best=None
 for limit,ratio,votes,strong in itertools.product([.2,.3,.4,.5,.65,.8,1,1.2],[1,1.1,1.3,1.5],[1,2],[1.5,2,3,5]):
  p=dict(maxDistance=limit,minRatio=ratio,minVotes=votes,mirror=True,strongRatio=strong);raw=outputs(mat,refs,p);out=[b or (n if n in NEW else None) for b,n in zip(base,raw)];m=stats(rows,out)
  feasible=m['existing']['wrong']<=baseline['existing']['wrong'] and m['negative']['wrong']<=baseline['negative']['wrong']
  score=(not feasible,4*m['new']['wrong']-m['new']['correct'],sum(v['wrong'] for v in m.values()))
  if best is None or score<best[0]:best=(score,p,m,out)
 candidate={**old,'labels':old['labels']+NEW,'samples':refs,'parameters':best[1],'baselineFirst':{'samples':old['samples'],'parameters':old['parameters']},'extraLabels':NEW}
 (ROOT/'expanded-candidate.json').write_text(json.dumps(candidate,separators=(',',':')))
 report={'method':'Existing model first; expanded model only suggests a new label when existing model rejects. Validation chooses expansion parameters.','parameters':best[1],'baseline':baseline,'expanded':best[2],'perWord':{l:{'total':sum(r['label']==l for r in rows),'correct':sum(r['label']==l and p==l for r,p in zip(rows,best[3]))} for l in NEW},'training':{l:sum(r['label']==l for r in refs) for l in NEW},'signerOverlap':False,'candidateSha256':hashlib.sha256((ROOT/'expanded-candidate.json').read_bytes()).hexdigest()}
 (ROOT/'validation-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
