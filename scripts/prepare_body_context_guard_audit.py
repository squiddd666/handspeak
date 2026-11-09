"""Freeze body-context candidate, then acquire a new unused PopSign TEST audit cohort.

No recognition runs here. Prior guard-audit54, phone TRAIN/VAL, Citizen fitting
captures, and earlier online audits stay excluded from selection. The acquired
originals are audit-only and must never fit gates.
"""
from __future__ import annotations

import argparse
import datetime
import json
import shutil
from pathlib import Path

from scripts import prepare_online_motion_audit as acquisition
from scripts.run_online_native_audit import ROOT, sha


def verified_candidate(folder):
    report = json.loads((folder / 'validation.json').read_text(encoding='utf-8'))
    digest = sha(folder / 'candidate.json')
    if digest != report['candidateSha256']:
        raise ValueError('Candidate digest drifted from frozen validation')
    if not report.get('parity', {}).get('predictionsIdentical'):
        raise ValueError('Candidate lacks Python/JS parity freeze')
    if report.get('deployed') or report.get('auditOutcomesRead') or report.get('testRead'):
        raise ValueError('Candidate has fitting/deployment contamination')
    model = json.loads((folder / 'candidate.json').read_text(encoding='utf-8'))
    if model.get('featureVersion') != 'body-context-recovery-v1':
        raise ValueError('Unexpected body-context feature version')
    if any(mode.get('recoveryPolicies') for mode in model['modes'].values()):
        raise ValueError('Guard audit receiver requires rejection-only candidate')
    return digest, report


def main(args):
    candidate = args.candidate.resolve()
    digest, report = verified_candidate(candidate)
    out = args.out.resolve()
    batch = args.batch.resolve()
    for folder in (out, batch):
        folder.relative_to((ROOT.parent / 'hs-eval').resolve())
        folder.mkdir(exist_ok=False)

    prior = json.loads((ROOT.parent / 'hs-eval/online-worker-recognition-audit-20261108/protocol.json').read_text(encoding='utf-8'))
    frozen = {
        str(candidate / 'candidate.json'): digest,
        str(candidate / 'validation.json'): sha(candidate / 'validation.json'),
        str(candidate / 'protocol.json'): sha(candidate / 'protocol.json'),
        str(ROOT / 'scripts/prepare_body_context_guard_audit.py'): sha(ROOT / 'scripts/prepare_body_context_guard_audit.py'),
        str(ROOT / 'training/test_body_context_guard_audit.py'): sha(ROOT / 'training/test_body_context_guard_audit.py'),
        str(ROOT / 'scripts/prepare_online_motion_audit.py'): sha(ROOT / 'scripts/prepare_online_motion_audit.py'),
        str(ROOT / 'scripts/verify_online_audit_videos.py'): sha(ROOT / 'scripts/verify_online_audit_videos.py'),
    }
    acquisition.write_new(out / 'pre-acquisition-freeze.json', dict(
        frozenAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        purpose='body-context-unused-recording-known-signer-audit-acquisition-only',
        candidate=str(candidate / 'candidate.json'),
        candidateSha256=digest,
        candidateValidation=str(candidate / 'validation.json'),
        captures=report.get('captures'),
        frozenFilesSha256=frozen,
        classifierArtifactsSha256=prior['classifierArtifactsSha256'],
        productionStatus=prior['productionStatus'],
        metadataSelectionOffset=args.min_archive_video_index,
        trainingAllowed=False,
        calibrationAllowed=False,
        deploymentAllowed=False,
        predictionsRun=False,
        newSignerAudit=False,
        full198Audit=False,
        priorGuardAudit54FittingExcluded=True,
        acceptance='No promotion without independent positive retention on this new cohort. Guard-audit54 remains fitting-excluded forever.'))

    publisher = batch / 'publisher'
    publisher.mkdir()
    source_publisher = ROOT.parent / 'hs-eval/online-motion-audit-recovery-20261108/publisher'
    for path in source_publisher.iterdir():
        if path.is_file():
            shutil.copy2(path, publisher / path.name)

    original = acquisition.inventory

    def inventory():
        keys, hashes, fitting, inputs = original()
        eval_root = ROOT.parent / 'hs-eval'
        extra = []
        for pattern in (
            'online-motion-audit*/downloads.json',
            'online-worker-recognition-audit*/cohort.json',
            'browser-domain-guard-audit*/cohort.json',
            'phone-domain-acquisition*/downloads.json',
            'phone-domain-feature-intake*/sources.json',
            'browser-domain-development*/sources.json',
            'full-family-body-domain-development*/sources.json',
            'manual-recovery-audit*/excluded-identity-inventory.json',
        ):
            extra.extend(eval_root.glob(pattern))
        for path in extra:
            data = json.loads(path.read_text(encoding='utf-8'))
            rows = data if isinstance(data, list) else data.get('downloads') or data.get('clips') or data.get('recordingKeys') and [] or []
            if isinstance(data, dict) and 'recordingKeys' in data:
                for key in data['recordingKeys']:
                    keys.add(tuple(key))
                hashes.update(data.get('hashes', []))
                inputs[str(path)] = sha(path)
                continue
            for row in rows:
                member = row.get('member') or row.get('originalName') or row.get('sourceFile') or row.get('file')
                if isinstance(member, str):
                    key = acquisition.recording_key(member)
                    if key:
                        keys.add(key)
                        if row.get('split') in ('train', 'val'):
                            fitting.add(key[0])
                for field in ('sha256', 'sourceSha256', 'videoSha256'):
                    digest_value = row.get(field)
                    if isinstance(digest_value, str) and len(digest_value) == 64:
                        hashes.add(digest_value)
            inputs[str(path)] = sha(path)
        inputs[str(out / 'pre-acquisition-freeze.json')] = sha(out / 'pre-acquisition-freeze.json')
        acquisition.write_new(out / 'excluded-identity-inventory.json', dict(
            recordingKeys=sorted(keys),
            hashes=sorted(hashes),
            fittingSignerIds=sorted(fitting),
            sourceInputsSha256=inputs,
            scope='Prior actual downloads, phone TRAIN/VAL, Citizen fitting intakes, worker/guard cohorts and Watch hashes; cross-dataset signer identity unverified.'))
        return keys, hashes, fitting, inputs

    acquisition.inventory = inventory
    print('Body-context candidate frozen before acquisition; recognition and gate adjustment prohibited.', flush=True)
    acquisition.main(argparse.Namespace(
        out=batch,
        min_archive_video_index=args.min_archive_video_index,
        allow_unverified_publisher_tls=args.allow_unverified_publisher_tls))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--batch', type=Path, required=True)
    parser.add_argument('--min-archive-video-index', type=int, default=150)
    parser.add_argument('--allow-unverified-publisher-tls', action='store_true')
    main(parser.parse_args())
