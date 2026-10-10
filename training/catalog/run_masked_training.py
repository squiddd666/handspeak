"""Run the missing-landmark augmentation correction without touching production."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--labels-file', type=Path)
    parser.add_argument('--target-weight', type=float, default=1.)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    if output.is_relative_to(repo) or output.is_relative_to(Path('/opt/handspeak/releases')):
        raise ValueError('Training artifacts must remain outside the served website')
    output.mkdir(parents=True, exist_ok=True)
    args.report.mkdir(parents=True, exist_ok=True)
    protocol = json.loads((args.baseline / 'protocol.json').read_text())
    source = Path(protocol['source'])
    if hashlib.sha256(source.read_bytes()).hexdigest() != protocol['sourceSha256']:
        raise ValueError('Baseline source changed')
    scripts = [Path(__file__), repo / 'training/catalog/train_motion_residual.py',
               repo / 'training/catalog/body_tip_features.py',
               repo / 'training/catalog/train_expansion_batch.py',
               repo / 'training/daily_words/train_citizen.py',
               repo / 'training/accuracy/temporal.py',
               repo / 'training/catalog/check_residual_browser.py',
               repo / 'training/accuracy/temporal-browser.js',
               repo / 'training/accuracy/motion-residual-browser.js']
    hashes = {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in scripts}
    frozen = dict(sourceSha256=protocol['sourceSha256'], implementations=hashes,
                  change='Coordinate-only noise; preserve missing landmarks and metadata',
                  independentTestOpened=False, deployed=False)
    labels_args = []
    if args.labels_file:
        labels = json.loads(args.labels_file.read_text())
        frozen['targetLabels'] = labels
        frozen['targetLossMultiplier'] = args.target_weight
        labels_path = output / 'target-labels.json'
        labels_path.write_text(json.dumps(labels) + '\n')
        labels_args = ['--labels-file', str(labels_path)]
    frozen_path = output / 'correction-protocol.json'
    if frozen_path.exists():
        raise ValueError('Use a new experiment directory; do not overwrite a run')
    frozen_path.write_text(json.dumps(frozen, indent=2) + '\n')
    for p in scripts:
        dest = output / 'source-snapshot' / p.relative_to(repo)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(p.read_bytes())

    def status(stage, **extra):
        value = dict(stage=stage, deployed=False, independentAccuracyPassed=False, **extra)
        for directory in (output, args.report):
            temp = directory / 'job-status.json.partial'
            temp.write_text(json.dumps(value, indent=2) + '\n')
            temp.replace(directory / 'job-status.json')
        print(json.dumps(value), flush=True)

    def verify_code():
        if any(hashlib.sha256(p.read_bytes()).hexdigest() != hashes[str(p.relative_to(repo))] for p in scripts):
            raise ValueError('Implementation changed during experiment')

    try:
        status('training', state='running')
        subprocess.run([sys.executable, str(repo / 'training/catalog/train_motion_residual.py'),
                        '--baseline', str(args.baseline), '--output', str(output),
                        '--report', str(args.report), '--body-tips', '--masked-augmentation',
                        '--target-weight', str(args.target_weight), *labels_args],
                       cwd=repo, check=True)
        verify_code()
        status('browser-parity', state='running')
        subprocess.run([sys.executable, str(repo / 'training/catalog/check_residual_browser.py'),
                        '--experiment', str(output), '--report', str(args.report)], cwd=repo, check=True)
        verify_code()
        result = json.loads((output / 'validation.json').read_text())
        status('complete', state='complete', passesValidation=result['passesValidation'],
               validation=result['selected']['validation'],
               nextStep=('Freeze candidate and perform independent recorded-video and integration tests'
                         if result['passesValidation'] else 'Validation failed; do not deploy'))
    except Exception as exc:
        status('failed', state='failed', error=str(exc))
        raise


if __name__ == '__main__':
    main()
