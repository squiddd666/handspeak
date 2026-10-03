"""Read held-out archive headers only; never request video payloads or score models."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import http.client
import json
from pathlib import Path
import re
import tarfile
from urllib.parse import urlsplit

ROOT=Path('/opt/handspeak-training')
OUT=ROOT/'vocabulary-expansion-holdout-readiness'
LABELS=['AIRPLANE','CAN','FINE','SHOWER']


def scan(job):
    label,url,known_names,known_signers=job
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.netloc!='signdata.cc.gatech.edu' or not parsed.path.startswith('/data/popsign_v1_0/game/test/') or parsed.query or parsed.fragment:
        raise ValueError('Only official held-out archive headers may be read')
    connection=http.client.HTTPSConnection(parsed.netloc,timeout=30)
    offset=0;rows=[];complete=False
    try:
        for _ in range(3000):
            connection.request('GET',parsed.path,headers={'Range':f'bytes={offset}-{offset+511}'})
            response=connection.getresponse()
            match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.getheader('Content-Range',''))
            if response.status!=206 or not match or tuple(map(int,match.groups()[:2]))!=(offset,offset+511):
                raise ValueError('Server did not honor the exact 512-byte header range')
            header=response.read(513)
            if len(header)!=512:raise ValueError('Unexpected header length')
            if header==bytes(512):complete=True;break
            info=tarfile.TarInfo.frombuf(header,'utf-8','replace')
            if info.size<0:raise ValueError('Invalid archive entry length')
            start=offset+512;offset=start+((info.size+511)//512)*512
            participant=re.search(r'4a\.(\d+)',info.name)
            if info.isfile() and info.name.endswith('.mp4') and participant:
                rows.append(dict(member=info.name,participant=participant.group(1),offset=start,size=info.size))
    finally:connection.close()
    (OUT/'indexes').mkdir(parents=True,exist_ok=True)
    (OUT/'indexes'/(label+'.json')).write_text(json.dumps(dict(source=url,rows=rows,complete=complete),indent=2)+'\n')
    return dict(label=label,archiveCompletelyScanned=complete,recordings=len(rows),
                previouslyUnselectedRecordings=sum(Path(r['member']).name not in known_names for r in rows),
                previouslyUnselectedSigners=len({r['participant'] for r in rows}-known_signers),
                recordingsFromPreviouslyUnselectedSigners=sum(r['participant'] not in known_signers for r in rows))


def main():
    known_names={p.name for p in ROOT.rglob('*.mp4')};known_signers=set();sources={label:set() for label in LABELS};manifests={}
    for path in ROOT.rglob('*.json'):
        if path.name not in ('manifest.json','development-manifest.json','test-manifest.json','fresh-test-manifest.json','selection.json'):
            continue
        data=json.loads(path.read_text())
        if not isinstance(data,list):continue
        used=False
        for row in data:
            if not isinstance(row,dict) or not str(row.get('source','')).startswith('https://signdata.cc.gatech.edu/data/popsign_v1_0/game/'):
                continue
            used=True
            if row.get('participant') is not None:known_signers.add(str(row['participant']))
            for key in ('member','file'):
                if row.get(key):known_names.add(Path(row[key]).name)
            if row.get('label') in sources:
                sources[row['label']].add(row['source'].replace('/train/','/test/').replace('/val/','/test/'))
        if used:manifests[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    if any(len(urls)!=1 for urls in sources.values()):raise ValueError('Established source mapping is missing or ambiguous')
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'metadata-protocol.json').write_text(json.dumps(dict(labels=LABELS,manifestHashes=manifests,
        sourceMappings={k:next(iter(v)) for k,v in sources.items()},knownSignerIds=sorted(known_signers),
        metadataOnly=True,testMediaDownloaded=False,testFeaturesOpened=False),indent=2)+'\n')
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(scan,[(label,next(iter(sources[label])),known_names,known_signers) for label in LABELS]))
    report=dict(words=results,testMediaDownloaded=False,testFeaturesOpened=False,
        limitations='Conservative metadata audit: previously selected signers are excluded even if their reserved clips may not have been evaluated. Unselected filenames still require content-hash checks after a candidate is frozen. No recognition or accuracy result.')
    output=Path(__file__).resolve().parents[2]/'reports/vocabulary-expansion/holdout-readiness.json'
    output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
