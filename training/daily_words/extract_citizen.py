"""Private landmark extraction using existing body-relative research pipeline."""
import sys,json,argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'accuracy'))
import extract as engine
ROOT=Path('/opt/handspeak-training/daily-words/citizen-research')
engine.ROOT=ROOT
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--test',action='store_true');args=p.parse_args()
 split='test' if args.test else 'development';rows=json.loads((ROOT/(split+'-manifest.json')).read_text())
 result=[]
 with ProcessPoolExecutor(max_workers=2) as pool:
  for row in pool.map(engine.extract,rows):
   result.append(row)
   if len(result)%10==0:print('Extracted',len(result),'/',len(rows),flush=True)
 (ROOT/(split+'-features.json')).write_text(json.dumps(result,separators=(',',':')))
 print('Complete',len(result),'usable motion sequences',sum(r['sequence'] is not None for r in result),flush=True)
