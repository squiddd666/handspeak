import sys,json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0,'/opt/handspeak/repository/training')
from train_words import extract
ROOT=Path('/opt/handspeak-training/vocabulary-v6')
if __name__=='__main__':
 rows=json.loads((ROOT/'development-manifest.json').read_text());out=[]
 # Reuse existing v3 encodings without touching the frozen v4 experiment.
 cached=json.loads(Path('/opt/handspeak-training/accuracy-v4/development-features.json').read_text());lookup={r['sha256']:r for r in cached};pending=[]
 for r in rows:
  if r['sha256'] in lookup:out.append({**lookup[r['sha256']],**r})
  else:pending.append(r)
 with ProcessPoolExecutor(max_workers=3) as pool:
  for r in pool.map(extract,pending):
   out.append(r)
   if len(out)%10==0:print('Extracted',len(out),'/',len(rows),flush=True)
 (ROOT/'development-features.json').write_text(json.dumps(out,separators=(',',':')));print('Complete',len(out),flush=True)
