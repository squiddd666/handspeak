"""Freeze a fresh ordinary-action selection against the eight-word candidate."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import ssl
import urllib.request
from calibrate_word_thresholds import sha,write
ROOT=Path('/opt/handspeak-training/novel-eight-ordinary')
MODEL=Path('/opt/handspeak-training/vocabulary-expansion-novel-eight-frozen/protocol.json')
URL='https://www.crcv.ucf.edu/THUMOS14/UCF101/UCF101/'

def main():
    p=json.loads(MODEL.read_text());rows=[]
    choices=[(a,25,c) for a in ['Typing','BrushingTeeth','ApplyEyeMakeup','ShavingBeard'] for c in [1,2,3]]
    choices += [(a,g,1) for a in ['ApplyLipstick','HeadMassage'] for g in range(19,25)]
    for action,group,clip in choices:
        name=f'v_{action}_g{group:02d}_c{clip:02d}.avi'
        rows.append(dict(action=action,group=group,label='OTHER MOVEMENT',split='test',participant=f'ucf-recording-group-{action}-{group}',source=URL+name,file=str(ROOT/name)))
    protocol=dict(checkpointSha256=p['checkpointSha256'],modelProtocolSha256=sha(MODEL),selection=rows,rule='Old four actions: group25 clips1–3; two additional actions: groups19–24 clip1. Chosen before scoring or reviewing this media.',scope='Fresh recordings, not verified new people. Private research only; no raw video redistribution.',implementationSha256=sha(__file__))
    path=ROOT/'protocol.json'
    if path.exists() and json.loads(path.read_text())!=protocol:raise ValueError('Frozen selection changed')
    write(path,protocol)
    context=ssl.create_default_context();context.load_verify_locations('/tmp/handspeak-ucf-ca/intermediate.pem')
    def download(row):
        target=Path(row['file'])
        if not target.exists():
            with urllib.request.urlopen(row['source'],context=context,timeout=45) as response:data=response.read(20_000_001)
            if len(data)>20_000_000 or not data.startswith(b'RIFF'):raise ValueError('Unexpected video')
            temp=target.with_suffix('.partial');temp.write_bytes(data);temp.replace(target)
        return dict(row,sha256=sha(target))
    with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(download,rows))
    known=set()
    for name in ['ordinary-movement-ucf101','ordinary-movement-fresh19','ordinary-movement-fresh22','ordinary-training-expanded','ordinary-development']:
        manifest=ROOT.parent/name/'manifest.json'
        if manifest.exists():known.update(r['sha256'] for r in json.loads(manifest.read_text()))
    if len({r['sha256'] for r in rows})!=len(rows) or known&{r['sha256'] for r in rows}:raise ValueError('Duplicate or previously used clips')
    write(ROOT/'manifest.json',rows);print('Downloaded',len(rows),'fresh ordinary recordings',flush=True)
if __name__=='__main__':main()
