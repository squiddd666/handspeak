import json,itertools,sys
import numpy as np
from pathlib import Path
sys.path.insert(0,'/opt/handspeak-training/vocabulary-v5')
from fit_expansion import ROOT,NEW,outputs,stats
from temporal import nuisance
old=json.loads(Path('/opt/handspeak/repository/models/asl-words.json').read_text());cand=json.loads((ROOT/'expanded-candidate.json').read_text());dev=json.loads((ROOT/'development-features.json').read_text());prev=json.loads(Path('/opt/handspeak-training/accuracy-v4/development-features.json').read_text());rows=[r for r in prev if r['split']=='val' and r['kind']=='supported']+[r for r in dev if r['split']=='val'];rows+=nuisance(rows,24,789);mat=np.load(ROOT/'validation.npy');base=outputs(mat[:,:len(old['samples'])],old['samples'],old['parameters']);best=None;table=[]
for limit,ratio,votes in itertools.product([.3,.4,.5,.65,.8,1,1.2],[1,1.1,1.3],[1,2]):
 p=dict(maxDistance=limit,minRatio=ratio,minVotes=votes,mirror=True,strongRatio=1.5);raw=outputs(mat,cand['samples'],p);out=[b or (n if n in NEW else None) for b,n in zip(base,raw)];m=stats(rows,out);per={l:sum(r['label']==l and a==l for r,a in zip(rows,out)) for l in NEW}
 score=(min(per.values())==0,4*m['existing']['wrong']+m['new']['wrong']+2*m['negative']['wrong']-2*m['new']['correct'])
 table.append(dict(parameters=p,stats=m,perWord=per))
 if best is None or score<best[0]:best=(score,p,m,per,out)
report=dict(status='optional-preview-only',parameters=best[1],validation=best[2],perWord=best[3],selection='Prefer at least one validation hit per new word, then minimize 4*existing wrong + new wrong + 2*negative false - 2*new correct. Default promotion constraints failed; opt-in only.')
cand['parameters']=best[1];(ROOT/'preview-candidate.json').write_text(json.dumps(cand,separators=(',',':')));(ROOT/'preview-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
