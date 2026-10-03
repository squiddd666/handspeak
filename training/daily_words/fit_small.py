import sys,json,itertools,hashlib
from pathlib import Path
sys.path[:0]=['/opt/handspeak/repository/training/catalog','/opt/handspeak/repository/training']
import fit
ROOT=Path('/opt/handspeak-training/vocabulary-v10');ROOT.mkdir(exist_ok=True);fit.ROOT=ROOT
labels=['HOME','HAVE']
dev=json.loads(Path('/opt/handspeak-training/vocabulary-v7/corrected-development-features.json').read_text())
old=json.loads(Path('/opt/handspeak-training/accuracy-v4/development-features.json').read_text())
# Deduplicate sources, retaining corrected extraction where present.
lookup={r['sha256']:r for r in old+dev};data=list(lookup.values())
train=[r for r in data if r['split']=='train' and r.get('sequence') and r['label'] in labels]
negative=fit.balanced([r for r in data if r['split']=='train' and r.get('sequence') and r['label'] not in labels],120)
refs=[dict(label=r['label'],sequence=r['sequence']) for r in train]+[dict(label=fit.OTHER,sequence=r['sequence']) for r in negative]
rows=[r for r in data if r['split']=='val']
assert not({r['participant'] for r in train+negative}&{r['participant'] for r in rows})
protocol={'labels':labels,'trainingPositive':len(train),'trainingNegative':len(negative),'validationClips':len(rows),'gate':'At least half of supported validation clips correct, at least one correct for each word, zero wrong supported labels, zero unsupported false accepts. Freeze before regression evaluation. Require same absolute gate on reserved regression clips plus real-time capture checks before any deployment. Reused data does not establish independent accuracy.','scope':'Separate opt-in preview; existing 13-word recognizers unchanged.'}
(ROOT/'protocol.json').write_text(json.dumps(protocol,indent=2));print(json.dumps(protocol),flush=True)
mat=fit.matrix(rows,refs,'small-validation');best=None
for limit,ratio,votes in itertools.product([.15,.2,.25,.3,.35,.4,.5,.65,.8,1.0],[1.1,1.3,1.5,2,2.5],[1,2,3]):
 p=dict(maxDistance=limit,minRatio=ratio,minVotes=votes,mirror=True,strongRatio=2)
 out=fit.outputs(mat,refs,p,labels);m=fit.metrics(rows,out,labels)
 score=(m['wrong']+m['negativeFalse'], -m['correct'],limit)
 if best is None or score<best[0]:best=(score,p,m,out)
m=best[2];per={l:dict(total=sum(r['label']==l for r in rows),correct=sum(r['label']==l and o==l for r,o in zip(rows,best[3]))) for l in labels}
passed=m['correct']>=m['total']/2 and m['wrong']==0 and m['negativeFalse']==0 and all(v['correct'] for v in per.values())
model=dict(version=1,encoding='two-hand-motion-v3',status='research-only',labels=labels,samples=refs,parameters=best[1],attribution='PopSign ASL v1.0, Georgia Tech and DPAN, CC BY 4.0. Hand-landmark sequences.')
path=ROOT/'home-have.json';path.write_text(json.dumps(model,separators=(',',':')))
report=dict(protocol=protocol,parameters=best[1],validation=m,perWord=per,passesValidation=passed,modelSha256=hashlib.sha256(path.read_bytes()).hexdigest())
(ROOT/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
