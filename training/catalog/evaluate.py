"""One reserved test run after all category models are frozen."""
import sys,json,hashlib,concurrent.futures,importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fit import ROOT,SITE,matrix,outputs,metrics,balanced
spec=importlib.util.spec_from_file_location('source_requests','/opt/handspeak/repository/training/accuracy/prepare.py');d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
sys.path.insert(0,str(Path(__file__).resolve().parent))
from extract import job

def download(r):
 p=Path(r['file']);p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists():p.write_bytes(d.request(r['source'],r['offset'],r['size']))
 return {**r,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
if __name__=='__main__':
 index=json.loads((ROOT/'frozen-index.json').read_text());selected=[r for r in json.loads((ROOT/'selection.json').read_text()) if r['split']=='test']
 if (ROOT/'test-features.json').exists():rows=json.loads((ROOT/'test-features.json').read_text())
 else:
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(download,selected))
  (ROOT/'test-manifest.json').write_text(json.dumps(rows,indent=2));result=[]
  with concurrent.futures.ProcessPoolExecutor(max_workers=3) as pool:
   for r in pool.map(job,rows):
    result.append(r)
    if len(result)%20==0:print('Test extracted',len(result),'/',len(rows),flush=True)
  rows=result;(ROOT/'test-features.json').write_text(json.dumps(rows,separators=(',',':')))
 dev=json.loads((ROOT/'development-features.json').read_text());assert not({r['participant'] for r in rows}&{r['participant'] for r in dev});assert not({r['sha256'] for r in rows}&{r['sha256'] for r in dev})
 regression=json.loads(Path('/opt/handspeak-training/accuracy-v4/test-features.json').read_text());reports={}
 for group in index['groups']:
  p=ROOT/'models'/Path(group['file']).name;assert hashlib.sha256(p.read_bytes()).hexdigest()==group['sha256'];model=json.loads(p.read_text());labels=model['labels'];test=list(rows)+balanced([r for r in regression if r['label'] not in labels],18)
  mat=matrix(test,model['samples'],group['id']+'-test');out=outputs(mat,model['samples'],model['parameters'],labels);m=metrics(test,out,labels)
  report={'test':m,'perWord':{l:{'total':sum(r['label']==l for r in test),'correct':sum(r['label']==l and o==l for r,o in zip(test,out))} for l in labels},'modelSha256':group['sha256'],'predictions':[{'expected':r['label'],'suggested':o,'sha256':r['sha256']} for r,o in zip(test,out)]};reports[group['id']]=report;group['test']=m
  print('Test',group['id'],json.dumps(m),flush=True)
 (ROOT/'test-report.json').write_text(json.dumps({'protocol':'Thresholds frozen from validation. New requested-word test clips were excluded from earlier experiments. Negative test clips include new requested signs outside the selected category and a balanced subset of an existing regression set. Ordinary non-sign hand movements are not covered. Whole-clip test only; not real-camera accuracy or emergency validation.','groups':reports},indent=2));(ROOT/'evaluated-index.json').write_text(json.dumps(index,indent=2))
