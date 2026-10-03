"""Development-only mirror diagnostic at the checkpoint's unchanged thresholds."""
import argparse
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
    protocol = json.loads((args.experiment / 'protocol.json').read_text())
    selected = json.loads((args.experiment / 'temporal-validation.json').read_text())['selected']
    source = Path(protocol['source'])
    checkpoint = args.experiment / 'temporal-private.pt'
    if (hashlib.sha256(source.read_bytes()).hexdigest() != protocol['sourceSha256'] or
            hashlib.sha256(checkpoint.read_bytes()).hexdigest() != selected['sha256']):
        raise ValueError('Frozen data/checkpoint changed')
    data = json.loads(source.read_text())
    if any(r['split'] not in ('train', 'val') for r in data):
        raise ValueError('Only development data is allowed')
    rows = [r for r in data if r['split'] == 'val']
    batch.trainer.LABELS = protocol['labels']
    net = batch.trainer.Net(selected['width'], num_classes=len(batch.model_outputs(protocol, selected)),
                            temporal_bins=protocol.get('temporalBins', 1)).eval()
    net.load_state_dict(torch.load(checkpoint, weights_only=True, map_location='cpu')['state'])
    probabilities = []
    for samples in (rows, [batch.trainer.encoding.mirrored(r) for r in rows]):
        x = torch.tensor(np.stack([batch.trainer.encoding.features(r) for r in samples]))
        with torch.no_grad():
            probabilities.append(net(x).softmax(1).numpy())
    original, mirrored = probabilities
    predict = lambda p: batch.trainer.outputs(rows, p, selected['threshold'], selected['margin'])
    baseline = batch.trainer.metrics(rows, predict(original))
    if baseline != selected['validation']:
        raise ValueError('Baseline validation did not reproduce')
    mean_predictions = predict((original + mirrored) / 2)
    consensus = [p if a == b else None for p, a, b in
                 zip(mean_predictions, original.argmax(1), mirrored.argmax(1))]
    trials = {name: batch.trainer.metrics(rows, pred) for name, pred in
              [('original', predict(original)), ('mirrorMean', mean_predictions), ('mirrorAgreement', consensus)]}
    result = dict(checkpointSha256=selected['sha256'], sourceSha256=protocol['sourceSha256'],
        threshold=selected['threshold'], margin=selected['margin'], trials=trials,
        passesValidation={name: batch.trainer.gate(metrics) for name, metrics in trials.items()},
        independentTest=False, deployed=False,
        scope='Existing development recordings and unchanged thresholds. Mirrors are correlated '
              'views of the same recording, not independent samples. No release or camera claim.')
    args.report.mkdir(parents=True, exist_ok=True)
    (args.report / 'mirror-diagnostic.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({name: {k:v for k,v in m.items() if k!='perWord'} for name,m in trials.items()}))


if __name__ == '__main__':
    main()
