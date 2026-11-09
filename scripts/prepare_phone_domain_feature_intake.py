"""Freeze phone-camera TRAIN/VAL originals into a capture-ready development intake.

Reads only the already-acquired phone-domain originals. No decode, prediction,
audit outcome, Watch clip, or official TEST source is consulted. The resulting
protocol is shaped for the shared production-equivalent landmark capture harness.
"""
from __future__ import annotations

import argparse
import collections
import datetime
import json
from pathlib import Path

from scripts.run_online_native_audit import ROOT, sha, verify


def rows_from_acquisition(downloads):
    rows = []
    for item in downloads:
        if item.get('status') != 'downloaded':
            continue
        if item['split'] not in ('train', 'val'):
            raise ValueError('Phone intake must stay TRAIN/VAL only')
        path = Path(item['path'])
        digest = sha(path)
        if digest != item['sha256']:
            raise ValueError('Phone original hash drifted: ' + item['originalName'])
        rows.append(dict(
            file=item['originalName'],
            path=str(path.resolve()),
            sha256=digest,
            split=item['split'],
            participant=item['participant'],
            gloss=item['label'],
            label=item['label'],
            acquisitionId=item['acquisitionId'],
            publisherLabel=item['publisherLabel'],
            recordingKey=item['recordingKey'],
            domain='phone-popsign-v1'))
    if not rows:
        raise ValueError('No downloaded phone originals')
    if len({r['file'] for r in rows}) != len(rows):
        raise ValueError('Duplicate phone original names')
    if {r['participant'] for r in rows if r['split'] == 'train'} & {r['participant'] for r in rows if r['split'] == 'val'}:
        raise ValueError('Phone TRAIN/VAL signer overlap')
    return rows


def support_table(rows, labels):
    support = {}
    for label in labels:
        train = [r for r in rows if r['split'] == 'train' and r['label'] == label]
        val = [r for r in rows if r['split'] == 'val' and r['label'] == label]
        support[label] = dict(
            train=len(train),
            val=len(val),
            valSigners=len({r['participant'] for r in val}),
            minimumMetadataSupport=len(train) >= 3 and len(val) >= 3 and len({r['participant'] for r in val}) >= 2)
    return support


def main(args):
    acquisition = args.acquisition.resolve()
    acquisition.relative_to((ROOT.parent / 'hs-eval').resolve())
    source_protocol = json.loads((acquisition / 'protocol.json').read_text(encoding='utf-8'))
    verify(source_protocol)
    if source_protocol['purpose'] != 'phone-domain-train-val-original-acquisition-only':
        raise ValueError('Wrong phone acquisition protocol')
    if source_protocol['trainingAllowed'] is not True or source_protocol['predictionsRun'] is not False:
        raise ValueError('Phone acquisition is not in the pre-capture state')
    if source_protocol.get('testSourcesAllowed') or source_protocol.get('auditSourcesAllowed') or source_protocol.get('watchSourcesAllowed'):
        raise ValueError('Prohibited fitting scopes were enabled')

    identity = json.loads((acquisition / 'original-identity.json').read_text(encoding='utf-8'))
    if not identity.get('allMatch'):
        raise ValueError('Phone original identity checks failed')
    downloads = json.loads((acquisition / 'downloads.json').read_text(encoding='utf-8'))
    summary = json.loads((acquisition / 'summary.json').read_text(encoding='utf-8'))
    if summary['downloadFailures'] or summary['downloaded'] != summary['expected']:
        raise ValueError('Phone acquisition incomplete; refuse capture intake')

    open_set = json.loads((ROOT.parent / 'hs-eval/manual-open-set-dev-v2-20261108/protocol.json').read_text(encoding='utf-8'))
    rows = rows_from_acquisition(downloads)
    labels = sorted({r['label'] for r in rows})
    support = support_table(rows, labels)

    out = args.out.resolve()
    out.relative_to((ROOT.parent / 'hs-eval').resolve())
    if 'phone-domain' not in out.name:
        raise ValueError('Use a dedicated phone-domain intake folder outside the served repository')
    out.mkdir(exist_ok=False)
    sources_path = out / 'sources.json'
    sources_path.write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')

    names = [
        'scripts/prepare_phone_domain_feature_intake.py',
        'training/test_phone_domain_feature_intake.py',
        'scripts/acquire_phone_domain_trainval.py',
        'scripts/prepare_phone_domain_development.py',
        'training/test_phone_domain_development.py',
        'landmark-capture.js', 'holistic-worker-tracker.js', 'holistic-body-worker.js',
        'legacy-holistic-worker-context.js', 'body-hand-recovery.js', 'hand-recovery-worker.js',
        'landmark-frame-geometry.js', 'camera-performance.js', 'gesture-model.js', 'motion-model.js',
        'training/experimental/dual_capture.mjs', 'training/experimental/dual_hand_worker.js',
        'training/experimental/prepared_tracker_factory.mjs',
    ]
    frozen = dict(source_protocol['frozenFilesSha256'])
    frozen.update({str(ROOT / n): sha(ROOT / n) for n in names})
    for path in (
        acquisition / 'protocol.json',
        acquisition / 'downloads.json',
        acquisition / 'original-identity.json',
        acquisition / 'summary.json',
        ROOT.parent / 'hs-eval/manual-open-set-dev-v2-20261108/protocol.json',
        sources_path,
    ):
        frozen[str(path.resolve())] = sha(path)
    frozen.update({r['path']: r['sha256'] for r in rows})

    protocol = dict(
        frozenAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        purpose='phone-domain-train-val-feature-intake',
        frozenFilesSha256=frozen,
        sourceManifest=str(sources_path),
        acquisition=str(acquisition),
        manualModes=open_set['manualModes'],
        predeclaredAliases=open_set['predeclaredManualAliases'],
        counts=dict(collections.Counter(r['split'] for r in rows)),
        support=support,
        excludedBrowserSources=[],
        selection='Exact frozen phone-domain acquisition originals only; no outcome-based choice and no TEST/audit/Watch sources.',
        fitting='TRAIN measured production-equivalent detector features only; gate selection on separate VAL only. Independent guard-audit54 remains fitting-excluded.',
        source='Official PopSign v1 phone-camera TRAIN/VAL originals already acquired locally.',
        capture='Use the frozen production sampler with separately measured immutable Holistic/Tasks VIDEO streams; original rate, letterbox 960x720, maximum tracked side 640, no hand-output fusion.',
        storage='Temporary camera images stay in tab memory. Only derived TRAIN/VAL landmark features may be stored in this local external research directory; no served/public template redistribution.',
        license='PopSign v1 CC BY 4.0; public-use publisher dataset, originals only; derived landmarks stay local.',
        watchExcluded=True,
        officialTestExcluded=True,
        priorOnlineAuditsExcluded=True,
        priorBrowserCheckExcluded=True,
        guardAudit54FittingExcluded=True,
        priorBrowserOutcomesReadForSelection=False,
        predictionsRun=False,
        featuresCaptured=False,
        trainingAllowed=True,
        calibrationAllowed=True,
        productionDeploymentAllowed=False,
        independentAccuracy=False,
        followup='Freeze the shared landmark capture harness against this intake. Do not promote rejected hand-only candidates or retune from fitting-excluded audits.')
    (out / 'protocol.json').write_text(json.dumps(protocol, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(
        counts=protocol['counts'],
        labels=len(labels),
        metadataSupportPassed=sum(s['minimumMetadataSupport'] for s in support.values()),
        predictionsRun=False,
        featuresCaptured=False), indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--acquisition', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args())
