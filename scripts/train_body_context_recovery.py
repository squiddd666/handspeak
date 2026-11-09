"""Freeze then fit a body-context candidate from one or more measured TRAIN/VAL captures.

Rejected hand-only candidates and fitting-excluded guard-audit54 outcomes are never
read. Official TEST / Watch sources are never used. Protocol is frozen before any
feature outcomes are opened for fitting.
"""
from __future__ import annotations

import argparse
import collections
import datetime
import json
import subprocess
import time
from pathlib import Path

import numpy as np

from scripts.run_online_native_audit import ROOT, sha, verify
from scripts.train_native_manual_v4 import dtw_many, mirrored, metrics
from scripts.audit_body_manual_v5 import BASELINE_FILES, RUNTIME_FILES
from scripts.freeze_browser_domain_capture import ALLOWED_CAPTURE_PURPOSES
from scripts.train_browser_domain_recovery import select_guard, select_recovery


def load_capture_records(capture):
    capture = Path(capture)
    protocol = json.loads((capture / 'protocol.json').read_text(encoding='utf-8'))
    # Completed captures keep durable feature/integrity receipts. Later tooling
    # edits may change historical frozen digests; measured feature bytes are the
    # fitting surface and are rehashed below.
    if protocol['purpose'] not in ALLOWED_CAPTURE_PURPOSES:
        raise ValueError('Unsupported capture purpose: ' + protocol['purpose'])
    if not (capture / 'capture-summary.json').exists():
        raise ValueError('Capture incomplete: ' + str(capture))
    integrity = json.loads((capture / 'post-run-integrity.json').read_text(encoding='utf-8'))
    if not integrity['allFrozenFilesUnchanged'] or not integrity['allFeaturesUnchanged']:
        raise ValueError('Capture integrity failed: ' + str(capture))
    summary = json.loads((capture / 'capture-summary.json').read_text(encoding='utf-8'))
    if summary.get('predictionsRun'):
        raise ValueError('Capture ran predictions; refuse fitting')
    ledger = json.loads((capture / 'features' / 'checkpoint.json').read_text(encoding='utf-8'))
    expected = json.loads(Path(protocol['sourceManifest']).read_text(encoding='utf-8'))
    if len(ledger) != len(expected) or [r['id'] for r in ledger] != protocol['order']:
        raise ValueError('Incomplete capture ledger: ' + str(capture))
    features = {}
    records = []
    originals = {r['file']: r for r in json.loads(Path(protocol.get('originalSourceManifest', protocol['sourceManifest'])).read_text(encoding='utf-8'))}
    for row, source in zip(ledger, expected):
        path = Path(row['path'])
        if sha(path) != row['sha256']:
            raise ValueError('Feature changed: ' + row['file'])
        feature = json.loads(path.read_text(encoding='utf-8'))
        features[str(path)] = row['sha256']
        if feature['source'] != source or source['split'] not in ('train', 'val'):
            raise ValueError('Feature source mismatch or prohibited split')
        capture_payload = feature['capture']
        records.append(dict(
            source,
            contractPassed=capture_payload['contractPassed'],
            rawFrames=[s['manual'] for s in capture_payload['samples']] if capture_payload['contractPassed'] else [],
            imageAspect=.75,
            captureFolder=str(capture)))
    for row in protocol.get('inheritedFeatures', []):
        path = Path(row['path'])
        if sha(path) != row['sha256']:
            raise ValueError('Inherited measured feature changed')
        feature = json.loads(path.read_text(encoding='utf-8'))
        source = feature['source']
        if source != originals[source['file']]:
            raise ValueError('Inherited source mapping changed')
        features[str(path)] = row['sha256']
        capture_payload = feature['capture']
        records.append(dict(
            source,
            contractPassed=capture_payload['contractPassed'],
            rawFrames=[s['manual'] for s in capture_payload['samples']] if capture_payload['contractPassed'] else [],
            imageAspect=.75,
            captureFolder=str(capture)))
    for missing in protocol.get('inheritedFailedSources', []):
        source = missing['source']
        if source != originals[source['file']]:
            raise ValueError('Missing-source disposition changed')
        records.append(dict(
            source,
            contractPassed=False,
            rawFrames=[],
            imageAspect=.75,
            missingFeatureReason=missing['reason'],
            captureFolder=str(capture)))
    return protocol, records, features


