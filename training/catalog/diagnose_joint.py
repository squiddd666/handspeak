"""Diagnose frozen candidates on development data; never open held-out tests."""
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
    parser.add_argument('--experiment', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    protocol = json.loads((args.experiment / 'protocol.json').read_text())
    selected = json.loads((args.experiment / 'temporal-validation.json').read_text())['selected']
    checkpoint = args.experiment / 'temporal-private.pt'
    source = Path(protocol['source'])
    if (hashlib.sha256(source.read_bytes()).hexdigest() != protocol['sourceSha256'] or
            hashlib.sha256(checkpoint.read_bytes()).hexdigest() != selected['sha256']):
        raise ValueError('Source or checkpoint differs from frozen selection')
    labels = protocol['labels']
    bins = protocol.get('temporalBins', 1)
    if selected.get('temporalBins', 1) != bins:
        raise ValueError('Selected architecture differs from frozen protocol')
    batch.prepare(source, args.experiment, labels=labels, temporal_bins=bins,
                  negative_weight=protocol.get('negativeExampleLossMultiplier', 1.0))
    data = json.loads(source.read_text())
    batch.trainer.LABELS = labels
    net = batch.trainer.Net(selected['width'], num_classes=len(labels) + 1, temporal_bins=bins)
    net.load_state_dict(torch.load(checkpoint, map_location='cpu', weights_only=True)['state'])
    net.eval()
    report = dict(checkpointSha256=selected['sha256'], sourceSha256=protocol['sourceSha256'],
                  temporalBins=bins, independentTest=False, deployed=False, partitions={})
    for split in ('train', 'val'):
        rows = [r for r in data if r['split'] == split]
        x = torch.tensor(np.stack([batch.trainer.encoding.features(r) for r in rows]))
        with torch.no_grad():
            probs = net(x).softmax(1).numpy()
        raw = [labels[i] if i < len(labels) else None for i in probs.argmax(1)]
        accepted = batch.trainer.outputs(rows, probs, selected['threshold'], selected['margin'])
        metrics = batch.trainer.metrics(rows, accepted)
        if split == 'val' and metrics != selected['validation']:
            raise ValueError('Validation could not be reproduced')
        per_word = {}
        for label in labels:
            ids = [i for i, row in enumerate(rows) if row['label'] == label]
            per_word[label] = dict(total=len(ids),
                signers=len({rows[i]['participant'] for i in ids}),
                trackingFailures=sum(rows[i].get('sequence') is None for i in ids),
                rawTop1Correct=sum(raw[i] == label for i in ids),
                acceptedCorrect=sum(accepted[i] == label for i in ids))
        positive = [i for i, row in enumerate(rows) if row['label'] in labels]
        confusion = collections.Counter((rows[i]['label'], raw[i] or 'OTHER')
                                        for i in positive if raw[i] != rows[i]['label'])
        report['partitions'][split] = dict(
            targetClips=len(positive),
            rawTop1Correct=sum(raw[i] == rows[i]['label'] for i in positive),
            targetTrackingFailures=sum(rows[i].get('sequence') is None for i in positive),
            thresholded=metrics, perWord=per_word,
            bodyModes=dict(collections.Counter(r.get('bodyMode', 'missing') for r in rows)),
            topConfusions=[dict(expected=a, predicted=b, count=n)
                           for (a, b), n in confusion.most_common(20)])
    report['limitations'] = ['Training includes failed clips for coverage accounting; only usable '
        'training clips were fitted. Raw top-1 ignores the tracking/rejection gates and is diagnostic only.',
        'Previously inspected development data; no new independent accuracy claim.',
        'A lower rejection threshold cannot repair tracking failure or wrong top-1 predictions.']
    args.report.mkdir(parents=True, exist_ok=True)
    (args.report / 'diagnostic.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({s: {k: v for k, v in values.items()
                         if k not in ('perWord', 'topConfusions', 'thresholded')}
                      for s, values in report['partitions'].items()}, indent=2))


if __name__ == '__main__':
    main()
