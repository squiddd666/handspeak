"""Reload and verify a joint temporal candidate; export evidence, never a model."""
import argparse
import collections
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
import train_expansion_batch as batch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    root = args.experiment
    protocol = json.loads((root / 'protocol.json').read_text())
    selected = json.loads((root / 'temporal-validation.json').read_text())['selected']
    checkpoint = root / 'temporal-private.pt'
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != selected['sha256']:
        raise ValueError('Checkpoint changed after validation')
    source = Path(protocol['source'])
    if hashlib.sha256(source.read_bytes()).hexdigest() != protocol['sourceSha256']:
        raise ValueError('Development data changed after training')
    labels = protocol['labels']
    # Recheck partition/coverage guards and the frozen protocol before inference.
    _, rows = batch.prepare(source, root,
        negative_weight=protocol.get('negativeExampleLossMultiplier', 1.0), labels=labels,
        temporal_bins=protocol.get('temporalBins', 1))
    if selected.get('temporalBins', 1) != protocol.get('temporalBins', 1):
        raise ValueError('Checkpoint architecture differs from protocol')
    batch.trainer.LABELS = labels
    net = batch.trainer.Net(selected['width'], num_classes=len(labels) + 1,
                            temporal_bins=protocol.get('temporalBins', 1))
    net.load_state_dict(torch.load(checkpoint, map_location='cpu', weights_only=True)['state'])
    net.eval()
    features = torch.tensor(np.stack([batch.trainer.encoding.features(r) for r in rows]))
    with torch.no_grad():
        probabilities = net(features).softmax(1).numpy()
    predictions = batch.trainer.outputs(rows, probabilities, selected['threshold'], selected['margin'])
    metrics = batch.trainer.metrics(rows, predictions)
    if metrics != selected['validation']:
        raise ValueError('Reloaded checkpoint does not reproduce reported validation')
    errors = [dict(expected=r['label'], predicted=p, sha256=r['sha256'],
                   usableSequence=r.get('sequence') is not None)
              for r, p in zip(rows, predictions)
              if (r['label'] in labels and p != r['label']) or (r['label'] not in labels and p is not None)]
    report = dict(status='needs-independent-testing' if selected['passesValidation'] else 'withheld',
        deployed=False, targetWords=len(labels), labels=labels, selected=selected,
        checkpointReloadReproducedValidation=True, protocol=protocol,
        validationBodyModes=dict(collections.Counter(r.get('bodyMode', 'missing') for r in rows)),
        validationFrameCounts=dict(collections.Counter(len(r['rawFrames']) for r in rows)),
        errors=errors,
        limitations=['Previously inspected development validation; not independent accuracy.',
            'Whole clips only; no automatic capture or browser timing test.',
            'No ordinary hand-movement negatives.',
            'Source caches use different frame sampling; body-reference modes and frame counts '
            'are recorded in the companion JSON.',
            'Existing signs outside this catalog are negatives for this candidate. '
            'It cannot replace the current recognizers without separate integration/regression tests.',
            'Softmax thresholds are model-selection parameters, not calibrated confidence.'])
    args.report.mkdir(parents=True, exist_ok=True)
    (args.report / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    lines = [f'# Joint {len(labels)}-word temporal experiment', '',
        f"**{report['status']}; not deployed.** Reloading the checkpoint reproduced validation.", '',
        f"The candidate recognized **{metrics['correct']}/{metrics['total']} target clips correctly**, "
        f"made **{metrics['wrong']} wrong-word suggestions**, and missed **{metrics['missed']}**. "
        f"It falsely accepted **{metrics['negativeFalse']}/{metrics['negativeTotal']}** other-sign clips.", '',
        f"Training used {protocol['usableTrainingClips']} usable clips from {protocol['trainClips']} "
        f"training recordings. Validation included {protocol['validationClips']} recordings. "
        'Training and validation signer IDs and recording hashes were checked for overlap. '
        'No reserved test clips were opened.', '',
        'The frozen screen requires at least 50% correct, no wrong or other-sign suggestions, '
        'and at least one correct example for every target word. Passing validation alone '
        'would still require independent signer tests and automatic-camera testing.', '',
        '| Word | Correct | Validation clips |', '| --- | ---: | ---: |']
    lines += [f"| {label} | {value['correct']} | {value['total']} |"
              for label, value in metrics['perWord'].items()]
    lines += ['', '## Limits', ''] + ['- ' + value for value in report['limitations']]
    lines += ['', 'Source: PopSign ASL v1.0, Georgia Tech and DPAN, CC BY 4.0. '
              'Private recordings and checkpoints remain outside the served website.', '']
    (args.report / 'README.md').write_text('\n'.join(lines))
    print(json.dumps({k: v for k, v in metrics.items() if k != 'perWord'}))


if __name__ == '__main__':
    main()
