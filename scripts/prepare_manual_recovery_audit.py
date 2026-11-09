"""Freeze recovery candidate, acquire unused originals, never run recognition."""
import argparse,datetime,json,shutil
from pathlib import Path
from scripts import prepare_online_motion_audit as acquisition
from scripts.run_online_native_audit import ROOT,sha,verify
from scripts.train_manual_open_set_guard import verify_dev


def verified_candidate(folder):
    report=json.loads((folder/'validation.json').read_text('utf-8'))
    parity=json.loads((folder/'runtime-parity.json').read_text('utf-8'))
    digest=sha(folder/'candidate.json')
    if digest!=report['modelSha256'] or digest!=parity['modelSha256'] or not all(parity.get(k) for k in ('baselineIdentical','guardIdentical','recoveryIdentical')):
        raise ValueError('Candidate must be frozen and exact-runtime verified')
    if report['testUsedForSelection'] or report['auditOutcomesRead'] or report['deployed']:
        raise ValueError('Audit candidate has fitting/deployment contamination')
    return digest


def main(args):
    candidate=args.candidate.resolve();digest=verified_candidate(candidate)
    cp=json.loads((candidate/'protocol.json').read_text('utf-8'));verify({'frozenFilesSha256':cp['frozenInputsSha256']})
    dev=Path(cp['development']);dp=json.loads((dev/'protocol.json').read_text('utf-8'));verify_dev(dp)
    out=args.out.resolve();batch=args.batch.resolve()
    for folder in (out,batch):
        folder.relative_to((ROOT.parent/'hs-eval').resolve());folder.mkdir(exist_ok=False)
    prior=json.loads((ROOT.parent/'hs-eval/online-worker-recognition-audit-20261108/protocol.json').read_text('utf-8'));verify(prior)
    frozen=dict(prior['frozenFilesSha256'])
    frozen.update({str(candidate/n):sha(candidate/n) for n in ('protocol.json','candidate.json','validation.json','runtime-parity.json')})
    frozen.update({str(ROOT/n):sha(ROOT/n) for n in ('scripts/prepare_manual_recovery_audit.py','training/experimental/manual_recovery_runtime.mjs',
        'training/experimental/manual_open_set_guard_v2.mjs','training/experimental/prepared_tracker_factory.mjs')})
    acquisition.write_new(out/'pre-acquisition-freeze.json',dict(frozenAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        candidate=str(candidate/'candidate.json'),candidateSha256=digest,frozenFilesSha256=frozen,
        classifierArtifactsSha256=prior['classifierArtifactsSha256'],productionStatus=prior['productionStatus'],
        metadataSelectionOffset=args.min_archive_video_index,trainingAllowed=False,calibrationAllowed=False,deploymentAllowed=False,
        predictionsRun=False,newSignerAudit=False,full198Audit=False,
        acceptance='No promotion without independent positive retention and unsupported-sign checks. Existing audits remain fitting-excluded.',
        purpose='unused-recording-known-signer-audit-acquisition-only'))
    publisher=batch/'publisher';publisher.mkdir()
    for p in (ROOT.parent/'hs-eval/online-motion-audit-20261107/publisher').iterdir():
        if p.is_file():shutil.copy2(p,publisher/p.name)
    original=acquisition.inventory
    def inventory():
        keys,hashes,fitting,inputs=original()
        # Explicitly include all actual worker-audit originals even if older
        # provenance scanners do not recognize their containing folder names.
        for f in (ROOT.parent/'hs-eval').glob('online-worker-recognition-audit*/cohort.json'):
            value=json.loads(f.read_text('utf-8'))
            for row in value['clips']:
                if row.get('member'):
                    key=acquisition.recording_key(row['member'])
                    if key:keys.add(key)
                hashes.add(row['sha256'])
            inputs[str(f)]=sha(f)
        inputs[str(out/'pre-acquisition-freeze.json')]=sha(out/'pre-acquisition-freeze.json')
        acquisition.write_new(out/'excluded-identity-inventory.json',dict(recordingKeys=sorted(keys),hashes=sorted(hashes),
            fittingSignerIds=sorted(fitting),sourceInputsSha256=inputs,
            scope='Available local provenance, prior actual downloads, worker-audit cohorts and Watch hashes; cross-dataset signer identity unverified.'))
        return keys,hashes,fitting,inputs
    acquisition.inventory=inventory
    print('Candidate frozen before acquisition; recognition and gate adjustment prohibited.',flush=True)
    acquisition.main(argparse.Namespace(out=batch,min_archive_video_index=args.min_archive_video_index,
        allow_unverified_publisher_tls=args.allow_unverified_publisher_tls))
    verify({'frozenFilesSha256':frozen})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--batch',type=Path,required=True)
    p.add_argument('--min-archive-video-index',type=int,default=135);p.add_argument('--allow-unverified-publisher-tls',action='store_true')
    main(p.parse_args())
