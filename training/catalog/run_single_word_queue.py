"""Serialize individual training and recorded-sign checks; never deploy an unchecked model."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
BASE = Path('/opt/handspeak-training/single-word-20261010')
REPORT = REPO / 'reports/vocabulary-expansion/single-word'
WORDS = ['FIND', 'FISH', 'SEE', 'SICK', 'PAIN', 'NIGHT', 'MORNING']


def write(value):
    value['deployed'] = any(item.get('deployed') for item in value.get('completed', []))
    REPORT.mkdir(parents=True, exist_ok=True)
    target = REPORT / 'queue-status.json'
    temporary = target.with_suffix('.partial')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(target)


def run(script, word):
    log = BASE / (word.lower() + '-queue.log')
    with log.open('a') as output:
        subprocess.run([sys.executable, '-u', str(REPO / 'training/catalog' / script), '--word', word],
                       cwd=REPO, stdout=output, stderr=subprocess.STDOUT, check=True)


def main():
    completed = []
    word = None
    try:
        for word in WORDS:
            report = REPORT / word.lower()
            completion = report / 'completion.json'
            write(dict(state='running', word=word, stage='training', completed=completed, deployed=False))
            # Adopt the already-running FIND job without starting a second trainer.
            deadline = time.monotonic() + 7200
            while not completion.exists() and subprocess.run(
                    ['systemctl', 'is-active', '--quiet', f'handspeak-single-{word.lower()}-20261010.service']).returncode == 0:
                if time.monotonic() > deadline:
                    raise TimeoutError('Existing training exceeded two hours')
                time.sleep(15)
            if not completion.exists():
                if (BASE / word.lower() / 'plan.json').exists():
                    raise RuntimeError('Interrupted frozen experiment requires inspection, not overwrite')
                run('train_single_word.py', word)
            if not json.loads(completion.read_text())['passesDevelopmentScreen']:
                completed.append(dict(word=word, outcome='development-failed'))
                continue
            write(dict(state='running', word=word, stage='recorded-sign-checks', completed=completed, deployed=False))
            status_path = report / 'release-status.json'
            status = json.loads(status_path.read_text()) if status_path.exists() else {}
            if status.get('stage') not in ('regression-failed', 'recording-check-complete'):
                run('evaluate_single_word.py', word)
                status = json.loads(status_path.read_text())
            if status.get('state') != 'complete':
                raise RuntimeError(f'Incomplete evaluation: {status}')
            if status.get('passesFreshSignGate'):
                write(dict(state='running', word=word, stage='publishing-experimental', completed=completed))
                run('publish_single_word.py', word)
                completed.append(dict(word=word, outcome='published-experimental', deployed=True,
                                      cameraTested=False, integrationTested=False))
                continue
            completed.append(dict(word=word, outcome=status['stage'], passesFreshSignGate=False))
        write(dict(state='complete', completed=completed, deployed=False,
                   message='Queue finished; passing candidates published as experimental. See per-word outcomes.'))
    except Exception as error:
        write(dict(state='failed', word=word, completed=completed, deployed=False, error=str(error)))
        raise


if __name__ == '__main__':
    main()
