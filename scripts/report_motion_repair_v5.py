"""Preserve every v5 result and distinguish fixes from experimental candidates."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re

try:
    from .report_motion_repair_v4 import diagnose, outcome
    from .summarize_motion_virtual_camera import normalized, assert_scalar_telemetry
except ImportError:
    from report_motion_repair_v4 import diagnose, outcome
    from summarize_motion_virtual_camera import normalized, assert_scalar_telemetry

REPO=Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def counts(attempts):
    # Use the returned label, not a runner's cached correctness flag.
    matched=sum(bool(a.get('predicted')) and normalized(a['predicted'])==normalized(a['label']) for a in attempts)
    wrong=sum(bool(a.get('predicted')) and normalized(a['predicted'])!=normalized(a['label']) for a in attempts)
    return dict(attempts=len(attempts),matched=matched,incorrect=wrong,noMatch=len(attempts)-matched-wrong)


def report(args):
    root=args.root
    current=read(args.current)
    assert_scalar_telemetry(current)
    manifest=read(REPO/'models/recognition-videos.json')['items']
    attempts=current['attempts']
    if (len(attempts)!=198 or len({a['id'] for a in attempts})!=198 or
        {a['id'] for a in attempts}!={a['id'] for a in manifest}):
        raise ValueError('Every label needs exactly one result; no best-of selection')
    if any(not a.get('finishedAt') or a['rate']!=1 or a['stage']!='baseline 1×' for a in attempts):
        raise ValueError('An attempt is incomplete or not normal-speed')
    if any(current['isolation'].get(key,0) for key in ['realCameraCalls','microphoneCalls']):
        raise ValueError('Expected virtual-only reference check')
    cfg_match=re.search(r'^window\.HANDSPEAK_VIRTUAL_FIXTURE = (.*);\s*$',args.fixture.read_text(encoding='utf-8'),re.M)
    if not cfg_match: raise ValueError('Missing frozen fixture configuration')
    cfg=json.loads(cfg_match.group(1))
    for field in ['runtimeSha256','activeModelSha256','activeAuxiliaryModelSha256','calibrationSha256']:
        if current[field]!=cfg[field]: raise ValueError('Fixture/report integrity differs: '+field)
    if any(sha(REPO/name)!=digest for name,digest in cfg['runtimeSha256'].items()):
        raise ValueError('Runtime changed during reference audit')
    if any(sha(REPO/name)!=digest for name,digest in cfg['manualModelSha256'].items()):
        raise ValueError('Manual model changed during reference audit')
    previous=read(args.previous)['attempts'];before={a['id']:a for a in previous}
    transitions=[]
    for a in attempts:
        if a['correct'] != (bool(a.get('predicted')) and normalized(a['predicted'])==normalized(a['label'])):
            raise ValueError('Runner correctness differs from actual output')
        transitions.append(dict(id=a['id'],label=a['label'],route=a['family'],before=outcome(before[a['id']]),
                                after=outcome(a),prediction=a.get('predicted'),diagnosis=diagnose(a)))
    candidate=read(root/'body-manual-heldout.json') if (root/'body-manual-heldout.json').exists() else None
    summary=dict(current=counts(attempts),previous=counts(previous),sourceSha256=sha(args.current),fixtureSha256=sha(args.fixture),
                 manualModelSha256=cfg['manualModelSha256'],runtimeSha256=cfg['runtimeSha256'],
                 recovered=[t for t in transitions if t['before']!='matched' and t['after']=='matched'],
                 regressions=[t for t in transitions if t['before']=='matched' and t['after']!='matched'],
                 remaining=[t for t in transitions if t['after']!='matched'],
                 completePlayback=sum(bool(a.get('completeSourcePlayed')) for a in attempts),
                 modelChangesInstalled=False,processingConsentPreserved=True,
                 candidate=dict(deployed=False,eligibleModes=candidate['eligibleModes'],metrics=candidate['candidate']) if candidate else None,
                 scope='Reference regression, not live-user accuracy. Every attempt retained. v4 used two source-runner protocols; v5 restarts the virtual stream for every reference. No best-of retry aggregation or Watch fitting.')
    root.mkdir(parents=True,exist_ok=True)
    (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    with (root/'word-results.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(transitions[0]));writer.writeheader();writer.writerows(transitions)
    c,p=summary['current'],summary['previous']
    lines=['# Recognition repair v5 — 2026-11-07','',
           '## Installed capture/routing repairs','',
           '* Recover a visible missing second hand without replacing the actual primary hand or inventing absent hands.',
           '* Reset the temporal body-tracking graph between takes, after any canceled send has finished.',
           '* Practice now selects the word’s public default/expanded vocabulary explicitly. An earlier extra-word exercise cannot silently leave DRINK/LIKE competing in default practice.',
           '* Model weights and acceptance calibration remain v3. No expected word is substituted into a prediction. Processing consent and user messages are unchanged.','',
           '## All 198 normal-speed virtual-camera references','',
           f'* Current: **{c["matched"]} matched / {c["incorrect"]} incorrect / {c["noMatch"]} no match**.',
           f'* Previous v4: {p["matched"]} matched / {p["incorrect"]} incorrect / {p["noMatch"]} no match.',
           f'* Recovered matches: {len(summary["recovered"])}; previous-match regressions: {len(summary["regressions"])}.',
           f'* Complete source playback: {summary["completePlayback"]}/198. Physical camera and microphone calls: zero.',
           '* Exactly one outcome for each word, including every miss/error. First ten diagnostic references and the remaining 188 use the same frozen v5 fixture, models, normal speed, and per-reference stream restart. No best-of selection.',
           '* These are reference regressions, **not independent live-user accuracy**. v4 had a disclosed source interruption/two-runner recovery, so the totals are not a clean same-protocol causal benchmark.','',
           '## Body-location candidate','',
           'The 24-word candidate was trained/calibrated only on source- and signer-separated train/validation data, with primary Watch clips excluded. Candidate and route policy were frozen before the 448-recording held-out audit. It is **not installed**. Independent audit eligibility does not establish browser integration, capture parity, or live-camera reliability. See body-manual-heldout.json for every paired outcome and unsupported-sign error.','',
           '## Remaining failures','', '| Word | Route | Actual output | Diagnosis |','|---|---|---|---|']
    lines += [f'| {t["label"]} | {t["route"]} | {t["prediction"] or "—"} | {t["diagnosis"]} |' for t in summary['remaining']]
    lines += ['', 'Full evidence: final-all-198.json, summary.json, word-results.csv, both separate pilots, frozen candidate and validation/held-out audits. Published recognition benchmarks have not been overwritten by these Watch-reference checks.']
    (root/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ['current','previous','completePlayback','candidate']},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=REPO/'reports/motion-repair-v5-20261107')
    parser.add_argument('--current',type=Path,required=True)
    parser.add_argument('--previous',type=Path,default=REPO/'reports/motion-repair-v4-20261107/virtual-final/final-all-198.json')
    parser.add_argument('--fixture',type=Path,default=REPO/'motion-virtual-camera-repair-v5-final.html')
    report(parser.parse_args())
