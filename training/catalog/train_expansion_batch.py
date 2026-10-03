"""Reproducible first expansion experiment; development data only, no deployment.

Reuses cached PopSign landmarks and the existing temporal/DTW trainers. All
non-target labels are negative examples, not additional supported vocabulary.
"""
import argparse
import hashlib
import json
import sys
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'daily_words'))
import train_citizen as trainer

LABELS = ['THIRSTY', 'HOT', 'SICK', 'READ', 'GIVE', 'CALL', 'FIND',
          'NOW', 'TOMORROW', 'MILK']


def prepare(source, root, negative_weight=1.0):
    if not math.isfinite(negative_weight) or negative_weight <= 0:
        raise ValueError('Negative-example loss multiplier must be finite and positive')
    data = json.loads(source.read_text())
    if any(r['split'] not in ('train', 'val') for r in data):
        raise ValueError('Only development partitions may enter this experiment')
    train_all = [r for r in data if r['split'] == 'train']
    val = [r for r in data if r['split'] == 'val']
    for field in ('participant', 'sha256'):
        if {str(r[field]) for r in train_all} & {str(r[field]) for r in val}:
            raise ValueError(f'Train/validation overlap: {field}')
    for row in data:
        row.setdefault('body', [None] * len(row['rawFrames']))
    train = [r for r in train_all if r.get('sequence') is not None]
    protocol = {
        'labels': LABELS,
        'source': str(source),
        'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'trainClips': len(train_all), 'usableTrainingClips': len(train),
        'validationClips': len(val),
        'perWord': {label: {
            'train': sum(r['label'] == label for r in train_all),
            'usableTrain': sum(r['label'] == label for r in train),
            'validation': sum(r['label'] == label for r in val),
        } for label in LABELS},
        'negativeLabels': sorted({r['label'] for r in data} - set(LABELS)),
        'validationGate': 'At least 50% correct, zero wrong supported and negative '
                          'accepts, and at least one correct example per word.',
        'releaseGate': 'Validation is screening only. Require a new untouched '
                       'signer test, real ordinary-movement negatives, comparison '
                       'with current models, and real-time browser capture tests '
                       'before deployment.',
        'limitations': 'Cached development data previously used in research. '
                      'No upper-body pose in this cache: temporal features use '
                      'wrist-centered fallback. Whole clips, not live capture. '
                      'No test set is opened by this script.',
        'attribution': 'PopSign ASL v1.0, Georgia Tech and DPAN, CC BY 4.0.',
    }
    body_count = sum(any(p is not None for p in row['body']) for row in data)
    if body_count:
        protocol['clipsWithBodyReference'] = body_count
        protocol['perWordTrainingSigners'] = {
            label: len({str(r['participant']) for r in train_all if r['label'] == label})
            for label in LABELS}
        protocol['limitations'] = (
            'Development validation data previously used in research. '
            'Temporal features use center-frame body references where visible, '
            'otherwise wrist-centered fallback. Whole clips, not live capture. '
            'No test set is opened by this script.')
    if negative_weight != 1.0:
        protocol['negativeExampleLossMultiplier'] = negative_weight
        protocol['negativeWeightScope'] = 'Temporal training only; DTW unchanged.'
    root.mkdir(parents=True, exist_ok=True)
    path = root / 'protocol.json'
    if path.exists() and json.loads(path.read_text()) != protocol:
        raise ValueError('Existing protocol differs; use a new experiment directory')
    path.write_text(json.dumps(protocol, indent=2) + '\n')
    return train, val


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(
        '/opt/handspeak-training/vocabulary-v8/development-features.json'))
    parser.add_argument('--output', type=Path, default=Path(
        '/opt/handspeak-training/vocabulary-expansion-batch1'))
    parser.add_argument('--model', choices=['temporal', 'dtw'], required=True)
    parser.add_argument('--negative-weight', type=float, default=1.0)
    args = parser.parse_args()
    train, val = prepare(args.source, args.output, args.negative_weight)
    trainer.LABELS = LABELS
    trainer.ROOT = args.output
    trainer.fit.ROOT = args.output
    print(f'Training {args.model}: {len(train)} usable train clips, '
          f'{len(val)} validation clips; labels={LABELS}', flush=True)
    if args.model == 'temporal':
        trainer.train_temporal(train, val, negative_weight=args.negative_weight)
    else:
        trainer.train_dtw(train, val)
