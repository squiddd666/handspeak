"""Private noncommercial research subset. Never copy videos/templates to served files."""
import csv,json,hashlib,zipfile,struct,zlib,concurrent.futures,argparse
from pathlib import Path
from remote_zip import RangeReader,ROOT,URL
OUT=ROOT/'citizen-research';OUT.mkdir(exist_ok=True)
TARGET={'NAME':'NAME','HOME':'HOME','HAVE':'HAVE','WANT1':'WANT','WANT2':'WANT','LOVE':'LOVE'}
def selection():
 tables={s:list(csv.DictReader((ROOT/'metadata/ASL_Citizen/splits'/f'{s}.csv').open())) for s in ['train','val','test']}
 signers={s:{r['Participant ID'] for r in rows} for s,rows in tables.items()}
 assert all(not(signers[a]&signers[b]) for a,b in [('train','val'),('train','test'),('val','test')])
 available=set.intersection(*[{r['Gloss'] for r in rows} for rows in tables.values()])
 # Predeclare negatives from all splits' labels only, without reading test video content.
 preferred=['HELLO','THANKYOU','PLEASE','YES','NO','FINISH','DRINK','WATER','BOOK','FOOD','HUNGRY','LIKE','GO','NEED','KNOW','THINK','HOUSE','FAMILY','FRIEND']
 negatives=[l for l in preferred if l in available and l not in TARGET]
 for l in sorted(available-set(TARGET)-set(negatives),key=lambda x:hashlib.sha256(x.encode()).hexdigest()):
  if len(negatives)>=24:break
  negatives.append(l)
 names=json.loads((ROOT/'archive-index.json').read_text());members={Path(n).name:n for n in names if n.endswith('.mp4')}
 selected=[]
 for split,rows in tables.items():
  seen={}
  for row in sorted(rows,key=lambda r:(r['Participant ID'],r['Video file'])):
   gloss=row['Gloss'];who=row['Participant ID'];k=(gloss,who)
   if gloss not in TARGET and gloss not in negatives:continue
   # Positive variants retain their official labels in provenance, map only to requested word.
   if seen.get(k,0):continue
   limit=100 if gloss in TARGET else (4 if split=='train' else 2)
   if sum(r['sourceLabel']==gloss and r['split']==split for r in selected)>=limit:continue
   name=row['Video file'];selected.append(dict(label=TARGET.get(gloss,gloss),sourceLabel=gloss,split=split,participant=who,source=URL,member=members[name],file=str(OUT/'videos'/split/name),kind='supported' if gloss in TARGET else 'unsupported'))
   seen[k]=1
 protocol={'dataset':'ASL Citizen','use':'Private noncommercial research; no redistribution of recordings or derived templates.','requestedWords':list(dict.fromkeys(TARGET.values())),'sourceMapping':TARGET,'negativeLabels':negatives,'split':'Official signer-independent partitions, at most one clip per gloss per signer; sorted deterministic selection.','promotionGate':'At least 50% correct supported clips, at least one correct per word, zero wrong supported labels and zero negative false accepts on validation; freeze before reserved test. Test must also meet that gate. No deployment without separate real-time timing and licensing review.','limitations':'Small research subset; WANT variants pooled by source gloss family; no ordinary non-sign motion or physical-webcam test.'}
 path=OUT/'selection.json';content=json.dumps(selected,indent=2)
 if path.exists():assert path.read_text()==content,'Frozen selection changed'
 else:path.write_text(content)
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2));return selected
INFO={}
def download(row):
 path=Path(row['file']);info=INFO[row['member']]
 if not path.exists():
  rr=RangeReader();rr.seek(info.header_offset);header=rr.read(30);assert header[:4]==b'PK\x03\x04'
  fn,extra=struct.unpack_from('<HH',header,26);rr.seek(info.header_offset+30+fn+extra);data=rr.read(info.compress_size)
  data=zlib.decompress(data,-15) if info.compress_type==8 else data
  assert len(data)==info.file_size and zlib.crc32(data)&0xffffffff==info.CRC
  path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.partial');temp.write_bytes(data);temp.replace(path)
 return {**row,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--test',action='store_true');args=p.parse_args();rows=selection();chosen=[r for r in rows if (r['split']=='test')==args.test]
 if args.test:
  frozen=json.loads((OUT/'temporal-validation.json').read_text())['selected']
  assert frozen['passesValidation'],'Candidate must pass validation before test download'
  assert hashlib.sha256((OUT/'temporal-private.pt').read_bytes()).hexdigest()==frozen['sha256'],'Frozen model changed'
 print('Selected',len(chosen),'test' if args.test else 'development','clips',flush=True)
 with zipfile.ZipFile(RangeReader()) as archive:INFO={r['member']:archive.getinfo(r['member']) for r in chosen}
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  ready=[]
  for r in pool.map(download,chosen):
   ready.append(r)
   if len(ready)%20==0:print('Downloaded',len(ready),'/',len(chosen),flush=True)
 (OUT/('test-manifest.json' if args.test else 'development-manifest.json')).write_text(json.dumps(ready,indent=2))
 print('Download complete',len(ready),flush=True)
