import sys,json,tarfile,re,hashlib,concurrent.futures
from pathlib import Path
sys.path.insert(0,'/opt/handspeak/repository/training/accuracy')
from prepare import request
ROOT=Path('/opt/handspeak-training/vocabulary-v6');OLD=Path('/opt/handspeak-training/accuracy-v4')
existing=json.loads((OLD/'development-features.json').read_text())+json.loads((OLD/'test-features.json').read_text())
lookup={(r['source'],r['member']):r for r in existing}
def job(args):
 label,split,count=args;out=ROOT/f'{split}-{label}-manifest.json'
 if out.exists():return json.loads(out.read_text())
 url=f'https://signdata.cc.gatech.edu/data/popsign_v1_0/game/{split}/{label}.tar';offset=0;rows=[];signers={}
 while len(rows)<count:
  header=request(url,offset,512)
  if header==bytes(512):break
  info=tarfile.TarInfo.frombuf(header,'utf-8','replace');start=offset+512;offset=start+((info.size+511)//512)*512
  if not info.isfile() or not info.name.endswith('.mp4'):continue
  match=re.search(r'4a\.(\d+)',info.name)
  if not match:continue
  who=match.group(1)
  if signers.get(who,0)>=3:continue
  previous=lookup.get((url,info.name))
  if split=='test' and previous:continue
  signers[who]=signers.get(who,0)+1
  row=dict(label=label.upper(),split=split,participant=who,source=url,member=info.name,offset=start,size=info.size,kind='supported' if label in ['food','hungry','like','go'] else 'unsupported')
  if previous:row['file']=previous['file']
  else:row['file']=str(ROOT/'videos'/split/label/Path(info.name).name)
  rows.append(row)
 out.write_text(json.dumps(rows,indent=2));print('Selected',label,split,len(rows),flush=True);return rows
def download(row):
 path=Path(row['file']);path.parent.mkdir(parents=True,exist_ok=True)
 if not path.exists():path.write_bytes(request(row['source'],row['offset'],row['size']))
 row['sha256']=hashlib.sha256(path.read_bytes()).hexdigest();return row
jobs=[(l,s,n) for l in ['food','hungry','like','go'] for s,n in [('train',24),('val',8),('test',6)]]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=[r for batch in pool.map(job,jobs) for r in batch]
# Select test metadata now but don't open its payload until candidates are frozen.
(ROOT/'selection.json').write_text(json.dumps(rows,indent=2))
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:dev=list(pool.map(download,[r for r in rows if r['split']!='test']))
(ROOT/'development-manifest.json').write_text(json.dumps(dev,indent=2));print('Downloaded development',len(dev),flush=True)
