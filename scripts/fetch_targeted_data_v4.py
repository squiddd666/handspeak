"""Download only selected official ZIP members, checking range and CRC."""
import argparse,hashlib,io,json,time,urllib.request,zipfile,struct,zlib
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
URL="https://download.microsoft.com/download/b/8/8/b88c0bae-e6c1-43e1-8726-98cf5af36ca4/ASL_Citizen.zip"


class RangeReader(io.RawIOBase):
    def __init__(self):
        with urllib.request.urlopen(urllib.request.Request(URL,method="HEAD"),timeout=60) as r:self.size=int(r.headers["Content-Length"])
        self.pos=0
    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.pos
    def seek(self,n,whence=0):
        self.pos=n if whence==0 else self.pos+n if whence==1 else self.size+n
        return self.pos
    def read(self,n=-1):
        n=min(n,self.size-self.pos) if n>=0 else self.size-self.pos
        if not n:return b""
        if n>30_000_000:raise ValueError("Unexpectedly large byte range")
        for attempt in range(4):
            try:
                request=urllib.request.Request(URL,headers={"Range":f"bytes={self.pos}-{self.pos+n-1}"})
                with urllib.request.urlopen(request,timeout=120) as r:
                    if r.status!=206:raise ValueError("Byte range not honored")
                    data=r.read(n+1)
                if len(data)!=n:raise ValueError("Incomplete byte range")
                self.pos+=n;return data
            except Exception:
                if attempt==3:raise
                time.sleep(2**attempt)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("manifest",type=Path)
    args=parser.parse_args();rows=json.loads(args.manifest.read_text(encoding="utf-8"))
    missing=[r for r in rows if not Path(r["path"]).exists()]
    print("Existing",len(rows)-len(missing),"to fetch",len(missing),flush=True)
    if missing:
        with zipfile.ZipFile(RangeReader()) as archive:
            info={r['member']:archive.getinfo(r['member']) for r in missing}
        def fetch(r):
            member=info[r['member']]
            length=member.compress_size+4096
            if length>30_000_000:raise ValueError('Unexpectedly large ZIP member')
            for attempt in range(4):
                try:
                    req=urllib.request.Request(URL,headers={'Range':f'bytes={member.header_offset}-{member.header_offset+length-1}'})
                    with urllib.request.urlopen(req,timeout=120) as response:
                        if response.status!=206:raise ValueError('Byte range not honored')
                        block=response.read(length+1)
                    header=struct.unpack('<IHHHHHIIIHH',block[:30])
                    if header[0]!=0x04034b50 or header[3]!=member.compress_type:raise ValueError('Invalid ZIP local header')
                    start=30+header[-2]+header[-1]
                    compressed=block[start:start+member.compress_size]
                    if len(compressed)!=member.compress_size:raise ValueError('Incomplete ZIP member')
                    data=zlib.decompress(compressed,-15) if member.compress_type==8 else compressed if member.compress_type==0 else None
                    if data is None or len(data)!=member.file_size or zlib.crc32(data)!=member.CRC:raise ValueError('ZIP length/CRC mismatch')
                    break
                except Exception:
                    if attempt==3:raise
                    time.sleep(2**attempt)
            # Persist the verified file only once, outside the retry loop.
            path=Path(r['path']);path.parent.mkdir(parents=True,exist_ok=True)
            temporary=path.with_suffix('.download');temporary.write_bytes(data);temporary.replace(path)
            return r['file']
        with ThreadPoolExecutor(max_workers=6) as pool:
            for i,future in enumerate(as_completed([pool.submit(fetch,r) for r in missing]),1):
                future.result()
                if i%20==0 or i==len(missing):print("Fetched",i,"/",len(missing),flush=True)
    evidence=[{"file":r["file"],"split":r["split"],"bytes":Path(r["path"]).stat().st_size,
               "sha256":hashlib.sha256(Path(r["path"]).read_bytes()).hexdigest()} for r in rows]
    args.manifest.with_suffix(".downloads.json").write_text(json.dumps(evidence,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":main()
