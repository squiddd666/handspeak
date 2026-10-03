"""Targeted v1 subset, fixed signer-separated selection, checkpointed downloads."""
import sys,json,re,tarfile,hashlib,concurrent.futures
from pathlib import Path
sys.path.insert(0,'/opt/handspeak/repository/training/accuracy')
from prepare import request
ROOT=Path('/opt/handspeak-training/vocabulary-v7');SITE=Path('/opt/handspeak/repository')
cache=[]
for p in [Path('/opt/handspeak-training/accuracy-v4/development-features.json'),Path('/opt/handspeak-training/accuracy-v4/test-features.json'),Path('/opt/handspeak-training/vocabulary-v5/development-features.json'),Path('/opt/handspeak-training/vocabulary-v5/test-features.json'),Path('/opt/handspeak-training/vocabulary-v6/development-features.json'),Path('/opt/handspeak-training/vocabulary-v6/test-features.json')]:cache+=json.loads(p.read_text())
lookup={(r['source'],r['member']):r for r in cache if 'source' in r};cat=json.loads((SITE/'models/motion-vocabulary.json').read_text());items=[i for i in cat['items'] if i['sourceVersion']=='v1_0'];labels={i['sourceLabel']:i['label'] for i in items}
def select(args):
 label,split,count=args;out=ROOT/f'{split}-{label}.json'
 if out.exists():return json.loads(out.read_text())
 url=f'https://signdata.cc.gatech.edu/data/popsign_v1_0/game/{split}/{label}.tar';offset=0;rows=[];signers={}
 for _ in range(2000):
  if len(rows)>=count:break
  header=request(url,offset,512)
  if header==bytes(512):break
  info=tarfile.TarInfo.frombuf(header,'utf-8','replace');start=offset+512;offset=start+((info.size+511)//512)*512
  if not info.isfile() or not info.name.endswith('.mp4'):continue
  match=re.search(r'4a\.(\d+)',info.name)
  if not match:continue
  who=match.group(1)
  if signers.get(who,0)>=2:continue
  old=lookup.get((url,info.name))
  # Fresh test clips even for words studied before this experiment.
  if split=='test' and old:continue
  signers[who]=signers.get(who,0)+1
  rows.append({'label':labels[label],'sourceLabel':label,'split':split,'participant':who,'source':url,'member':info.name,'offset':start,'size':info.size,'file':old['file'] if old else str(ROOT/'videos'/split/label/Path(info.name).name),'kind':'supported'})
 out.write_text(json.dumps(rows,indent=2));print('Selected',label,split,len(rows),flush=True);return rows
def download(row):
 p=Path(row['file']);p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists():
  data=request(row['source'],row['offset'],row['size']);temp=p.with_suffix('.partial');temp.write_bytes(data);temp.replace(p)
 return {**row,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
if __name__=='__main__':
 jobs=[(l,s,n) for l in labels for s,n in [('train',12),('val',4),('test',4)]]
 with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:rows=[r for batch in pool.map(select,jobs) for r in batch]
 partitions={s:{r['participant'] for r in rows if r['split']==s} for s in ['train','val','test']};assert not(partitions['train']&partitions['val'] or partitions['train']&partitions['test'] or partitions['val']&partitions['test'])
 (ROOT/'selection.json').write_text(json.dumps(rows,indent=2))
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  dev=[]
  for row in pool.map(download,[r for r in rows if r['split']!='test']):
   dev.append(row)
   if len(dev)%25==0:print('Downloaded',len(dev),flush=True)
 (ROOT/'development-manifest.json').write_text(json.dumps(dev,indent=2));print('Development ready',len(dev),flush=True)
