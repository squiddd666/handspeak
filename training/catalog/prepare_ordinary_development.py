"""Download separate ordinary-action development clips, never the reserved test groups."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import ssl
import urllib.request

ROOT=Path('/opt/handspeak-training/ordinary-development-ucf101')
BASE='https://www.crcv.ucf.edu/THUMOS14/UCF101/UCF101/'
ACTIONS=['Typing','BrushingTeeth','ApplyEyeMakeup','ShavingBeard']


def main():
    ROOT.mkdir(exist_ok=True)
    rows=[dict(action=action,group=group,label='OTHER MOVEMENT',
               split='train' if group<=15 else 'val',
               participant=f'ucf-recording-group-{action}-{group}',
               source=BASE+f'v_{action}_g{group:02d}_c01.avi',
               file=str(ROOT/f'v_{action}_g{group:02d}_c01.avi'))
          for action in ACTIONS for group in range(4,19)]
    protocol=dict(selection=rows,trainingGroups=list(range(4,16)),
                  validationGroups=[16,17,18],reservedTestGroups=[19,20,21],
                  excludedPreviouslyEvaluatedGroups=[1,2,3],
                  selectionRule='Four previously reviewed action categories; fixed recording groups and clip 1. No score-based media selection.',
                  grouping='Recording groups, not verified unique person identities',
                  use='Private research training/evaluation. No raw media redistribution on the website.',
                  source='https://www.crcv.ucf.edu/data/UCF101.php',
                  attribution='Soomro, Zamir and Shah, UCF101, CRCV-TR-12-01 (2012)',
                  implementationSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    path=ROOT/'protocol.json'
    if path.exists() and json.loads(path.read_text())!=protocol:raise ValueError('Frozen development selection changed')
    path.write_text(json.dumps(protocol,indent=2)+'\n')
    context=ssl.create_default_context()
    context.load_verify_locations('/tmp/handspeak-ucf-ca/intermediate.pem')
    def download(row):
        path=Path(row['file'])
        if not path.exists():
            with urllib.request.urlopen(row['source'],context=context,timeout=30) as response:
                content=response.read(20_000_001)
            if len(content)>20_000_000 or not content.startswith(b'RIFF'):
                raise ValueError('Unexpected video format or size')
            temporary=path.with_suffix('.partial');temporary.write_bytes(content);temporary.replace(path)
        return dict(row,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(download,rows))
    hashes=[r['sha256'] for r in rows]
    old=json.loads(Path('/opt/handspeak-training/ordinary-movement-ucf101/manifest.json').read_text())
    if len(set(hashes))!=len(hashes) or set(hashes)&{r['sha256'] for r in old}:
        raise ValueError('Duplicate media in development selection')
    (ROOT/'manifest.json').write_text(json.dumps(rows,indent=2)+'\n')
    print('Downloaded',len(rows),'development clips; reserved groups untouched.',flush=True)


if __name__=='__main__':main()
