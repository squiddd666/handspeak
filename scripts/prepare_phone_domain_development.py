"""Freeze official PopSign TRAIN/VAL metadata for camera-domain development."""
import argparse,collections,datetime,json
from pathlib import Path
from scripts.run_online_native_audit import ROOT,sha
from scripts.prepare_online_motion_audit import LABELS,recording_key,HOST

def select(source_map,slug,excluded,count=3):
    rows=[];signers={}
    for split in ('train','val','test'):
        names=source_map[split]['orig_name'];signers[split]={recording_key(n)[0] for n in names.values() if recording_key(n)}
    if any(signers[a]&signers[b] for a,b in (('train','val'),('train','test'),('val','test'))):raise ValueError('Official signer split overlap')
    for split in ('train','val'):
        used=set()
        for index,name in sorted(source_map[split]['orig_name'].items(),key=lambda x:x[1]):
            key=recording_key(name)
            if not key or not key[1].startswith(slug+'-'):raise ValueError('Wrong original label/source identity')
            if key in excluded or key[0] in used:continue
            rows.append(dict(label=LABELS[slug],publisherLabel=slug,split=split,participant=key[0],originalName=name,publisherIndex=index,
                recordingKey=list(key),archive=f'https://{HOST}/data/popsign_v1_0/game/{split}/{slug}.tar'))
            used.add(key[0])
            if len(used)==count:break
    return rows

def main(args):
    out=args.out.resolve();out.relative_to((ROOT.parent/'hs-eval').resolve());out.mkdir(exist_ok=False)
    publisher=ROOT.parent/'hs-eval/online-motion-audit-recovery-20261108/publisher'
    registry_path=ROOT.parent/'hs-eval/manual-recovery-audit-20261108/excluded-identity-inventory.json'
    registry=json.loads(registry_path.read_text('utf-8'));excluded={tuple(k) for k in registry['recordingKeys']}
    frozen={str(registry_path):sha(registry_path),str(Path(__file__)):sha(Path(__file__)),str(ROOT/'training/test_phone_domain_development.py'):sha(ROOT/'training/test_phone_domain_development.py')}
    for path in (ROOT.parent/'hs-eval').glob('online-motion-audit*/downloads.json'):
        data=json.loads(path.read_text('utf-8'));frozen[str(path)]=sha(path)
        for r in data if isinstance(data,list) else data.get('downloads',[]):
            key=recording_key(r['member']) if r.get('member') else None
            if key:excluded.add(key)
    sources=[];missing=[]
    for slug in LABELS:
        path=publisher/f'v1-{slug}-source-map.json'
        if not path.exists():missing.append(slug);continue
        source_map=json.loads(path.read_text('utf-8'));frozen[str(path)]=sha(path);sources.extend(select(source_map,slug,excluded))
    if {r['participant'] for r in sources if r['split']=='train'}&{r['participant'] for r in sources if r['split']=='val'}:raise ValueError('Cross-word signer overlap')
    (out/'sources.json').write_text(json.dumps(sources,indent=2)+'\n','utf-8');frozen[str(out/'sources.json')]=sha(out/'sources.json')
    protocol=dict(purpose='official-phone-domain-train-val-metadata-only',frozenAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        frozenFilesSha256=frozen,sourceManifest=str(out/'sources.json'),counts=dict(collections.Counter(r['split'] for r in sources)),
        labels=sorted({r['label'] for r in sources}),missingPublisherMaps=missing,
        selection='Three first-filename remaining official TRAIN and three VAL originals per exact available target/negative label, distinct declared signers; no outcomes/decodes consulted.',
        license='PopSign v1 CC BY 4.0; public-use publisher dataset, originals only; record original hashes and archive membership before capture.',
        sourceScope='Previously available public metadata, not newly acquired recordings yet; no new-signer identity claim across datasets.',
        trainingAllowed=True,calibrationAllowed=True,testSourcesAllowed=False,watchSourcesAllowed=False,auditSourcesAllowed=False,
        auditOutcomesUsedForSourceSelection=False,downloadsPerformed=False,featuresCaptured=False,predictionsRun=False,deploymentAllowed=False,
        missingExactTargets=['BABY','LOVE','NAME','PAIN','WANT'],
        followup='Acquire these frozen TRAIN/VAL originals with checked byte ranges and source map membership, then freeze production-equivalent feature capture. All prior test/audit originals remain fitting-excluded.')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n','utf-8');print(json.dumps(dict(sources=len(sources),counts=protocol['counts'],labels=len(protocol['labels']),predictionsRun=False)),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);main(p.parse_args())
