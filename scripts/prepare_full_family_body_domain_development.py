"""Freeze full-family Citizen TRAIN/VAL capture intake, deduped against prior domain captures.

Uses the already-frozen full-family metadata census only. Official TEST, Watch,
and independent audit originals stay excluded. Previously attempted browser-domain
source dispositions are never silently recaptured.
"""
from __future__ import annotations

import argparse
import collections
import datetime
import json
from pathlib import Path

from scripts.run_online_native_audit import ROOT, sha, verify
from scripts.prepare_targeted_data_v4 import MANUAL


def gloss_to_label(gloss, beginner_map):
    for label, glosses in MANUAL.items():
        if gloss in glosses:
            return label
    for label, glosses in beginner_map.items():
        if gloss in glosses:
            return label
    return gloss


def prior_dispositions(capture_roots):
    """Collect every previously attempted Citizen original disposition.

    Old capture protocols may include tooling digests that later changed. Source
    identity is taken from the durable manifests/ledgers themselves; measured
    feature files are rehashed when present so silent substitution is refused.
    """
    files = {}
    failed = []
    for root in capture_roots:
        root = root.resolve()
        protocol_path = root / 'protocol.json'
        if not protocol_path.exists():
            continue
        protocol = json.loads(protocol_path.read_text(encoding='utf-8'))
        original = Path(protocol.get('originalSourceManifest', protocol['sourceManifest']))
        sources = json.loads(original.read_text(encoding='utf-8'))
        for source in sources:
            files[source['file']] = source
        for row in protocol.get('inheritedFeatures', []):
            path = Path(row['path'])
            if sha(path) != row['sha256']:
                raise ValueError('Prior measured feature changed: ' + row['file'])
            files.setdefault(row['file'], dict(file=row['file'], split=row['split'], participant=row['participant'], label=row.get('label')))
        for missing in protocol.get('inheritedFailedSources', []):
            source = missing['source']
            files[source['file']] = source
            failed.append(dict(source=source, reason=missing['reason'], capture=str(root)))
        disposition_path = root / 'failure-disposition.json'
        if disposition_path.exists():
            disposition = json.loads(disposition_path.read_text(encoding='utf-8'))
            source = disposition['missingFeatureSource']
            files[source['file']] = source
            failed.append(dict(source=source, reason=disposition['reason'], capture=str(root)))
        checkpoint = root / 'features' / 'checkpoint.json'
        if checkpoint.exists():
            for row in json.loads(checkpoint.read_text(encoding='utf-8')):
                path = Path(row['path'])
                if sha(path) != row['sha256']:
                    raise ValueError('Prior measured feature changed: ' + row['file'])
                files.setdefault(row['file'], dict(file=row['file'], split=row['split'], participant=row['participant'], label=row.get('label')))
    return files, failed


