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


def model_outputs(protocol, selected):
    labels = protocol['labels']
    rejection = protocol.get('rejectionLabels', [trainer.OTHER])
    if not rejection or len(set(labels + rejection)) != len(labels + rejection):
        raise ValueError('Invalid or overlapping output classes')
    expected = labels + rejection
    if (protocol.get('outputLabels', labels + [trainer.OTHER]) != expected or
            selected.get('outputLabels', labels + [trainer.OTHER]) != expected):
        raise ValueError('Checkpoint class order differs from frozen protocol')
    return expected


def prepare(source, root, negative_weight=1.0, labels=None, temporal_bins=1, separate_negatives=False):
    if temporal_bins not in (1, 4):
        raise ValueError('Temporal bins must be 1 or 4')
    custom_labels = labels is not None
    labels = LABELS if labels is None else labels
    if (not isinstance(labels, list) or not labels or
            any(not isinstance(label, str) or not label.strip() or label != label.strip()
                or label == trainer.OTHER for label in labels) or
            len(labels) != len(set(labels))):
        raise ValueError('Labels must be a nonempty list of unique word names')
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
    if custom_labels:
        for label in labels:
            if not any(r['label'] == label for r in train) or not any(r['label'] == label for r in val):
                raise ValueError(f'Missing usable training or validation examples: {label}')
        if not any(r['label'] not in labels for r in train) or not any(r['label'] not in labels for r in val):
            raise ValueError('A vocabulary expansion needs other-sign negatives in both partitions')
    protocol = {
        'labels': labels,
        'source': str(source),
        'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'trainClips': len(train_all), 'usableTrainingClips': len(train),
        'validationClips': len(val),
        'perWord': {label: {
            'train': sum(r['label'] == label for r in train_all),
            'usableTrain': sum(r['label'] == label for r in train),
            'validation': sum(r['label'] == label for r in val),
        } for label in labels},
        'negativeLabels': sorted({r['label'] for r in data} - set(labels)),
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
            for label in labels}
        protocol['limitations'] = (
            'Development validation data previously used in research. '
            'Temporal features use center-frame body references where visible, '
            'otherwise wrist-centered fallback. Whole clips, not live capture. '
            'No test set is opened by this script.')
        body_modes = sorted({r.get('bodyMode', 'missing') for r in data})
        if 'per-frame pose' in body_modes:
            protocol['bodyReferenceModes'] = body_modes
            protocol['limitations'] = (
                'Development validation data previously used in research. '
                'Body references are measured per sampled frame where available; '
                'features use wrist-centered fallback when shoulders are not visible. '
                'Whole clips, not live capture. No test set is opened by this script.')
    if negative_weight != 1.0:
        protocol['negativeExampleLossMultiplier'] = negative_weight
        protocol['negativeWeightScope'] = 'Temporal training only; DTW unchanged.'
    if temporal_bins != 1:
        protocol['temporalBins'] = temporal_bins
        protocol['architectureChange'] = 'Pool into four ordered time regions instead of a single clip average.'
    if separate_negatives:
        rejected = sorted({r['label'] for r in train} - set(labels))
        if not rejected or any(r['label'] not in labels + rejected for r in val):
            raise ValueError('Every validation rejection label requires usable training examples')
        protocol['rejectionLabels'] = rejected
        protocol['outputLabels'] = labels + rejected
        protocol['rejectionTraining'] = ('Learn each other-sign label separately with per-class loss balancing; '
            'reject every non-target winning class without renormalization or fallback.')
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
    parser.add_argument('--labels-file', type=Path,
                        help='JSON list of target words; requires development coverage and negatives')
    parser.add_argument('--temporal-bins', type=int, choices=[1, 4], default=1)
    parser.add_argument('--separate-negatives', action='store_true')
    args = parser.parse_args()
    if args.model != 'temporal' and args.temporal_bins != 1:
        parser.error('--temporal-bins only applies to temporal training')
    if args.model != 'temporal' and args.separate_negatives:
        parser.error('--separate-negatives only applies to temporal training')
    labels = json.loads(args.labels_file.read_text()) if args.labels_file else LABELS
    train, val = prepare(args.source, args.output, args.negative_weight,
                         labels if args.labels_file else None, args.temporal_bins, args.separate_negatives)
    trainer.LABELS = labels
    trainer.ROOT = args.output
    trainer.fit.ROOT = args.output
    print(f'Training {args.model}: {len(train)} usable train clips, '
          f'{len(val)} validation clips; labels={labels}', flush=True)
    if args.model == 'temporal':
        trainer.train_temporal(train, val, negative_weight=args.negative_weight,
                               temporal_bins=args.temporal_bins,
                               rejection_labels=sorted({r['label'] for r in train} - set(labels))
                               if args.separate_negatives else None)
    else:
        trainer.train_dtw(train, val)
