import sys,json,hashlib,concurrent.futures
from pathlib import Path
sys.path[:0]=['/opt/handspeak-training/vocabulary-v6','/opt/handspeak/repository/training/vocabulary','/opt/handspeak/repository/training','/opt/handspeak/repository/training/accuracy']
from fit import ROOT,SITE,NEW,old_predictions,metrics
import fit_expansion as fit
from train_words import extract
# Avoid importing prepare: that filename is also the download executable.
import importlib.util
spec=importlib.util.spec_from_file_location('range_download','/opt/handspeak/repository/training/accuracy/prepare.py');down=importlib.util.module_from_spec(spec);spec.loader.exec_module(down)
from temporal import nuisance
from dtw import encode

def download(r):
 p=Path(r['file']);p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists():p.write_bytes(down.request(r['source'],r['offset'],r['size']))
 return {**r,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
if __name__=='__main__':
 frozen=json.loads((ROOT/'frozen.json').read_text());assert hashlib.sha256((ROOT/'candidate.json').read_bytes()).hexdigest()==frozen['sha256']
 rows=[r for r in json.loads((ROOT/'selection.json').read_text()) if r['split']=='test']
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p:rows=list(p.map(download,rows))
 with concurrent.futures.ProcessPoolExecutor(max_workers=3) as p:rows=list(p.map(extract,rows))
 (ROOT/'test-features.json').write_text(json.dumps(rows,separators=(',',':')))
 dev=json.loads((ROOT/'development-features.json').read_text());assert not({r['participant'] for r in rows}&{r['participant'] for r in dev});assert not({r['sha256'] for r in rows}&{r['sha256'] for r in dev})
 rows += [r for r in json.loads(Path('/opt/handspeak-training/accuracy-v4/test-features.json').read_text()) if r['kind']=='supported']+json.loads(Path('/opt/handspeak-training/vocabulary-v5/test-features.json').read_text())
 rows+=nuisance(rows,24,903);encode(rows)
 old=json.loads((SITE/'models/asl-words.json').read_text());extra=json.loads((ROOT/'previous-extra.json').read_text());model=json.loads((ROOT/'candidate.json').read_text());refs=old['samples']+model['samples'];fit.ROOT=ROOT
 mat=fit.matrix(rows,refs,'test');base=old_predictions(mat,old,extra);raw=fit.outputs(mat,refs,model['parameters']);out=[p if p in NEW else b for b,p in zip(base,raw)]
 report=dict(candidateSha256=frozen['sha256'],protocol='New-word test videos opened only after parameter freeze. Existing and negative sets are previously evaluated regression clips; these are whole-clip results, not real webcam sentence accuracy.',baseline=metrics(rows,base),expanded=metrics(rows,out),perWord={l:dict(total=sum(r['label']==l for r in rows),correct=sum(r['label']==l and p==l for r,p in zip(rows,out))) for l in NEW},predictions=[dict(label=r['label'],baseline=b,expanded=p,kind=r['kind']) for r,b,p in zip(rows,base,out)])
 report['defaultPromotion']=False;report['reason']='Optional isolated-word preview; no real-time sentence validation or default accuracy claim.'
 (ROOT/'test-report.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='predictions'},indent=2),flush=True)
