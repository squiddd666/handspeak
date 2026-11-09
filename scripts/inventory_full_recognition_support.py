"""Metadata-only support census for all 198 references and both loaded families."""
import argparse,collections,csv,datetime,json
from pathlib import Path
from scripts.run_online_native_audit import ROOT,sha
from scripts.prepare_targeted_data_v4 import MANUAL

PHRASES={'GOOD MORNING','GOOD AFTERNOON','GOOD NIGHT'}

def support(glosses,official,excluded,cached):
    out={}
    for split in ('train','val','test'):
        rows=[r for r in official if r['split']==split and r['gloss'] in glosses and r['file'] not in excluded]
        available=[r for r in rows if r['file'] in cached]
        out[split]=dict(originalRecordings=len(rows),signers=len({r['participant'] for r in rows}),cachedOriginals=len(available),
            cachedSigners=len({r['participant'] for r in available}))
    return out

def choose(rows,count):
    # Diversify by declared participant metadata, not capture/prediction quality.
    rows=sorted(rows,key=lambda r:r['file']);chosen=[];signers=set()
    for r in rows:
        if r['participant'] not in signers:chosen.append(r);signers.add(r['participant'])
        if len(chosen)>=count:return chosen
    identities={r['file'] for r in chosen}
    return (chosen+[r for r in rows if r['file'] not in identities])[:count]

