"""Summarize an independent body-context unused-recording guard audit. No refitting."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.freeze_online_worker_audit import MANUAL_MODES
from scripts.run_online_native_audit import ROOT, sha
from scripts.train_native_manual_v4 import metrics


def compare_mode(rows, before, after, labels):
    lost = []
    for row, old, new in zip(rows, before, after):
        if old == row['label'] and old is not None and old != new:
            lost.append(dict(id=row['id'], label=row['label'], before=old, after=new))
    return dict(
        baseline=metrics(rows, before, labels),
        candidate=metrics(rows, after, labels),
        lostCorrectSources=lost,
        positiveRetentionPassed=not lost)


def main(args):
    folder = args.folder.resolve()
    protocol = json.loads((folder / 'protocol.json').read_text(encoding='utf-8'))
    if protocol['purpose'] != 'frozen-browser-independent-recording-guard-audit':
        raise ValueError('Wrong audit protocol')
    if sha(Path(protocol['candidate'])) != protocol['candidateSha256']:
        raise ValueError('Candidate changed after audit freeze')
    ledger = json.loads((folder / 'browser-ledger' / 'checkpoint.json').read_text(encoding='utf-8'))
    guard = json.loads((folder / 'browser-ledger' / 'guard' / 'checkpoint.json').read_text(encoding='utf-8'))
    if len(ledger['attempts']) != len(protocol['order']) or len(guard) != len(ledger['attempts']):
        raise ValueError('Incomplete audit ledger')
    integrity = json.loads((folder / 'post-run-integrity.json').read_text(encoding='utf-8'))
    if not integrity.get('allFrozenFilesUnchanged'):
        raise ValueError('Post-run integrity failed')
    rows = []
    for attempt, guarded in zip(ledger['attempts'], guard):
        if attempt['id'] != guarded['id']:
            raise ValueError('Guard supplement order mismatch')
        rows.append(dict(
            id=attempt['id'],
            label=attempt['label'],
            contractPassed=attempt['contractPassed'],
            baseline=attempt['manualPredictions'],
            candidate=guarded['predictions'],
            pairCount=attempt.get('pairCount', 0)))
    comparison = {}
    for mode, labels in MANUAL_MODES.items():
        before = [r['baseline'].get(mode) for r in rows]
        after = [r['candidate'].get(mode) for r in rows]
        comparison[mode] = compare_mode(rows, before, after, labels)
    promotion = 'reject production promotion: correct independent-audit source(s) lost' if any(
        not c['positiveRetentionPassed'] for c in comparison.values()) else (
        'retain offline; positive retention held on this unused-recording cohort, but do not claim full recognition repair without new-signer/full198/live-camera evidence')
    if any(not c['positiveRetentionPassed'] for c in comparison.values()):
        decision = 'rejected'
    else:
        decision = 'not-promoted-pending-broader-evidence'
    summary = dict(
        candidateSha256=protocol['candidateSha256'],
        sources=len(rows),
        contractsPassed=sum(r['contractPassed'] for r in rows),
        pairedFrames=sum(r['pairCount'] for r in rows),
        comparison=comparison,
        productionReceipts=len(list((folder / 'api-receipts').glob('*.json'))),
        fittingExcluded=True,
        gateSelectionFromAudit=False,
        deployed=False,
        promotion=promotion,
        decision=decision,
        independentAccuracy=False,
        newSignerAccuracy=False,
        scope=protocol['scope'])
    report_dir = ROOT / 'reports' / args.report_name
    report_dir.mkdir(exist_ok=False)
    (folder / 'audit-summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    (report_dir / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# Frozen body-context unused-recording guard audit',
        '',
        '**Recognition is not fully fixed; no production changes deployed.**',
        '',
        protocol['scope'],
        '',
        '| Mode | Correct before → candidate | Wrong before → candidate | Unsupported accepts before → candidate | Correct sources lost |',
        '|---|---:|---:|---:|---:|',
    ]
    for mode, result in comparison.items():
        lines.append(
            f"| {mode} | {result['baseline']['correct']} → {result['candidate']['correct']} | "
            f"{result['baseline']['wrong']} → {result['candidate']['wrong']} | "
            f"{result['baseline']['negativeFalse']} → {result['candidate']['negativeFalse']} | "
            f"{len(result['lostCorrectSources'])} |")
    lines += [
        '',
        promotion[0].upper() + promotion[1:] + '.',
        '',
        'Candidate only vetoes baseline accepts; no additional words recovered. Do not sum overlapping mode counts as independent recordings. No gate revision from this audit is allowed.',
        '',
        f"Actual production API receipts checked: {summary['productionReceipts']}.",
    ]
    for mode, result in comparison.items():
        for lost in result['lostCorrectSources']:
            lines.append(
                f"- Lost {lost['label']} ({lost['id']}) in {mode}; no best-of retry or gate adjustment.")
    (report_dir / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(dict(decision=decision, promotion=promotion, comparison={
        mode: dict(
            correct=(c['baseline']['correct'], c['candidate']['correct']),
            wrong=(c['baseline']['wrong'], c['candidate']['wrong']),
            negativeFalse=(c['baseline']['negativeFalse'], c['candidate']['negativeFalse']),
            lost=len(c['lostCorrectSources']),
            positiveRetentionPassed=c['positiveRetentionPassed'])
        for mode, c in comparison.items())
    }, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    parser.add_argument('--report-name', required=True)
    main(parser.parse_args())
