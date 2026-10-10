"""New ordinary recordings for one frozen word, selected before model scoring."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import ssl
import time
import urllib.request
import evaluate_novel_ordinary as evaluation
from calibrate_word_thresholds import write,sha
BASE=Path('/opt/handspeak-training')
REPO=Path(__file__).resolve().parents[2]
URL='https://www.crcv.ucf.edu/THUMOS14/UCF101/UCF101/'

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--word',required=True);parser.add_argument('--clip',type=int,default=2);parser.add_argument('--reviewed',action='store_true');args=parser.parse_args()
    if args.word not in ['CALL','FIND','FISH','SEE','SICK','PAIN','NIGHT','MORNING'] or not 2<=args.clip<=4:raise ValueError('Unsupported cohort')
    root=BASE/'single-word-20261010'/args.word.lower();model=root/'frozen';media=root/f'ordinary-c{args.clip}';report=REPO/'reports/vocabulary-expansion/single-word'/args.word.lower()/'fresh'
    if args.reviewed:
        evaluation.MODEL=model;evaluation.MEDIA=media;evaluation.ROOT=root/f'ordinary-evaluation-c{args.clip}';evaluation.REPORT=report;evaluation.main();return
    deadline=time.monotonic()+7200
    while not (model/'protocol.json').exists():
        completed=REPO/'reports/vocabulary-expansion/single-word'/args.word.lower()/'completion.json'
        if completed.exists() and not json.loads(completed.read_text())['passesDevelopmentScreen']:raise ValueError('Development failed')
        if time.monotonic()>deadline:raise TimeoutError('Frozen model not available')
        time.sleep(5)
    p=json.loads((model/'protocol.json').read_text());rows=[]
    choices=[(a,g) for a in ['Typing','BrushingTeeth','ApplyEyeMakeup','ShavingBeard'] for g in [22,23,24]]
    choices += [(a,g) for a in ['ApplyLipstick','HeadMassage'] for g in range(19,25)]
    for action,group in choices:
        name=f'v_{action}_g{group:02d}_c{args.clip:02d}.avi'
        rows.append(dict(action=action,group=group,label='OTHER MOVEMENT',split='test',participant=f'ucf-recording-group-{action}-{group}',source=URL+name,file=str(media/name)))
    known=set()
    for manifest in BASE.rglob('manifest.json'):
        if media in manifest.parents:continue
        try:entries=json.loads(manifest.read_text())
        except (ValueError,OSError):continue
        if isinstance(entries,list):known.update(r['sha256'] for r in entries if isinstance(r,dict) and 'sha256' in r)
    plan=dict(checkpointSha256=p['checkpointSha256'],modelProtocolSha256=sha(model/'protocol.json'),selection=rows,knownHashes=sorted(known),rule=f'Preselected clip {args.clip} for old four actions groups22–24 and two additional actions groups19–24. No scores viewed.',scope='Fresh recordings from previously encountered groups, not independent people. Private research only.',implementationSha256=sha(__file__))
    path=media/'protocol.json'
    if path.exists():
        prior=json.loads(path.read_text())
        # The known-content snapshot is fixed at first selection, not refreshed on retry.
        plan['knownHashes']=prior['knownHashes']
        if prior!=plan:raise ValueError('Frozen selection changed')
    write(path,plan)
    context=ssl.create_default_context();context.load_verify_locations('/tmp/handspeak-ucf-ca/intermediate.pem')
    def get(row):
        target=Path(row['file'])
        if not target.exists():
            with urllib.request.urlopen(row['source'],context=context,timeout=45) as response:data=response.read(20_000_001)
            if len(data)>20_000_000 or not data.startswith(b'RIFF'):raise ValueError('Unexpected media')
            tmp=target.with_suffix('.partial');tmp.write_bytes(data);tmp.replace(target)
        return dict(row,sha256=sha(target))
    with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(get,rows))
    if len({r['sha256'] for r in rows})!=len(rows) or set(plan['knownHashes'])&{r['sha256'] for r in rows}:raise ValueError('Previously used or duplicate recordings')
    write(media/'manifest.json',rows);write(report/'ordinary-acquisition.json',dict(word=args.word,clips=len(rows),stage='needs-content-review',modelScoresViewed=False,deployed=False))
    print('Downloaded',len(rows),'clips; review before evaluation',flush=True)
if __name__=='__main__':main()