def main(args):
    out=args.out.resolve();out.relative_to((ROOT.parent/'hs-eval').resolve());out.mkdir(exist_ok=False)
    eval_root=ROOT.parent/'hs-eval';frozen={str(ROOT/n):sha(ROOT/n) for n in ('scripts/inventory_full_recognition_support.py','training/test_full_recognition_support.py')};official=[];identities=set();signers=collections.defaultdict(set)
    for split in ('train','val','test'):
        path=eval_root/'cache'/f'{split}.csv';frozen[str(path)]=sha(path)
        for r in csv.DictReader(path.open(encoding='utf-8-sig')):
            if r['Video file'] in identities:raise ValueError('Official source overlap')
            identities.add(r['Video file']);signers[split].add(r['Participant ID'])
            official.append(dict(file=r['Video file'],gloss=r['Gloss'],participant=r['Participant ID'],split=split))
    if any(signers[a]&signers[b] for a,b in (('train','val'),('train','test'),('val','test'))):raise ValueError('Official signer overlap')
    watch_path=ROOT/'models/recognition-videos.json';watch=json.loads(watch_path.read_text('utf-8'));frozen[str(watch_path)]=sha(watch_path)
    excluded={s['originalFile'] for r in watch['items'] for s in r.get('sources',[])}
    excluded_hashes={s['sha256'] for r in watch['items'] for s in r.get('sources',[]) if s.get('sha256')}
    paths=[ROOT/'reports/online-motion-audit-20261107/frozen-online-intake.json',eval_root/'online-worker-recognition-audit-20261108/cohort.json',
        eval_root/'manual-guard-browser-dev-v3-20261108/cohort.json']
    for path in paths:
        data=json.loads(path.read_text('utf-8'));frozen[str(path)]=sha(path)
        for r in data['clips']:
            excluded.add(r.get('sourceFile') or Path(r['path']).name)
            excluded_hashes.add(r['sha256'])
    for path in eval_root.glob('online-motion-audit*/downloads.json'):
        data=json.loads(path.read_text('utf-8'));frozen[str(path)]=sha(path)
        rows=data if isinstance(data,list) else data.get('downloads',[])
        for r in rows:
            if r.get('sha256'):excluded_hashes.add(r['sha256'])
            if r.get('path'):excluded.add(Path(r['path']).name)
    # Only known ORIGINAL research directories; do not inventory derived Watch clips.
    roots=[eval_root/'cache',eval_root/'beginner-100/videos',eval_root/'beginner-100/clips',eval_root/'daily-words/videos',
        eval_root/'daily-words/pack-clips',eval_root/'motion-repair-v4-20261107/videos']
    cached={}
    for root in roots:
        for path in sorted(root.rglob('*.mp4')):
            if path.name in identities and path.name not in excluded:cached.setdefault(path.name,str(path.resolve()))
    prior_path=eval_root/'full198-production-browser-v2-20261108/protocol.json';prior=json.loads(prior_path.read_text('utf-8'));frozen[str(prior_path)]=sha(prior_path)
    map_path=ROOT/'models/beginner-100-label-map.json';bm=json.loads(map_path.read_text('utf-8'));frozen[str(map_path)]=sha(map_path)
    beginner={r['label']:r['citizenGlosses'] for r in bm['entries']}
    # MORNING is its own loaded output, not interchangeable with GOOD MORNING.
    beginner['MORNING']=['MORNING']
    loaded_beginner=prior['productionStatus']['beginner']['labels'];loaded_full=prior['productionStatus']['capstone']['labels']
    if len(loaded_beginner)!=79 or len(loaded_full)!=100:raise ValueError('Wrong loaded family sizes')
    families={};gloss_union=set()
    for family,labels in [('beginner',loaded_beginner),('capstone',loaded_full),('manual',list(MANUAL))]:
        rows=[]
        for label in labels:
            glosses=beginner.get(label,[]) if family=='beginner' else MANUAL[label] if family=='manual' else [label]
            gloss_union.update(glosses);s=support(set(glosses),official,excluded,cached)
            natural=label not in PHRASES
            rows.append(dict(label=label,glosses=glosses,support=s,naturalTargetSupported=natural,
                componentOnly=not natural,minimumCachedMetadataSupport=natural and s['train']['cachedOriginals']>=3 and s['val']['cachedOriginals']>=3 and s['val']['cachedSigners']>=2))
        families[family]=rows
    references=[]
    for r in watch['items']:
        glosses=MANUAL.get(r['label'],r.get('modelGlosses',[]));s=support(set(glosses),official,excluded,cached)
        references.append(dict(id=r['id'],label=r['label'],recognitionModes=r['recognitionModes'],glosses=glosses,support=s,
            componentOnly=r['label'] in PHRASES,minimumCachedMetadataSupport=r['label'] not in PHRASES and s['train']['cachedOriginals']>=3 and s['val']['cachedOriginals']>=3 and s['val']['cachedSigners']>=2))
    if len(references)!=198 or len({r['id'] for r in references})!=198:raise ValueError('Full-198 support coverage missing')
    chosen=[]
    for gloss in sorted(gloss_union):
        for split in ('train','val'):
            pool=[r for r in official if r['gloss']==gloss and r['split']==split and r['file'] in cached and r['file'] not in excluded]
            for r in choose(pool,4 if split=='train' else 3):chosen.append({**r,'path':cached[r['file']]})
    selected=[]
    for r in chosen:
        digest=sha(Path(r['path']))
        if digest in excluded_hashes:continue
        selected.append({**r,'sha256':digest});frozen[r['path']]=digest
    # Hash exclusions also affect cached-support counts. Do not claim verified
    # eligibility from this census alone: the exact capture plan must revalidate.
    report=dict(purpose='full-family-source-support-metadata-census',frozenAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        references=references,families=families,selectedCachedTrainVal=selected,frozenFilesSha256=frozen,
        excludedSourceFiles=sorted(excluded),excludedOriginalHashes=sorted(excluded_hashes),
        selection='Up to four TRAIN / three VAL cached originals per exact gloss, first distinct participants then first filenames. No features or outcomes influence selection.',
        componentWarning='Three greetings have isolated component support only; no natural continuous phrase recording or accuracy is fabricated.',
        testMetadataOnly=True,testFeaturesRead=False,auditOutcomesRead=False,previouslyCapturedOriginalsAreNotNew=True,
        productionChanges=False,trainingPerformed=False,requiresSeparateFrozenCapturePlan=True,
        scope='All 198 reference labels, loaded Beginner-79/Capstone-100 and manual24. Source metadata/cached availability is not detector usability or recognition accuracy.')
    (out/'support.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    summary=dict(referenceLabels=198,referenceMetadataSupported=sum(r['minimumCachedMetadataSupport'] for r in references),
        families={k:dict(labels=len(rows),minimumCachedMetadataSupported=sum(r['minimumCachedMetadataSupport'] for r in rows),
            missing=[r['label'] for r in rows if not r['minimumCachedMetadataSupport']]) for k,rows in families.items()},
        selectedCachedTrainVal=dict(collections.Counter(r['split'] for r in selected)),selectedOriginals=len(selected),
        naturalPhraseRecordingsFound=0,testOutcomesRead=False,predictionsRun=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n','utf-8');print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);main(p.parse_args())