def main(args):
    census_dir = args.census.resolve()
    census = json.loads((census_dir / 'support.json').read_text(encoding='utf-8'))
    if census.get('purpose') != 'full-family-source-support-metadata-census':
        raise ValueError('Wrong full-family census')
    if 'frozenFilesSha256' not in census:
        raise ValueError('Census missing frozen file digests')
    verify(census)
    if census.get('testFeaturesRead') or census.get('auditOutcomesRead') or census.get('predictionsRun'):
        raise ValueError('Census was contaminated by prohibited outcomes')
    selected = census['selectedCachedTrainVal']
    if len(selected) != 1448:
        raise ValueError('Unexpected census selection size')

    capture_roots = [Path(p) for p in args.prior_captures]
    prior_files, prior_failed = prior_dispositions(capture_roots)
    if len(prior_files) < 294:
        raise ValueError('Expected at least the completed 294 browser-domain dispositions')

    open_set = json.loads((ROOT.parent / 'hs-eval/manual-open-set-dev-v2-20261108/protocol.json').read_text(encoding='utf-8'))
    beginner = json.loads((ROOT / 'models/beginner-100-label-map.json').read_text(encoding='utf-8'))
    beginner_map = {r['label']: r['citizenGlosses'] for r in beginner['entries']}
    beginner_map['MORNING'] = ['MORNING']

    remaining = []
    for row in selected:
        if row['split'] not in ('train', 'val'):
            raise ValueError('Census leaked a non TRAIN/VAL source')
        if row['file'] in prior_files:
            continue
        path = Path(row['path'])
        digest = sha(path)
        if digest != row['sha256']:
            raise ValueError('Census original drifted: ' + row['file'])
        if digest in set(census.get('excludedOriginalHashes', [])):
            raise ValueError('Excluded hash slipped into remaining capture plan')
        label = gloss_to_label(row['gloss'], beginner_map)
        remaining.append(dict(
            file=row['file'],
            path=str(path.resolve()),
            sha256=digest,
            split=row['split'],
            participant=row['participant'],
            gloss=row['gloss'],
            label=label,
            domain='asl-citizen'))

    if {r['participant'] for r in remaining if r['split'] == 'train'} & {r['participant'] for r in remaining if r['split'] == 'val'}:
        raise ValueError('Remaining full-family TRAIN/VAL signer overlap')
    if len({r['file'] for r in remaining}) != len(remaining):
        raise ValueError('Duplicate remaining originals')

    labels = sorted({r['label'] for r in remaining} | set().union(*map(set, open_set['manualModes'].values())))
    support = {}
    for label in labels:
        train = [r for r in remaining if r['split'] == 'train' and r['label'] == label]
        val = [r for r in remaining if r['split'] == 'val' and r['label'] == label]
        support[label] = dict(
            train=len(train),
            val=len(val),
            valSigners=len({r['participant'] for r in val}),
            minimumMetadataSupport=len(train) >= 3 and len(val) >= 3 and len({r['participant'] for r in val}) >= 2)

    out = args.out.resolve()
    out.relative_to((ROOT.parent / 'hs-eval').resolve())
    if 'body-domain' not in out.name and 'full-family' not in out.name:
        raise ValueError('Use a dedicated full-family/body-domain folder outside the served repository')
    out.mkdir(exist_ok=False)
    sources_path = out / 'sources.json'
    sources_path.write_text(json.dumps(remaining, indent=2) + '\n', encoding='utf-8')
    disposition_path = out / 'prior-capture-disposition.json'
    disposition_path.write_text(json.dumps(dict(
        priorSourceFiles=sorted(prior_files),
        priorSourceCount=len(prior_files),
        priorFailedCaptures=prior_failed,
        dedupeRule='Exact original filename identity against completed/failed browser-domain dispositions; codec failures stay explicit and are not retried.',
        predictionsRun=False), indent=2) + '\n', encoding='utf-8')

    names = [
        'scripts/prepare_full_family_body_domain_development.py',
        'training/test_full_family_body_domain_development.py',
        'scripts/inventory_full_recognition_support.py',
        'training/test_full_recognition_support.py',
        'models/beginner-100-label-map.json',
        'landmark-capture.js', 'holistic-worker-tracker.js', 'holistic-body-worker.js',
        'legacy-holistic-worker-context.js', 'body-hand-recovery.js', 'hand-recovery-worker.js',
        'landmark-frame-geometry.js', 'camera-performance.js', 'gesture-model.js', 'motion-model.js',
        'training/experimental/dual_capture.mjs', 'training/experimental/dual_hand_worker.js',
        'training/experimental/prepared_tracker_factory.mjs',
    ]
    frozen = dict(census['frozenFilesSha256'])
    frozen.update({str(ROOT / n): sha(ROOT / n) for n in names})
    for path in (
        census_dir / 'support.json',
        census_dir / 'summary.json',
        ROOT.parent / 'hs-eval/manual-open-set-dev-v2-20261108/protocol.json',
        sources_path,
        disposition_path,
    ):
        frozen[str(path.resolve())] = sha(path)
    for root in capture_roots:
        for name in ('protocol.json', 'failure-disposition.json', 'features/checkpoint.json', 'capture-summary.json'):
            path = root / name
            if path.exists():
                frozen[str(path.resolve())] = sha(path)
    frozen.update({r['path']: r['sha256'] for r in remaining})

    protocol = dict(
        frozenAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        purpose='full-family-body-domain-train-val-development',
        frozenFilesSha256=frozen,
        sourceManifest=str(sources_path),
        priorCaptureDisposition=str(disposition_path),
        census=str(census_dir / 'support.json'),
        manualModes=open_set['manualModes'],
        predeclaredAliases=open_set['predeclaredManualAliases'],
        counts=dict(collections.Counter(r['split'] for r in remaining)),
        support=support,
        excludedBrowserSources=sorted(prior_files),
        selection='Frozen full-family census TRAIN/VAL originals minus exact prior browser-domain dispositions; metadata only.',
        fitting='TRAIN measured production-equivalent body/manual features only; VAL gate selection only. Guard-audit54 and rejected candidates remain fitting-excluded.',
        source='Previously cached official ASL Citizen TRAIN/VAL originals from the full-family census, not new recordings or new signers.',
        capture='Use the frozen production sampler with separately measured immutable Holistic/Tasks VIDEO streams; original rate, letterbox 960x720, maximum tracked side 640, no hand-output fusion.',
        storage='Temporary camera images stay in tab memory. Only derived TRAIN/VAL landmark features may be stored in this local external research directory; no served/public template redistribution.',
        license='ASL Citizen noncommercial research terms; originals and derived candidate stay local, no source-video redistribution',
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
        followup='Freeze the shared landmark capture harness. Keep codec failures explicit. Include phone-domain measured TRAIN/VAL later without loosening rejected candidate thresholds.')
    (out / 'protocol.json').write_text(json.dumps(protocol, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(
        remainingSources=len(remaining),
        counts=protocol['counts'],
        priorDispositions=len(prior_files),
        priorFailedCaptures=len(prior_failed),
        labels=len(support),
        metadataSupportPassed=sum(s['minimumMetadataSupport'] for s in support.values()),
        predictionsRun=False,
        featuresCaptured=False), indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--census', type=Path, required=True)
    parser.add_argument('--prior-captures', nargs='+', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args())
