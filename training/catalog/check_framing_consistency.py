"""Development-only invariance screen; fixed predictions must agree in both views."""
import argparse
import json
from pathlib import Path
import numpy as np
import torch
from body_tip_features import features
from camera_framing import scaled
from calibrate_word_thresholds import predictions, sha, write
from train_motion_residual import MotionNet, batch


def agreement(first, second):
    if len(first) != len(second):
        raise ValueError('Prediction lengths differ')
    return [a if a is not None and a == b else None for a, b in zip(first, second)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    p = json.loads((args.candidate / 'protocol.json').read_text())
    if sha(args.candidate / 'frozen.pt') != p['checkpointSha256'] or sha(p['source']) != p['sourceSha256']:
        raise ValueError('Frozen inputs changed')
    data = json.loads(Path(p['source']).read_text())
    if any(r['split'] not in ('train', 'val') for r in data):
        raise ValueError('Development data only')
    rows = [r for r in data if r['split'] == 'val']
    del data
    saved = torch.load(args.candidate / 'frozen.pt', weights_only=True)
    if len(saved['states']) != 1 or saved['outputLabels'] != p['outputLabels']:
        raise ValueError('Unexpected model layout')
    torch.set_num_threads(1)
    model = MotionNet(len(p['outputLabels']), torch.zeros(175), torch.ones(175)).eval()
    model.load_state_dict(saved['states'][0])
    batch.trainer.LABELS = p['labels']
    results = []
    for factor in (1, .5625, 1.3):
        framed = [scaled(r, factor) for r in rows]
        views = [framed, [batch.trainer.encoding.mirrored(r) for r in framed]]
        outputs = []
        for view in views:
            with torch.no_grad():
                scores = model(torch.tensor(np.stack([features(r) for r in view]))).softmax(1).numpy()
            outputs.append(predictions(view, scores, p))
        results.append(dict(scale=factor, metrics=batch.trainer.metrics(rows, agreement(*outputs))))
    result = dict(checkpointSha256=p['checkpointSha256'], implementationSha256=sha(__file__),
                  rule='Require the unchanged classifier to accept the same word on original and mirrored views; otherwise reject. No thresholds tuned.',
                  scope='Reused development clips only. Extra inference cost; no camera or independent accuracy claim.',
                  passesDevelopmentScreen=all(batch.trainer.gate(r['metrics']) for r in results),
                  framingValidation=results, deployed=False)
    write(args.report / 'mirror-consistency.json', result)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