def prepare(captures, out):
    out = out.resolve()
    out.relative_to((ROOT.parent / 'hs-eval').resolve())
    out.mkdir(exist_ok=False)
    capture_paths = [Path(c).resolve() for c in captures]
    if len({str(p) for p in capture_paths}) != len(capture_paths):
        raise ValueError('Duplicate capture folders')
    frozen = {}
    purposes = []
    modes = None
    for capture in capture_paths:
        protocol = json.loads((capture / 'protocol.json').read_text(encoding='utf-8'))
        if protocol['purpose'] not in ALLOWED_CAPTURE_PURPOSES:
            raise ValueError('Unsupported capture purpose')
        if protocol.get('auditInputsAllowed'):
            raise ValueError('Audit inputs are not allowed for body-context fitting')
        if not (capture / 'capture-summary.json').exists():
            raise ValueError('Capture incomplete; freeze training only after measured features exist')
        integrity = json.loads((capture / 'post-run-integrity.json').read_text(encoding='utf-8'))
        if not integrity['allFrozenFilesUnchanged'] or not integrity['allFeaturesUnchanged']:
            raise ValueError('Capture integrity failed before training freeze')
        purposes.append(protocol['purpose'])
        if modes is None:
            modes = protocol['manualModes']
        elif modes != protocol['manualModes']:
            raise ValueError('manualModes differ across captures')
        frozen[str(capture / 'protocol.json')] = sha(capture / 'protocol.json')
        frozen[str(capture / 'capture-summary.json')] = sha(capture / 'capture-summary.json')
        frozen[str(capture / 'post-run-integrity.json')] = sha(capture / 'post-run-integrity.json')
        frozen[str(capture / 'features' / 'checkpoint.json')] = sha(capture / 'features' / 'checkpoint.json')

    names = [
        'scripts/train_body_context_recovery.py',
        'training/test_body_context_recovery.py',
        'scripts/train_browser_domain_recovery.py',
        'training/experimental/browser_domain_recovery.mjs',
        'training/experimental/online_manual_runtime.mjs',
        'training/ux/run_manual_guard_baseline.mjs',
        'scripts/train_native_manual_v4.py',
        'scripts/audit_body_manual_v5.py',
        'scripts/run_online_native_audit.py',
        'scripts/prepare_native_repair_v4.py',
        'scripts/train_body_manual_v5.py',
        'scripts/prepare_targeted_data_v4.py',
    ] + list(BASELINE_FILES.values()) + RUNTIME_FILES
    frozen.update({str(ROOT / n): sha(ROOT / n) for n in names})
    plan = dict(
        purpose='measured-body-context-train-val-recovery-development-only',
        frozenAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        captures=[str(p) for p in capture_paths],
        capturePurposes=purposes,
        frozenFilesSha256=frozen,
        manualModes=modes,
        prototypeSelection='All up to four measured usable TRAIN samples per label across allowed captures, rounded to six decimals; sparse classes remain in competition.',
        distanceLimits=[.2, .3, .4, .5, .65, .8, 1., 1.5, 2., 3., 5., 10.],
        ratios=[0., .5, .75, 1., 1.05, 1.1, 1.2, 1.3, 1.5, 2., 3., 5.],
        votes=[1, 2, 3],
        guardSelection='Per predicted label only. At least three retained correct VAL recordings and two VAL signers; retain EVERY correct baseline source. No sparse-class global fallback; require at least one fewer wrong/unsupported accept.',
        recoverySelection='Only after baseline/guard rejection. Nearest overall TRAIN label competes with all observed labels. At least three correct VAL recoveries / two signers and zero new wrong/unsupported VAL accepts per enabled class.',
        tieBreak='Most recovered correct or fewest false accepts, then smallest distance, greatest ratio and greatest votes.',
        requirements='Entire mode must retain every baseline correct recording and never increase wrong/unsupported accepts; otherwise fail training, do not install.',
        failedCapturePolicy='Failed captures are retained as no-match outcomes but never references or gate support; no imputed landmarks.',
        excludedFitting='Rejected browser-domain and manual-recovery candidates stay out of production. Guard-audit54 remains permanently fitting-excluded.',
        trainSplit='train',
        selectionSplit='val',
        testRead=False,
        auditOutcomesRead=False,
        watchReadForFitting=False,
        independentAccuracy=False,
        productionDeploymentAllowed=False)
    (out / 'protocol.json').write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
    print('Frozen body-context training protocol before feature outcomes were read.', flush=True)


