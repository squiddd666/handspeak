"""Expand near-face negative training data; keep prior test groups excluded."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import ssl
import urllib.request
ROOT=Path('/opt/handspeak-training/ordinary-training-expanded')
BASE='https://www.crcv.ucf.edu/THUMOS14/UCF101/UCF101/'
ACTIONS=['ApplyEyeMakeup','ShavingBeard','ApplyLipstick','HeadMassage']
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n')
def main():
    rows=[]
    for action in ACTIONS:
        groups=range(4,16) if action in ACTIONS[:2] else range(4,19)
        for group in groups:
            for clip in ([2,3] if action in ACTIONS[:2] else [1]):
                split='train' if group<16 else 'val'
                name=f'v_{action}_g{group:02d}_c{clip:02d}.avi'
                rows.append(dict(action=action,group=group,label='OTHER MOVEMENT',split=split,participant=f'ucf-recording-group-{action}-{group}',source=BASE+name,file=str(ROOT/name)))
    plan=dict(selection=rows,rule='Add clips 2/3 in existing training groups 4–15 for makeup/shaving; add lipstick/head massage groups 4–15 for training and 16–18 for validation. Prior test groups 1–3 and 19–24 are excluded for all existing actions. New actions groups 19–25 reserved.',scope='Private research training; groups are not verified unique persons; no raw video publication',implementationSha256=sha(__file__))
    path=ROOT/'protocol.json'
    if path.exists() and json.loads(path.read_text())!=plan:raise ValueError('Frozen selection changed')
    write(path,plan)
    context=ssl.create_default_context();context.load_verify_locations('/tmp/handspeak-ucf-ca/intermediate.pem')
    def download(row):
        path=Path(row['file'])
        if not path.exists():
            with urllib.request.urlopen(row['source'],context=context,timeout=30) as response:
                data=response.read(20_000_001)
                if len(data)>20_000_000 or not data.startswith(b'RIFF'):raise ValueError('Unexpected source media')
            tmp=path.with_suffix('.partial');tmp.write_bytes(data);tmp.replace(path)
        return dict(row,sha256=sha(path))
    with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(download,rows))
    heldout=set()
    for name in ['ordinary-movement-ucf101','ordinary-movement-fresh19','ordinary-movement-fresh22']:
        for r in json.loads((ROOT.parent/name/'manifest.json').read_text()):heldout.add(r['sha256'])
    if len({r['sha256'] for r in result})!=len(result) or heldout&{r['sha256'] for r in result}:raise ValueError('Training clips duplicate test content')
    write(ROOT/'manifest.json',result);print(json.dumps(dict(downloaded=len(result),train=sum(r['split']=='train' for r in result),validation=sum(r['split']=='val' for r in result))))
if __name__=='__main__':main()
