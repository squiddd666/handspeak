"""Metadata-only audit intake. Never trains, decodes, or copies a signer video."""
import argparse,collections,csv,hashlib,json
from pathlib import Path
from scripts.prepare_targeted_data_v4 import MANUAL
ROOT=Path(__file__).resolve().parents[1];EVAL=ROOT.parent/'hs-eval'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def validate_intake(manifest,base,known_signers,known_files,known_hashes):
    if manifest.get('purpose')!='audit-only' or manifest.get('consentConfirmed') is not True or manifest.get('newSignerDeclaration') is not True:
        raise ValueError('Audit-only purpose, consent, and new-signer declaration are required')
    clips=manifest.get('clips',[])
    if not clips:raise ValueError('No new-signer recordings supplied')
    records=[];seen_hashes=set();seen_ids=set()
    used_signers={value.strip().casefold() for value in known_signers}
    used_sources={value.strip().casefold() for value in known_files}
    for index,clip in enumerate(clips,1):
        signer=clip.get('signerId');label=clip.get('label');source=clip.get('sourceId');negative=clip.get('negative')
        if not isinstance(signer,str) or not signer.strip() or signer.strip().casefold() in used_signers:raise ValueError('Missing or previously used signer ID')
        if not isinstance(source,str) or not source.strip() or source.strip().casefold() in used_sources or source.strip().casefold() in seen_ids:raise ValueError('Missing, reused, or duplicate source ID')
        if not isinstance(label,str) or not label.strip() or type(negative) is not bool:raise ValueError('Each clip needs a label and explicit negative flag')
        signer=signer.strip();source=source.strip();label=label.strip().upper()
        if (label in MANUAL)==negative:raise ValueError('Known/unsupported label and negative flag disagree')
        path=Path(clip['path']);path=(base/path).resolve() if not path.is_absolute() else path.resolve()
        if not path.is_file() or path.suffix.lower() not in ('.mp4','.mov','.webm','.mkv'):raise ValueError('Expected an existing signer video')
        if path.name.casefold() in used_sources:raise ValueError('Previously used source filename')
        digest=sha(path)
        if digest in known_hashes or digest in seen_hashes:raise ValueError('Previously used or duplicate clip content')
        seen_hashes.add(digest);seen_ids.add(source.casefold())
        records.append(dict(file=f'fresh-audit-{index:04}',path=str(path),sourceId=source,participant=signer,label=label,
                            manualLabel=label if not negative else None,negative=negative,sha256=digest,split='test',source='User-declared new-signer cohort'))
    return records

def inventory():
    table_paths={s:EVAL/'cache'/f'{s}.csv' for s in ('train','val','test')}
    tables={s:list(csv.DictReader(p.open(encoding='utf-8-sig'))) for s,p in table_paths.items()}
    old_path=ROOT/'reports/motion-repair-v5-20261107/manual-test-selection.json'
    old=json.loads(old_path.read_text(encoding='utf-8'));used={r['participant'] for r in old};test={r['Participant ID'] for r in tables['test']}
    known_signers={r['Participant ID'] for rows in tables.values() for r in rows}
    known_files={r['Video file'] for rows in tables.values() for r in rows}
    known_hashes=set();download_paths=list(EVAL.rglob('*.downloads.json'))
    for path in download_paths:
        data=json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data,list):known_hashes.update(r['sha256'] for r in data if isinstance(r,dict) and r.get('sha256'))
    watch_path=ROOT/'models/recognition-videos.json'
    for item in json.loads(watch_path.read_text(encoding='utf-8'))['items']:
        known_hashes.add(sha(ROOT/item['video']))
    audit=dict(officialTestSigners=len(test),previousAuditSigners=len(used),unusedOfficialTestSigners=sorted(test-used),
               newSignerCohortAvailable=bool(test-used),freshAuditRun=False,
               inputSha256={str(p):sha(p) for p in list(table_paths.values())+[old_path,watch_path]+download_paths},
               scope='Metadata inventory only. Every official test signer was used previously; reused recordings cannot be represented as a new-signer audit.')
    return audit,known_signers,known_files,known_hashes

def main(args):
    args.out.mkdir(parents=True,exist_ok=False)
    audit,signers,files,hashes=inventory()
    (args.out/'existing-cohort-inventory.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8')
    if args.manifest:
        raw=json.loads(args.manifest.read_text(encoding='utf-8'))
        records=validate_intake(raw,args.manifest.parent,signers,files,hashes)
        # Only this explicitly supplied index is saved; videos remain in place.
        (args.out/'frozen-intake.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
        summary=dict(recordings=len(records),signers=len({r['participant'] for r in records}),
                     positiveCounts=dict(collections.Counter(r['label'] for r in records if not r['negative'])),
                     unsupportedSignRecordings=sum(r['negative'] for r in records),metadataAndKnownContentChecksPassed=True,
                     signerIdentityIndependentlyVerified=False,newSignerStatus='declared by provider',freshAuditRun=False,
                     trainingOrGateSelectionAllowed=False,manifestSha256=sha(args.manifest))
        (args.out/'intake-summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    else:
        template=dict(purpose='audit-only',consentConfirmed=False,newSignerDeclaration=False,clips=[
            dict(path='C:/your-recordings/hello-01.mp4',sourceId='new-source-001',signerId='NEW01',label='HELLO',negative=False),
            dict(path='C:/your-recordings/other-sign-01.mp4',sourceId='new-source-002',signerId='NEW01',label='CAR',negative=True)])
        (args.out/'intake-template.json').write_text(json.dumps(template,indent=2)+'\n',encoding='utf-8')
    (args.out/'README.md').write_text('''# Fresh recognition audit intake

No new-signer audit has run. All 11 official test signers have appeared in the
previous audit, so more clips from that split are regression data, not a fresh
signer cohort.

Provide a local folder/path or upload consented new-signer recordings. Annotate
each clip with its true sign label, a pseudonymous signer ID, a unique source
ID, and whether the sign is outside the frozen 24-word candidate vocabulary.
Do not place names, contact details, or other identifying information in IDs.

The intake-template.json examples are placeholders. Consent and new-signer
declarations must be confirmed by the provider; the script does not infer consent
or identity from a face. Keep audit clips out of training and calibration.
Include several independent new signers, all target words (especially NO),
different speeds/viewpoints, and unsupported signs. Missing labels and tracking
failures will remain in the audit denominator; no best-of retries are selected.

The intake validator checks declared signer/source separation, duplicates, and
known downloaded/Watch clip hashes. This is not independent identity proof or
a guarantee that every historical private recording has a known content hash.
It writes a local metadata index only; it does not copy or upload video.
''',encoding='utf-8')
    print(json.dumps({k:v for k,v in audit.items() if k!='inputSha256'},indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path);p.add_argument('--out',type=Path,required=True);main(p.parse_args())
