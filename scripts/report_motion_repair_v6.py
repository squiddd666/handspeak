"""Preserve three separate diagnostic trials; never select best-of outcomes."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import re

from scripts.report_motion_repair_v5 import counts
from scripts.summarize_motion_virtual_camera import assert_scalar_telemetry, normalized

ROOT = Path(__file__).resolve().parents[1]


def compare(reports):
    baseline = reports['baseline']['attempts']
    ids = {a['id'] for a in baseline}
    if len(baseline) != 28 or len(ids) != 28:
        raise ValueError('Expected 28 distinct baseline references')
    for report in reports.values():
        assert_scalar_telemetry(report)
        attempts = report['attempts']
        if len(attempts) != 28 or {a['id'] for a in attempts} != ids:
            raise ValueError('Expected all 28 diagnostic references, once in each trial')
        if any(report[field] != reports['baseline'][field] for field in
               ('activeModelSha256', 'activeAuxiliaryModelSha256', 'calibrationSha256')):
            raise ValueError('These trials must not change model weights or calibration')
        if report['isolation'].get('host') != '127.0.0.1' or any(report['isolation'][key] for key in ('realCameraCalls', 'microphoneCalls')):
            raise ValueError('Expected virtual camera only')
        for a in attempts:
            before = next(b for b in baseline if b['id'] == a['id'])
            if any(a[key] != before[key] for key in ('label', 'clipSha256', 'clip', 'family', 'vocabulary', 'rate', 'stage')):
                raise ValueError('Reference or route identity changed')
            if not a.get('finishedAt') or a['rate'] != 1 or a['stage'] != 'baseline 1×':
                raise ValueError('Unfinished or altered-speed trial')
            if a['correct'] != (bool(a.get('predicted')) and normalized(a['predicted']) == normalized(a['label'])):
                raise ValueError('Correctness must describe the actual output')
    transitions = {}
    for name, report in reports.items():
        if name == 'baseline':
            continue
        lookup = {a['id']: a for a in report['attempts']}
        transitions[name] = dict(
            recovered=[a['label'] for a in baseline if not a['correct'] and lookup[a['id']]['correct']],
            regressions=[a['label'] for a in baseline if a['correct'] and not lookup[a['id']]['correct']])
    return dict(trials={name:counts(report['attempts']) for name,report in reports.items()}, transitions=transitions)


def verify_retained_runtime(baseline, root=ROOT):
    hashes = dict(baseline['runtimeSha256'], **{'index.html': baseline['indexSha256']})
    if baseline.get('calibrationSha256'):
        hashes['models/motion-calibration.json'] = baseline['calibrationSha256']
    for name, digest in hashes.items():
        path = root / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Retained runtime differs: ' + name)
    return hashes


def main():
    root = ROOT/'reports/motion-repair-v6-20261107'
    paths = dict(baseline=root/'baseline-pilot-28.json', padding=root/'padding-pilot-28.json',
                 paddingParity=root/'padding-parity-pilot-28.json')
    reports = {key:json.loads(path.read_text(encoding='utf-8')) for key,path in paths.items()}
    result = compare(reports)
    retained = verify_retained_runtime(reports['baseline'])
    for name in ('app.js','landmark-capture.js','beginner-recognition.js','capstone-recognition.js','index.html'):
        if (ROOT / name).read_bytes() != (root / 'pre-padding' / name).read_bytes():
            raise ValueError('Experimental capture changes are still installed: ' + name)
    cfg = re.search(r'^window\.HANDSPEAK_VIRTUAL_FIXTURE = (.*);\s*$',
                    (ROOT / 'motion-virtual-camera-v6-baseline.html').read_text(encoding='utf-8'),re.M)
    if not cfg:
        raise ValueError('Missing baseline fixture')
    config = json.loads(cfg.group(1))
    candidates = {'beginner': [ROOT/'models/beginner-repaired-v2.pt',ROOT/'models/beginner-repaired-v1.pt',ROOT.parent/'hs-eval/models/beginner-need79-v1.pt'],
                  'capstone': [ROOT/'third_party/microsoft_asl_citizen/capstone100-repaired-v1.pt',ROOT/'third_party/microsoft_asl_citizen/capstone100-v4-ensemble.pt']}
    for family, paths_for_family in candidates.items():
        current = next(path for path in paths_for_family if path.exists())
        if hashlib.sha256(current.read_bytes()).hexdigest() != reports['baseline']['activeModelSha256'][family]:
            raise ValueError('Active model changed: ' + family)
    for name, digest in config['manualModelSha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest:
            raise ValueError('Manual model changed: ' + name)
    calibration = json.loads((ROOT/'models/motion-calibration.json').read_text(encoding='utf-8'))
    for family, digest in reports['baseline']['activeAuxiliaryModelSha256'].items():
        path = ROOT / calibration['models'][family]['auxiliary']['checkpoint']
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Auxiliary model changed: ' + family)
    result.update(modelChangesInstalled=False, paddingInstalled=False, checkpointingImplemented=True,
                  retainedRuntimeVerified=True, retainedRuntimeSha256=retained,
                  all198Retested=False, allWordsReliablyFixed=False, liveCameraAccuracyVerified=False,
                  evidenceSha256={key:hashlib.sha256(path.read_bytes()).hexdigest() for key,path in paths.items()},
                  scope='Separate diagnostic reference trials, not independent accuracy or a clean causal benchmark. '
                        'The first padding candidate changed unpadded warm-up resolution; the second restores that input. '
                        'Sampling rates differed between trials. Every wrong/no-match output is retained. No best-of aggregation.')
    parity_path = root/'body-runtime-validation-parity.json'
    if parity_path.exists():
        parity = json.loads(parity_path.read_text(encoding='utf-8'))
        assert_scalar_telemetry(parity)
        if parity['predictionMatches'] != parity['validationRecordings'] or parity['featureMaxAbsError'] > 1e-5:
            raise ValueError('Body runtime parity did not pass')
        result['bodyRuntimeMathParity'] = {key:parity[key] for key in
            ('validationRecordings','predictionMatches','featureMaxAbsError','distanceMaxAbsError','browserCaptureParityVerified')}
        result['bodyRuntimeMathParity']['evidenceSha256'] = hashlib.sha256(parity_path.read_bytes()).hexdigest()
    (root/'summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    lookups = {key:{a['id']:a for a in report['attempts']} for key,report in reports.items()}
    rows = []
    for a in reports['baseline']['attempts']:
        rows.append(dict(label=a['label'],route=a['family'],**{key:lookup[a['id']]['predicted'] or 'NO MATCH' for key,lookup in lookups.items()}))
    with (root/'word-results.csv').open('w',encoding='utf-8',newline='') as out:
        writer=csv.DictWriter(out,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    lines=['# Recognition diagnostics v6 — 2026-11-07','',
           'The padding candidates are **not installed**. The production capture code, model weights and calibration were restored to the retained pre-padding state. The v5 body-manual candidate also remains offline.', '',
           '## Separate 28-reference trials','', '| Trial | Matched | Incorrect | No match |', '|---|---:|---:|---:|']
    for name,c in result['trials'].items():
        lines.append(f'| {name} | {c["matched"]} | {c["incorrect"]} | {c["noMatch"]} |')
    lines += ['',result['scope'],'',
              '## Installed diagnostic repair','',
              'The opt-in fixture now saves scalar checkpoints after every completed attempt using scripts/serve_motion_audit.py. The audit server binds only to 127.0.0.1, uses a separate test database, validates frozen fixture/clip identities, rejects raw coordinate arrays and changed past outcomes, and preserves misses. Production server.py has no checkpoint endpoint. These are test outcomes, not user video/landmarks or personal samples.', '',
              '## Offline body-runtime math parity','',
              'The experimental JavaScript representation, anatomical mirror, banded distance, and frozen prediction gates are checked against Python without a camera. The candidate is not imported by production. Body and manual hand streams must remain separate; this check does not fix the known NO regression or verify browser capture parity.', '',
              '## Remaining work','',
              'All 198 words were not retested in v6. The previous v5 all-word report was lost before download after the browser session ended; no totals have been reconstructed from incomplete logs. The last saved full-198 v4 result remains separate (135 matched, 6 incorrect, 57 no match) and is not a v6 result.', '',
              'Padding alone does not resolve the native/browser sampling gap, sign variants, or model confusion. Do not lower gates or promote the v5 model using the reused held-out results. The next model iteration needs separate body + hand capture streams, validation-only training/route selection, a newly untouched signer/source-separated audit, and a full browser regression with durable reports.','',
              'All frontend tests passed for each candidate; relevant recognition/checkpoint Python tests passed. Full Python discovery did not pass: missing platform dependencies (MediaPipe in the PyTorch environment, Linux-only ffprobe path), Windows text encoding, and legacy motion/word fixture failures remain recorded in the external v6 test logs. No blanket all-tests-passed claim is made.']
    (root/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if 'bodyRuntimeMathParity' in result:
        with (root/'README.md').open('a',encoding='utf-8') as out:
            p=result['bodyRuntimeMathParity']
            out.write(f'\nFrozen JS/Python validation prediction agreement: {p["predictionMatches"]}/{p["validationRecordings"]}. '
                      f'Maximum feature absolute difference: {p["featureMaxAbsError"]:.3g}; distance difference: {p["distanceMaxAbsError"]:.3g}. '
                      'All validation outcomes, including rejected inputs, are preserved in body-runtime-validation-parity.json. This is implementation agreement, not recognition accuracy.\n')
    print(json.dumps(result['trials'],indent=2))


if __name__=='__main__':
    main()
