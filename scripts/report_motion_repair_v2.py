"""Summarize the v2 frozen release, without dropping failures or tuning on tests."""
from __future__ import annotations
import json
import hashlib
import csv
from pathlib import Path
from report_motion_repair import baseline_attempts, counts
from summarize_motion_virtual_camera import summarize

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/motion-repair-v2-20261107'


def report():
    raw = REPORT / 'virtual-final/final-all-198.json'
    summarize(raw)
    summary = json.loads((raw.parent / 'summary.json').read_text(encoding='utf-8'))
    previous = json.loads((ROOT / 'reports/motion-repair-20261107/virtual-final/final-all-198.json').read_text(encoding='utf-8'))
    current = json.loads(raw.read_text(encoding='utf-8'))
    old = baseline_attempts(previous)
    new = baseline_attempts(current)
    takes = list(new.values())
    before, after = counts(old), counts(new)
    config = json.loads((ROOT / 'models/motion-calibration.json').read_text(encoding='utf-8'))
    if current['calibrationSha256'] != hashlib.sha256((ROOT / 'models/motion-calibration.json').read_bytes()).hexdigest():
        raise ValueError('Calibration identity changed')
    for name, identity in current['runtimeSha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != identity:
            raise ValueError(f'Runtime file changed during verification: {name}')
    for t in takes:
        response = t.get('response') or {}
        if response.get('checkpointSha256'):
            if response['checkpointSha256'] != config['models'][t['family']]['checkpointSha256'] or response.get('calibrationId') != config['calibrationId']:
                raise ValueError('A stale model or calibration was tested')
    transitions = [{'label': t['label'], 'before': 'matched' if old[t['id']]['correct'] else 'wrong' if old[t['id']].get('predicted') else 'no match',
                    'after': 'matched' if t['correct'] else 'wrong' if t.get('predicted') else 'no match', 'prediction': t.get('predicted')}
                   for t in takes]
    remaining = [w for w in summary['words'] if w['outcome'] != 'matched']
    independent = []
    for family in ('beginner', 'capstone'):
        prior = json.loads((ROOT / f'reports/motion-repair-20261107/heldout-{family}.json').read_text(encoding='utf-8'))
        selected = json.loads((REPORT / f'heldout-{family}.json').read_text(encoding='utf-8'))
        for mode in selected['selected']['modes']:
            b = prior['selected']['modes'][mode]['accepted'];a = selected['selected']['modes'][mode]['accepted']
            if a['attempts'] != b['attempts'] or a['negativeAttempts'] != b['negativeAttempts']:
                raise ValueError('Independent before/after denominators differ')
            independent.append({'family': family, 'mode': mode, 'before': {k:b[k] for k in ('attempts','correct','wrong','noMatch','negativeAttempts','negativeFalse')},
                                'after': {k:a[k] for k in ('attempts','correct','wrong','noMatch','negativeAttempts','negativeFalse')}})
    result = {'before': before, 'after': after, 'calibrationId': config['calibrationId'],
              'scope': summary['scope'], 'independentAudits': independent, 'transitions': transitions,
              'remainingFailures': remaining, 'allWordsReliablyFixed': False,
              'appUrl': 'http://127.0.0.1:8002/#learn'}
    (REPORT / 'repair-summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (REPORT / 'remaining-reference-failures.json').write_text(json.dumps(remaining,indent=2)+'\n',encoding='utf-8')
    with (REPORT / 'remaining-reference-failures.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['label','modelRoute','prediction','outcome','rejectionReason','trackedFrames','status'],extrasaction='ignore')
        writer.writeheader();writer.writerows(remaining)
    lines = ['# Second motion-recognition repair and all-word verification', '',
             '## Implemented', '',
             '* Retrained the complete Beginner-79 checkpoint for 10 epochs with training-only aspect-ratio augmentation; selected using validation macro accuracy.',
             '* Added predicted-class rejection gates only with at least three correct validation examples. Sparse classes retain the global policy. Each class keeps its global validation error/unsupported-sign budget.',
             '* Retained the full-100 ensemble and applied validation-only recalibration; no test/practice target can select a label.',
             '* Added same-frozen-frame full-image/pose-wrist crop hand recovery in a separate classic worker, isolated from Holistic WASM globals. Resting second hands do not trigger unnecessary recovery.',
             '* Increased bounded real-frame sampling; cancellation releases snapshots/bitmaps and asynchronous recovery cannot enter another recording.',
             '* Preserved previous weights, source/evidence, and archived accuracy counts. Published actual current counts, including zero-accuracy classes and tracking failures.', '',
             '## All 198 reference checks', '',
             f"* Previous release: **{before['matched']} matched / {before['wrong']} wrong / {before['noMatch']} no match**.",
             f"* This release: **{after['matched']} matched / {after['wrong']} wrong / {after['noMatch']} no match**.",
             f"* Complete reference playback: {summary['completeClipPlayback']}/198. Insufficient-tracking misses: {summary['insufficientTrackingMisses']}.",
             '* Exactly one normal-speed primary-reference attempt per word through Watch → Practice → Record. No forced expected label, no adding reviewed text, no physical camera/microphone calls.',
             '* These are previously seen reference-video regression results, **not independent or live-user accuracy**.', '',
             '## Frozen independent extracted-recording audit', '',
             '| Model / mode | Attempts | Prior correct / wrong / no match | Current correct / wrong / no match | Unsupported false accepts: prior → current |',
             '|---|---:|---|---|---|']
    for row in independent:
        b,a=row['before'],row['after']
        lines.append(f"| {row['family']} / {row['mode']} | {a['attempts']} | {b['correct']} / {b['wrong']} / {b['noMatch']} | {a['correct']} / {a['wrong']} / {a['noMatch']} | {b['negativeFalse']} → {a['negativeFalse']} / {a['negativeAttempts']} |")
    lines += ['', '**Mixed generalization:** validation improved, but the independent audit does not improve every metric. Beginner/full accept slightly more correct words but also more wrong words. Core/extended reject substantially more unsupported signs at the cost of some correct matches. Do not present this as all words being fixed or a universal accuracy improvement.', '',
              '## Remaining incorrect and no-match words', '', '| Word | Route | Actual output | Outcome | Reason |', '|---|---|---|---|---|']
    for w in remaining:lines.append(f"| {w['label']} | {w['modelRoute']} | {w['prediction'] or '—'} | {w['outcome']} | {w['rejectionReason'] or w['status']} |")
    lines += ['', '## Evidence and limitations', '',
              '* `selection.json`, training history, validation archives, and calibration audits freeze selection before independent evaluation.',
              '* `virtual-final/final-all-198.json`, `virtual-final/summary.json`, and `repair-summary.json` retain every result and before/after transition.',
              '* `heldout-*.json` excludes primary Watch references and checks disjoint source/signers. Synthetic GOOD greetings are not natural continuous phrase recordings.',
              '* Tests: 175 frontend checks passed (2 platform skips), plus 48 targeted Python recognition/report checks. The broader Python suite is not all-passing: after installing the missing QuickJS dependency, it ran 126 tests with 8 failures and 3 errors in legacy/dependency/platform paths. See `test-scope.json` and `python-all-tests-with-dependencies.txt`; these were not hidden or described as passed.',
              '* Remaining failures require diverse independent recordings and better tracking/model features. Lowering thresholds until a reference passes would inflate wrong predictions.',
              '* Updated local runtime: http://127.0.0.1:8002/#learn. Port 8001 had a stale in-memory Beginner checkpoint; it was not counted as v2 verification.',
              '* No public deployment, external biometric upload, or user history modification was performed. Research references remain localhost-only.']
    (REPORT / 'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return {'before':before,'after':after,'remaining':len(remaining)}


if __name__ == '__main__':print(json.dumps(report(),indent=2))
