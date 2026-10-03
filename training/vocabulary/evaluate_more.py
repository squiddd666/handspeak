import sys,json,hashlib,concurrent.futures
from pathlib import Path
import numpy as np,quickjs
sys.path[:0]=['/opt/handspeak-training/vocabulary-v5','/opt/handspeak/repository/training','/opt/handspeak/repository/training/accuracy']
from prepare import request
from train_words import extract
from fit_expansion import matrix,outputs,stats,ROOT,NEW,SITE
from temporal import nuisance
from dtw import encode

def download(r):
 p=Path(r['file']);p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists():p.write_bytes(request(r['source'],r['offset'],r['size']))
 return {**r,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
if __name__=='__main__':
 report=json.loads((ROOT/'validation-report.json').read_text());assert hashlib.sha256((ROOT/'expanded-candidate.json').read_bytes()).hexdigest()==report['candidateSha256']
 candidate=json.loads((ROOT/'expanded-candidate.json').read_text());rows=[r for r in json.loads((ROOT/'selection.json').read_text()) if r['split']=='test']
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(download,rows))
 (ROOT/'test-manifest.json').write_text(json.dumps(rows,indent=2))
 with concurrent.futures.ProcessPoolExecutor(max_workers=3) as pool:rows=list(pool.map(extract,rows))
 (ROOT/'test-features.json').write_text(json.dumps(rows,separators=(',',':')))
 dev=json.loads((ROOT/'development-features.json').read_text());previous=json.loads(Path('/opt/handspeak-training/accuracy-v4/development-features.json').read_text());oldtest=[r for r in json.loads(Path('/opt/handspeak-training/accuracy-v4/test-features.json').read_text()) if r['kind']=='supported'];rows+=oldtest
 assert not({r['participant'] for r in rows}&{r['participant'] for r in dev+previous})
 assert not({r['sha256'] for r in rows}&{r['sha256'] for r in dev+previous})
 rows+=nuisance(rows,24,1117);encode(rows)
 js=quickjs.Context()
 for name in ['motion-model.js','automatic-motion.js']:js.eval((SITE/name).read_text().replace('export ',''))
 js.eval('''function segment(row){const auto=createAutomaticMotion(),out=[];row.rawFrames.concat(Array.from({length:20},()=>[null,null])).forEach((f,i)=>{const c=auto.push(f,i*100,row.imageAspect);if(c)out.push(encodeMotion(c.frames,c.imageAspect));});return JSON.stringify(out);}''')
 clips=[]
 for i,row in enumerate(rows):
  for sequence in json.loads(js.eval('segment('+json.dumps(row)+')')):clips.append({**row,'sequence':sequence,'parent':i})
 mat=matrix(rows+clips,candidate['samples'],'test');old=candidate['baselineFirst'];base=outputs(mat[:,:len(old['samples'])],old['samples'],old['parameters']);raw=outputs(mat,candidate['samples'],candidate['parameters']);expanded=[b or (n if n in NEW else None) for b,n in zip(base,raw)]
 n=len(rows)
 def automatic(out):
  groups=[[] for r in rows]
  for c,p in zip(clips,out[n:]):
   if p:groups[c['parent']].append(p)
  return dict(correct=sum(r['label'] in ps for r,ps in zip(rows,groups) if r['kind']=='supported'),wrong=sum(sum(p!=r['label'] for p in ps) for r,ps in zip(rows,groups) if r['kind']=='supported'),unsupportedFalse=sum(len(ps) for r,ps in zip(rows,groups) if r['kind']!='supported'),repeats=sum(len(ps)-len(set(ps)) for ps in groups))
 bs=stats(rows,base[:n]);ex=stats(rows,expanded[:n]);ba=automatic(base);ea=automatic(expanded)
 gate=ex['existing']['correct']>=bs['existing']['correct'] and ex['existing']['wrong']<=bs['existing']['wrong'] and ex['negative']['wrong']<=bs['negative']['wrong'] and all(ea[k]<=ba[k] for k in ['wrong','unsupportedFalse','repeats'])
 result=dict(protocol='New-word/unsupported test recordings selected before fitting and opened after candidate freeze; existing-word clips are a previously evaluated regression set. Signer partitions disjoint. Automatic replay uses synthetic 100 ms timestamps, not real webcam timing.',baseline=bs,expanded=ex,automaticBaseline=ba,automaticExpanded=ea,regressionGate=gate,perWord={l:dict(total=sum(r['label']==l for r in rows),correct=sum(r['label']==l and p==l for r,p in zip(rows,expanded))) for l in NEW},candidateSha256=report['candidateSha256'],predictions=[dict(label=r['label'],kind=r['kind'],sha256=r['sha256'],baseline=b,expanded=e) for r,b,e in zip(rows,base,expanded)])
 (ROOT/'test-report.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='predictions'},indent=2),flush=True)