def fit(folder):
    folder = Path(folder)
    protocol = json.loads((folder / 'protocol.json').read_text(encoding='utf-8'))
    verify(protocol)
    if protocol['purpose'] != 'measured-body-context-train-val-recovery-development-only':
        raise ValueError('Wrong body-context training protocol')
    if (folder / 'training-started.json').exists():
        raise FileExistsError('Training already started; no outcome-driven reruns')
    started = time.perf_counter()
    records = []
    features = {}
    capture_protocols = []
    for capture in protocol['captures']:
        capture_protocol, capture_records, capture_features = load_capture_records(capture)
        capture_protocols.append(capture_protocol)
        records.extend(capture_records)
        features.update(capture_features)
    if len({r['file'] for r in records}) != len(records):
        raise ValueError('Cross-capture source duplication')
    (folder / 'training-started.json').write_text(json.dumps(dict(
        protocolSha256=sha(folder / 'protocol.json'),
        captureCount=len(protocol['captures']),
        recordCount=len(records))) + '\n', encoding='utf-8')
    data = dict(
        models={k: json.loads((ROOT / n).read_text(encoding='utf-8')) for k, n in BASELINE_FILES.items()},
        cases=[dict(rawFrames=r['rawFrames'], imageAspect=r['imageAspect']) for r in records])
    run = subprocess.run(
        ['C:/Program Files/nodejs/node.exe', str(ROOT / 'training/ux/run_manual_guard_baseline.mjs')],
        input=json.dumps(data), capture_output=True, text=True, check=True)
    cases = json.loads(run.stdout)
    if len(cases) != len(records):
        raise ValueError('Actual baseline case count changed')
    for row, case in zip(records, cases):
        row['sequence'] = case['sequence']
        row['baseline'] = case['baseline']
    train = [r for r in records if r['split'] == 'train' and r['sequence'] is not None and r['contractPassed']]
    val = [r for r in records if r['split'] == 'val']
    if {r['participant'] for r in train} & {r['participant'] for r in val}:
        raise ValueError('Signer leakage')
    groups = collections.defaultdict(list)
    for row in train:
        groups[row['label']].append(row)
    refs = [
        dict(label=label, sequence=np.round(row['sequence'], 6).tolist(), file=row['file'], participant=row['participant'])
        for label in sorted(groups) for row in groups[label][:4]]
    if len(refs) > 1024 or len(groups) < 2:
        raise ValueError('Wrong training bank size')
    sequences = np.asarray([r['sequence'] for r in refs])
    labels = np.asarray([r['label'] for r in refs])
    statistics = []
    for i, row in enumerate(val):
        if row['sequence'] is None:
            statistics.append(None)
            continue
        array = np.asarray(row['sequence'])
        distances = np.minimum(dtw_many(array, sequences), dtw_many(mirrored(array), sequences))
        ranking = np.argsort(distances, kind='stable')
        label = str(labels[ranking[0]])
        distance = float(distances[ranking[0]])
        other = float(distances[next(j for j in ranking if labels[j] != label)])
        statistics.append(dict(
            byLabel={str(name): float(distances[labels == name].min()) for name in sorted(set(labels))},
            label=label,
            distance=distance,
            ratio=other / (distance + 1e-6),
            votes=int((labels[ranking[:3]] == label).sum())))
        if i % 50 == 0:
            print('Measured VAL statistics', i + 1, '/', len(val), flush=True)
    candidate = dict(
        version=1,
        featureVersion='body-context-recovery-v1',
        samples=[dict(label=r['label'], sequence=r['sequence']) for r in refs],
        modes={})
    outputs = {}
    guard_outputs = {}
    comparison = {}
    selection = {}
    for mode, mode_labels in protocol['manualModes'].items():
        before = [r['baseline'][mode] for r in val]
        guarded = list(before)
        guard_policies = {}
        recovery_policies = {}
        selection[mode] = {}
        for label in mode_labels:
            chosen = select_guard(val, before, statistics, label, protocol['distanceLimits'], protocol['ratios'])
            if chosen:
                _, gate, accepted = chosen
                guard_policies[label] = gate
                for i, prediction in enumerate(before):
                    if prediction == label and i not in accepted:
                        guarded[i] = None
        current = list(guarded)
        for label in mode_labels:
            chosen = select_recovery(val, guarded, statistics, label, protocol['distanceLimits'], protocol['ratios'], protocol['votes'])
            if chosen:
                _, gate, ids = chosen
                recovery_policies[label] = gate
                for i in ids:
                    current[i] = label
                selection[mode][label] = dict(
                    correctSources=[val[i]['file'] for i in ids],
                    signers=sorted({val[i]['participant'] for i in ids}))
        if any(row['label'] == before_label and before_label is not None and before_label != after
               for row, before_label, after in zip(val, before, current)):
            raise ValueError('Correct baseline recording lost')
        old = metrics(val, before, mode_labels)
        new = metrics(val, current, mode_labels)
        if new['wrong'] > old['wrong'] or new['negativeFalse'] > old['negativeFalse']:
            raise ValueError('New validation false accept')
        candidate['modes'][mode] = dict(labels=mode_labels, guardPolicies=guard_policies, recoveryPolicies=recovery_policies)
        comparison[mode] = dict(
            baseline=old,
            candidate=new,
            guarded=metrics(val, guarded, mode_labels),
            guardClasses=list(guard_policies),
            recoveryClasses=list(recovery_policies))
        outputs[mode] = current
        guard_outputs[mode] = guarded
        print(mode, json.dumps(comparison[mode]), flush=True)
    (folder / 'candidate.json').write_text(json.dumps(candidate, separators=(',', ':')), encoding='utf-8')
    module = (ROOT / 'training/experimental/browser_domain_recovery.mjs').as_uri()
    code = (
        'import {predictBrowserDomainRecovery} from ' + json.dumps(module) +
        ";let t='';for await(const c of process.stdin)t+=c;const i=JSON.parse(t);"
        "process.stdout.write(JSON.stringify(i.cases.map(c=>predictBrowserDomainRecovery(i.model,c.sequence,c.baseline))));")
    run = subprocess.run(
        ['C:/Program Files/nodejs/node.exe', '--input-type=module', '-e', code],
        input=json.dumps(dict(model=candidate, cases=[dict(sequence=r['sequence'], baseline=r['baseline']) for r in val])),
        capture_output=True, text=True, check=True)
    actual = json.loads(run.stdout)
    max_error = 0.
    for i, (row, result, stats) in enumerate(zip(val, actual, statistics)):
        if result['predictions'] != {mode: outputs[mode][i] for mode in outputs} or result['guarded'] != {mode: guard_outputs[mode][i] for mode in outputs}:
            raise ValueError('Python/JS prediction parity failed')
        if stats:
            if result['statistics']['label'] != stats['label'] or result['statistics']['votes'] != stats['votes']:
                raise ValueError('Python/JS rank parity failed')
            max_error = max(
                max_error,
                abs(stats['distance'] - result['statistics']['distance']),
                abs(stats['ratio'] - result['statistics']['ratio']))
    verify(protocol)
    verify({'frozenFilesSha256': features})
    report = dict(
        candidateSha256=sha(folder / 'candidate.json'),
        comparison=comparison,
        selection=selection,
        captures=protocol['captures'],
        capturePurposes=[p['purpose'] for p in capture_protocols],
        trainSources=len(train),
        references=len(refs),
        trainCounts=dict(collections.Counter(r['label'] for r in train)),
        validationSources=len(val),
        failedValidationCaptures=sum(not r['contractPassed'] for r in val),
        featureFilesSha256=features,
        parity=dict(cases=len(val), modeOutcomes=len(val) * 4, predictionsIdentical=True, maxDistanceOrRatioError=max_error),
        records=[dict(file=r['file'], label=r['label'], baseline=r['baseline'], candidate={mode: outputs[mode][i] for mode in outputs}) for i, r in enumerate(val)],
        selectionSetOnly=True,
        independentAccuracy=False,
        deployed=False,
        productionFilesUnchanged=True,
        guardAudit54FittingExcluded=True,
        rejectedCandidatesNotInstalled=True,
        next='Do not promote. Freeze a genuinely different untouched audit before any later promotion decision.',
        seconds=round(time.perf_counter() - started, 3))
    (folder / 'validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('Measured body-context candidate frozen, NOT deployed.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--captures', nargs='+', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--fit', type=Path)
    args = parser.parse_args()
    if args.fit:
        fit(args.fit.resolve())
    elif args.captures and args.out:
        prepare(args.captures, args.out.resolve())
    else:
        parser.error('Use --captures/--out to freeze before outcomes, then --fit after capture completion')
