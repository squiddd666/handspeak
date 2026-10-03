"""Overlap completed downloads with bounded extraction; resumable per-video caches."""
import sys,json,time,hashlib
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
sys.path.insert(0,str(Path(__file__).resolve().parent))
from extract import job,ROOT
if __name__=='__main__':
 rows=[r for r in json.loads((ROOT/'selection.json').read_text()) if r['split']!='test'];out=[];pending={};remaining=list(rows);idle=0
 with ProcessPoolExecutor(max_workers=3) as pool:
  while remaining or pending:
   submitted=False
   for row in remaining[:]:
    if len(pending)>=6:break
    p=Path(row['file'])
    if not p.exists() or p.stat().st_size!=row['size']:continue
    ready={**row,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()};pending[pool.submit(job,ready)]=ready;remaining.remove(row);submitted=True
   if pending:
    done,_=wait(pending,timeout=2,return_when=FIRST_COMPLETED)
    for future in done:
     pending.pop(future);out.append(future.result())
     if len(out)%20==0:print('Extracted development',len(out),'/',len(rows),flush=True)
    idle=0
   elif not submitted:
    idle+=1
    if idle>300:raise RuntimeError('Downloads stalled for more than ten minutes')
    time.sleep(2)
 # Reproducible order independent of worker completion.
 lookup={(r['source'],r['member']):r for r in out};out=[lookup[(r['source'],r['member'])] for r in rows]
 (ROOT/'development-features.json').write_text(json.dumps(out,separators=(',',':')));print('Complete development',len(out),flush=True)
