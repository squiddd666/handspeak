"""Conservative identity screening across renamed PopSign originals, metadata only."""
import argparse,datetime,json,re
from pathlib import Path,PurePosixPath
from scripts.run_online_native_audit import ROOT,sha

PATTERN=re.compile(r'^(?:(?:gtsignstudy)?4a\.(\d+)|([0-9a-f]{4,32}))-([a-z]+)-(\d{4}_\d{2}_\d{2}_\d{2}_\d{2}_\d{2}\.\d+)-(\d+)\.mp4$')

def identity(name):
    match=PATTERN.fullmatch(PurePosixPath(name.replace('\\','/')).name)
    if not match:return None
    legacy,anon,label,time,take=match.groups()
    # Ignore the anonymized prefix for conservative duplicate screening. Equal
    # word/timestamp/take is a possible renamed source even with a new ID.
    return dict(participant=legacy or anon,recordingKey=(label,time,take),legacy=legacy is not None)

def screen(source,slug,known_keys,fitting,mapping,count=3):
    names=source['test']['orig_name'];previous=source['test']['prev_name'];sizes=source['test']['size']
    # Publisher "size" is the cardinality of each name table, NOT video bytes.
    if set(names)!=set(previous) or sizes!={'prev_name':len(previous),'orig_name':len(names)}:raise ValueError('Publisher original/previous/count linkage mismatch')
    selected=[];observed=[];signers=set()
    for index in sorted(names,key=lambda x:int(x)):
        original=identity(names[index]);old=identity(previous[index])
        if not original or not old or original['recordingKey'][0]!=slug:raise ValueError('Unrecognized exact original identity/gloss')
        linked=set(mapping.get(original['participant'],[]));key=original['recordingKey'];previous_key=old['recordingKey']
        reason=('unresolved-previous-source-link' if key!=previous_key else 'known-renamed-recording' if key in known_keys else
            'known-fitting-signer-link' if linked&fitting else 'signer-already-selected' if original['participant'] in signers else
            'fixed-count-already-selected' if len(selected)>=count else 'metadata-eligible')
        row=dict(publisherIndex=index,originalName=names[index],previousName=previous[index],originalByteSizePending=True,
            anonymousParticipant=original['participant'],possibleLegacyParticipants=sorted(linked),recordingKey=list(key),reason=reason)
        observed.append(row)
        if reason=='metadata-eligible':selected.append(row);signers.add(original['participant'])
    return dict(selected=selected,observed=observed,requested=count,metadataEligible=len(selected),
        newSignerVerified=False,originalContentHashesPending=True)

def main(args):
    metadata=args.metadata.resolve();out=args.out.resolve();out.relative_to((ROOT.parent/'hs-eval').resolve());out.mkdir(exist_ok=False)
    eval_root=ROOT.parent/'hs-eval';registry_path=eval_root/'manual-recovery-audit-20261108/excluded-identity-inventory.json'
    registry=json.loads(registry_path.read_text('utf-8'));known=set()
    for participant,suffix in registry['recordingKeys']:
        value=identity('4a.'+participant+'-'+suffix)
        if value:known.add(value['recordingKey'])
    mapping_path=eval_root/'online-motion-audit-recovery-20261108/publisher/legacy-linkage-preliminary.json'
    linkage=json.loads(mapping_path.read_text('utf-8'));mapping=linkage['mapping'];fitting=set(registry['fittingSignerIds'])
    frozen={str(registry_path):sha(registry_path),str(mapping_path):sha(mapping_path),str(Path(__file__)):sha(Path(__file__)),
        str(ROOT/'training/test_popsign_v2_provenance.py'):sha(ROOT/'training/test_popsign_v2_provenance.py')}
    # Prior actual downloads, not publisher inventories of unused records.
    for path in eval_root.glob('online-motion-audit*/downloads.json'):
        data=json.loads(path.read_text('utf-8'));frozen[str(path)]=sha(path)
        for row in data if isinstance(data,list) else data.get('downloads',[]):
            for name in (row.get('member'),row.get('originalName')):
                value=identity(name) if name else None
                if value:known.add(value['recordingKey'])
    result={}
    for slug in ('baby','love'):
        path=metadata/(slug+'-source-map.json');frozen[str(path)]=sha(path)
        result[slug]=screen(json.loads(path.read_text('utf-8')),slug,known,fitting,mapping)
    report=dict(purpose='popsign-v2-renamed-recording-provenance-screening-only',frozenAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        results=result,frozenFilesSha256=frozen,knownPrefixIndependentRecordingKeys=len(known),
        legacyMapping='Preliminary label/timestamp/take evidence, not publisher-certified person linkage. Used conservatively for exclusion, never to claim new people.',
        source='https://signdata.cc.gatech.edu/view/datasets/popsign_v2_1/index.html',publisherLicense='CC BY 4.0',
        freshness='Metadata-eligible unused recording keys under available local provenance only. Original archive membership, original hashes and decode still pending.',
        videosDownloaded=False,predictionsRun=False,trainingAllowed=False,calibrationAllowed=False,newSignerClaim=False,
        followup='Freeze candidate before original test acquisition, verify archive map/size and original hashes, retain duplicates/failures; do not train or tune on these selected test records.')
    (out/'provenance.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    print(json.dumps({slug:dict(metadataEligible=r['metadataEligible'],selectedPrefixes=[x['anonymousParticipant'] for x in r['selected']],originalHashesPending=True,newSignerVerified=False) for slug,r in result.items()}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--metadata',type=Path,required=True);p.add_argument('--out',type=Path,required=True);main(p.parse_args())
