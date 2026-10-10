"""Acquire a fixed small ordinary-action benchmark; private evaluation only."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import ssl
import subprocess
import urllib.request

ROOT=Path('/opt/handspeak-training/ordinary-movement-ucf101')
BASE='https://www.crcv.ucf.edu/THUMOS14/UCF101/UCF101/'
ACTIONS=['Typing','BrushingTeeth','ApplyEyeMakeup','ShavingBeard']


def main():
    global ROOT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT)
    parser.add_argument('--groups',type=int,nargs='+',default=[1,2,3])
    parser.add_argument('--model-protocol',type=Path)
    args=parser.parse_args();ROOT=args.output.resolve()
    if len(set(args.groups))!=len(args.groups) or any(g<1 or g>25 for g in args.groups):
        raise ValueError('Invalid recording groups')
    ROOT.mkdir(parents=True,exist_ok=True)
    issuer=Path('/tmp/handspeak-ucf-ca/intermediate.pem')
    # Complete the publisher's missing intermediate, without disabling verification.
    subprocess.run(['openssl','verify','-CAfile','/etc/ssl/certs/ca-certificates.crt',
                    '-untrusted',str(issuer),'-verify_hostname','www.crcv.ucf.edu',
                    '/tmp/handspeak-ucf-ca/leaf.pem'],check=True)
    shutil.copyfile(issuer,ROOT/'publisher-intermediate.pem')
    context=ssl.create_default_context(cafile='/etc/ssl/certs/ca-certificates.crt')
    context.load_verify_locations(str(issuer))
    rows=[dict(action=action,group=group,label='OTHER MOVEMENT',split='test',
               participant=f'ucf-recording-group-{action}-{group}',
               source=BASE+f'v_{action}_g{group:02d}_c01.avi',
               file=str(ROOT/f'v_{action}_g{group:02d}_c01.avi'))
          for action in ACTIONS for group in args.groups]
    protocol=dict(selection=rows,rule=f'Four ordinary actions; groups {args.groups}, clip 1; chosen before model scoring',
                  provenance='https://www.crcv.ucf.edu/THUMOS14/download.html',
                  use='Private research evaluation; no training or website redistribution',
                  grouping='Dataset recording groups, not verified unique person identities',
                  attribution='Soomro, Zamir and Shah, UCF101, CRCV-TR-12-01 (2012)',
                  modelScoresViewed=False)
    if args.model_protocol:
        model=json.loads(args.model_protocol.read_text())
        protocol['frozenModelProtocolSha256']=hashlib.sha256(args.model_protocol.read_bytes()).hexdigest()
        protocol['checkpointSha256']=model['checkpointSha256']
    path=ROOT/'protocol.json'
    if path.exists() and json.loads(path.read_text())!=protocol:raise ValueError('Frozen selection changed')
    path.write_text(json.dumps(protocol,indent=2)+'\n')
    def get(row):
        path=Path(row['file'])
        if not path.exists():
            with urllib.request.urlopen(row['source'],context=context,timeout=30) as response:
                data=response.read(20_000_001)
                if len(data)>20_000_000 or not data.startswith(b'RIFF'):raise ValueError('Unexpected media or size')
            temp=path.with_suffix('.partial');temp.write_bytes(data);temp.replace(path)
        return dict(row,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(get,rows))
    (ROOT/'manifest.json').write_text(json.dumps(rows,indent=2)+'\n')
    print('Downloaded',len(rows),'ordinary-action clips',flush=True)


if __name__=='__main__':main()
