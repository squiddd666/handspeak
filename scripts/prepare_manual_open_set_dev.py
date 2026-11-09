"""Freeze official train/val source/hash exclusions before rejection development."""
import argparse,collections,csv,datetime,json
from pathlib import Path
from scripts.run_online_native_audit import ROOT,sha,verify
from scripts.prepare_targeted_data_v4 import MANUAL
from scripts.audit_body_manual_v5 import MODES,BASELINE_FILES,RUNTIME_FILES


def prepare(args):
    folder=args.out.resolve(); folder.relative_to((ROOT.parent/'hs-eval').resolve()); folder.mkdir(exist_ok=False)
    native=args.native.resolve()
    rows=[json.loads(l) for l in native.read_text('utf-8').splitlines() if l.strip()]
    if any(r['split'] not in ('train','val') or r.get('error') for r in rows):raise ValueError('Only successful original train/val extraction archive permitted')
    if len({r['file'] for r in rows})!=len(rows):raise ValueError('Duplicate source recording')
    frozen_audit=ROOT.parent/'hs-eval/online-worker-recognition-audit-20261108/protocol.json'
    prior=json.loads(frozen_audit.read_text('utf-8')); verify(prior)
    watch_path=ROOT/'models/recognition-videos.json';watch=json.loads(watch_path.read_text('utf-8'))
    watch_files={s['originalFile'] for item in watch['items'] for s in item.get('sources',[])}
    known_hashes=set();known_files=set();audit_inputs={}
    for p in (ROOT/'reports/online-motion-audit-20261107/frozen-online-intake.json',ROOT.parent/'hs-eval/online-worker-recognition-audit-20261108/cohort.json'):
        c=json.loads(p.read_text('utf-8'));audit_inputs[str(p)]=sha(p)
        for clip in c['clips']:
            known_hashes.add(clip['sha256']);known_files.add(Path(clip['path']).name)
    official={};tables={}
    for split in ('train','val','test'):
        p=ROOT.parent/f'hs-eval/cache/{split}.csv';tables[str(p)]=sha(p)
        for r in csv.DictReader(p.open(encoding='utf-8-sig')):
            if r['Video file'] in official:raise ValueError('Official CSV source overlap')
            official[r['Video file']]=(split,r['Gloss'],r['Participant ID'])
    selection_path=ROOT.parent/'hs-eval/motion-repair-v4-20261107/selection.json'
    selected={r['file']:r for r in json.loads(selection_path.read_text('utf-8'))}
    aliases={gloss:label for label,glosses in MANUAL.items() for gloss in glosses}
    manifest=[];split_signers=collections.defaultdict(set)
    for r in rows:
        if official.get(r['file'])!=(r['split'],r['gloss'],r['participant']):raise ValueError('Extraction does not match the official source/signer split')
        if r['file'] in watch_files or r['file'] in known_files:raise ValueError('Watch/audit source in development')
        path=Path(selected[r['file']]['path']).resolve();digest=sha(path)
        if digest in known_hashes:raise ValueError('Audit original hash in development')
        label=aliases.get(r['gloss'],r['gloss'])
        if r.get('manualLabel') not in (None,label):raise ValueError('Unexpected manual label alias')
        split_signers[r['split']].add(r['participant'])
        manifest.append(dict(file=r['file'],path=str(path),sha256=digest,split=r['split'],participant=r['participant'],gloss=r['gloss'],label=label))
    if split_signers['train']&split_signers['val']:raise ValueError('Train/validation signer overlap')
    test_signers={p for split,gloss,p in official.values() if split=='test'}
    if (split_signers['train']|split_signers['val'])&test_signers:raise ValueError('Official test signer in development')
    inputs={str(native):sha(native),str(selection_path):sha(selection_path),str(watch_path):sha(watch_path),str(frozen_audit):sha(frozen_audit),**tables,**audit_inputs}
    names=['scripts/prepare_manual_open_set_dev.py','scripts/train_manual_open_set_guard.py','scripts/verify_manual_open_set_guard.py',
        'scripts/audit_body_manual_v5.py','scripts/train_native_manual_v4.py','scripts/prepare_native_repair_v4.py','scripts/prepare_targeted_data_v4.py',
        'training/experimental/manual_open_set_guard.mjs','training/experimental/online_manual_runtime.mjs','training/ux/run_manual_guard_baseline.mjs',
        'training/test_manual_open_set_guard.py','training/test_manual_open_set_guard.mjs']+RUNTIME_FILES+list(BASELINE_FILES.values())
    inputs.update({str(ROOT/n):sha(ROOT/n) for n in names})
    protocol=dict(frozenAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),purpose='local-noncommercial-development-only',
        source='ASL Citizen, previously used official train/validation originals; not new recordings/signers',
        sourceLicense='ASL Citizen noncommercial research terms; originals and derived candidate stay local, no source-video redistribution',
        nativeArchive=str(native),nativeSha256=sha(native),frozenInputsSha256=inputs,
        productionFrozenFilesSha256=prior['frozenFilesSha256'],classifierArtifactsSha256=prior['classifierArtifactsSha256'],
        sourceOriginalsSha256={r['path']:r['sha256'] for r in manifest},manualModes=MODES,predeclaredManualAliases=MANUAL,
        counts=dict(collections.Counter(r['split'] for r in manifest)),signers={k:sorted(v) for k,v in split_signers.items()},
        prototypeSelection='4 deterministic medoid/farthest-point representatives per label, usable TRAIN encodings only, rounded to six decimals before validation',
        maxPrototypeCount=256,selection='Global distance/separation gate per mode selected on VAL only. Rejection-only; cannot create or change baseline predictions.',
        limits=[.2,.3,.4,.5,.65,.8,1.,1.5,2.,3.,5.,10.],ratios=[0.,.25,.5,.75,1.,1.1,1.2,1.3,1.5,2.,3.,5.],
        selectionRequirements='No loss of baseline correctly accepted validation recordings in ANY label; no increase in incorrect/unsupported accepts. Require at least 25% fewer unsupported accepts per enabled mode; otherwise leave that mode disabled.',
        gateTieBreak='Fewest unsupported accepts, then fewest known-word errors, then least restrictive ratio/distance. Not probability confidence.',
        deploymentAllowed=False,auditTrainingAllowed=False,watchTrainingAllowed=False,
        auditCohortsExcluded=['previous 76 originals','fresh 62 originals'],auditOutcomesReadForFitting=False,
        knownCrossDatasetSignerIdentitySeparationVerified=False,nativeNotBrowserEquivalent=True,
        futureGate='No production promotion without a frozen unused-recording browser audit and positive-retention checks. Existing online audits cannot be recycled to tune/select this candidate.')
    with (folder/'source-manifest.json').open('x',encoding='utf-8') as f:json.dump(manifest,f,indent=2)
    with (folder/'protocol.json').open('x',encoding='utf-8') as f:json.dump(protocol,f,indent=2)
    print('Frozen development intake',protocol['counts'],'source/signer/Watch/audit exclusions passed; no predictions run.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--native',type=Path,required=True);p.add_argument('--out',type=Path,required=True);prepare(p.parse_args())
