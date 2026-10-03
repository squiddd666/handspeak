"""Read selected members of the official archive without downloading 43 GiB."""
import io,urllib.request,zipfile,json,time
from pathlib import Path
URL='https://download.microsoft.com/download/b/8/8/b88c0bae-e6c1-43e1-8726-98cf5af36ca4/ASL_Citizen.zip'
ROOT=Path('/opt/handspeak-training/daily-words');ROOT.mkdir(exist_ok=True)
class RangeReader(io.RawIOBase):
 def __init__(self):
  with urllib.request.urlopen(urllib.request.Request(URL,method='HEAD'),timeout=30) as r:self.size=int(r.headers['Content-Length'])
  self.pos=0
 def seekable(self):return True
 def readable(self):return True
 def tell(self):return self.pos
 def seek(self,n,whence=0):
  self.pos=n if whence==0 else self.pos+n if whence==1 else self.size+n
  return self.pos
 def read(self,n=-1):
  n=self.size-self.pos if n<0 else min(n,self.size-self.pos)
  if not n:return b''
  if n>30_000_000:raise ValueError('Refusing an unexpectedly large member/range')
  for attempt in range(3):
   try:
    req=urllib.request.Request(URL,headers={'Range':f'bytes={self.pos}-{self.pos+n-1}'})
    with urllib.request.urlopen(req,timeout=60) as r:
     if r.status!=206:raise ValueError('Server did not honor byte range')
     result=r.read(n+1)
    if len(result)!=n:raise ValueError('Incomplete byte range')
    self.pos+=n;return result
   except Exception:
    if attempt==2:raise
    time.sleep(1)
if __name__=='__main__':
 with zipfile.ZipFile(RangeReader()) as archive:
  names=archive.namelist();(ROOT/'archive-index.json').write_text(json.dumps(names))
  for n in names:
   if n in {'ASL_Citizen/use.txt','ASL_Citizen/splits/train.csv','ASL_Citizen/splits/val.csv','ASL_Citizen/splits/test.csv'}:
    print(n,archive.getinfo(n).file_size,flush=True)
    if archive.getinfo(n).file_size<20_000_000:
     target=ROOT/'metadata'/n;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(n))
