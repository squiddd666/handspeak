"""Resumable managed training job. Writes reports, never deploys a model."""
import datetime
import fcntl
import json
from pathlib import Path
import subprocess
import sys

SITE = Path(__file__).resolve().parents[2]
ROOT = Path('/opt/handspeak-training/vocabulary-expansion-joint50-balanced')
LABELS = '/opt/handspeak-training/vocabulary-expansion-joint50/labels.json'
SOURCE = '/opt/handspeak-training/vocabulary-expansion-joint50-recovery/development-features.json'
REPORT = SITE / 'reports/vocabulary-expansion/joint50-balanced'


def update(stage, state, **extra):
    status = dict(stage=stage, state=state, updated=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  deployed=False, **extra)
    temporary = ROOT / 'job-status.tmp'
    temporary.write_text(json.dumps(status, indent=2) + '\n')
    temporary.replace(ROOT / 'job-status.json')


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    # Quarantine interrupted generated-cache writes; preserve original recordings.
    for path in [*(ROOT / 'videos').rglob('*.landmarks.json'), *(ROOT / 'body').glob('*.json')]:
        try:
            json.loads(path.read_text())
        except json.JSONDecodeError:
            path.rename(path.with_name(path.name + '.interrupted-' + str(path.stat().st_mtime_ns)))
    jobs = [
        ('download', ['expand_joint_data.py', '--source', SOURCE, '--labels-file', LABELS,
                      '--output', str(ROOT), '--stage', 'download']),
        ('extract', ['expand_joint_data.py', '--source', SOURCE, '--labels-file', LABELS,
                     '--output', str(ROOT), '--stage', 'extract']),
        ('train', ['train_expansion_batch.py', '--source', str(ROOT / 'development-features.json'),
                   '--labels-file', LABELS, '--output', str(ROOT), '--model', 'temporal']),
        ('verify', ['report_joint_experiment.py', '--experiment', str(ROOT), '--report', str(REPORT)]),
        ('browser-parity', ['check_joint_browser.py', '--experiment', str(ROOT), '--report', str(REPORT)]),
    ]
    for stage, args in jobs:
        update(stage, 'running')
        print('Starting', stage, flush=True)
        command = [sys.executable, str(SITE / 'training/catalog' / args[0]), *args[1:]]
        with (ROOT / (stage + '.log')).open('a') as output:
            result = subprocess.run(command, cwd=SITE, stdout=output, stderr=subprocess.STDOUT)
        if result.returncode:
            update(stage, 'failed', exitCode=result.returncode)
            raise SystemExit(result.returncode)
    result = json.loads((REPORT / 'validation.json').read_text())
    selected = result['selected']
    update('complete', 'complete', passesValidation=selected['passesValidation'],
           metrics=selected['validation'], report=str(REPORT / 'README.md'),
           independentAccuracyPassed=False,
           nextStep='Independent signer and live-capture tests are still required if validation passes.')
    for name in ('expansion-protocol.json', 'extraction-protocol.json', 'coverage.json', 'job-status.json'):
        (REPORT / name).write_bytes((ROOT / name).read_bytes())
    print('Completed; validation passed:', selected['passesValidation'], '; no deployment.', flush=True)


if __name__ == '__main__':
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / '.job.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            main()
        except Exception as error:
            update('pipeline', 'failed', error=str(error))
            raise
