"""Evaluate a frozen dense-data candidate against the same v7 regression recordings."""
import sys,json,hashlib,os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parent))
from recover_tracking import job
import fit
OLD=Path('/opt/handspeak-training/vocabulary-v7');ROOT=Path('/opt/handspeak-training/vocabulary-v8');fit.ROOT=ROOT
if __name__=='__main__':
 index=json.loads((ROOT/'frozen-index.json').read_text());original=json.loads((OLD/'test-features.json').read_text());legacy=json.loads(Path('/opt/handspeak-training/accuracy-v4/test-features.json').read_text());catalog=json.loads((fit.SITE/'models/motion-vocabulary.json').read_text());result=[]
 if (ROOT/'test-features.json').exists():dense=json.loads((ROOT/'test-features.json').read_text())
 else:
  with ProcessPoolExecutor(max_workers=3) as pool:
   for row in pool.map(job,[r for r in original if not r.get('sequence')]):
    result.append(row)
    if len(result)%20==0:print('Test tracking retry',len(result),flush=True)
  lookup={r['sha256']:r for r in result};dense=[lookup.get(r['sha256'],r) for r in original];(ROOT/'test-features.json').write_text(json.dumps(dense,separators=(',',':')))
 dev=json.loads((ROOT/'development-features.json').read_text());assert not ({r['participant'] for r in dev}&{r['participant'] for r in dense});assert not ({r['sha256'] for r in dev}&{r['sha256'] for r in dense});reports={}
 for group in index['groups']:
  path=ROOT/'models'/Path(group['file']).name;assert hashlib.sha256(path.read_bytes()).hexdigest()==group['sha256'];candidate=json.loads(path.read_text());baseline=json.loads((OLD/'models'/path.name).read_text());wanted=[i['label'] for i in catalog['items'] if group['id'] in i['categories'] and i['sourceVersion']=='v1_0'];negative=fit.balanced([r for r in legacy if r['label'] not in wanted],18)
  oldrows=original+negative;newrows=dense+negative
  before=fit.outputs(fit.matrix(oldrows,baseline['samples'],group['id']+'-baseline-regression'),baseline['samples'],baseline['parameters'],baseline['labels']);after=fit.outputs(fit.matrix(newrows,candidate['samples'],group['id']+'-dense-regression'),candidate['samples'],candidate['parameters'],candidate['labels'])
  bm=fit.metrics(oldrows,before,wanted);cm=fit.metrics(newrows,after,wanted)
  gate=cm['correct']>bm['correct'] and cm['wrong']<=bm['wrong'] and cm['negativeFalse']<=bm['negativeFalse']
  reports[group['id']]={'baseline':bm,'candidate':cm,'passesRegressionGate':gate,'modelSha256':group['sha256'],'perWord':{l:{'total':sum(r['label']==l for r in newrows),'correct':sum(r['label']==l and o==l for r,o in zip(newrows,after))} for l in candidate['labels']},'predictions':[{'expected':r['label'],'suggested':o,'sha256':r['sha256']} for r,o in zip(newrows,after)]};print(group['id'],bm,'->',cm,'gate',gate,flush=True)
 (ROOT/'regression.json').write_text(json.dumps({'protocol':'Same previously evaluated v7 test clips, with tracking failures retried at up to 60 sampled frames. This compares complete offline pipelines and is a regression test, not a new independent accuracy claim. Models and thresholds frozen before test retry. Physical webcam accuracy and ordinary non-sign movements are not evaluated.','recoveredTestSequences':sum(bool(r.get('sequence')) for r in dense)-sum(bool(r.get('sequence')) for r in original),'groups':reports},indent=2))
