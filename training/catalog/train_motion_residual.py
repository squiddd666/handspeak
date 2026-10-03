"""Development-only residual motion experiment. Never deploys or reads test clips."""
import argparse
import copy
import hashlib
import itertools
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
import train_expansion_batch as batch
import body_tip_features


class MotionNet(nn.Module):
    """Keep frame-local evidence and explicit motion before pooling."""
    def __init__(self, classes, mean, scale):
        super().__init__()
        channels = torch.as_tensor(mean).numel()
        self.register_buffer('mean', torch.as_tensor(mean).reshape(1, channels, 1))
        self.register_buffer('scale', torch.as_tensor(scale).reshape(1, channels, 1))
        self.project = nn.Conv1d(channels * 2, 64, 1)
        self.blocks = nn.ModuleList([
            nn.Sequential(nn.Conv1d(64, 64, 3, padding=d, dilation=d),
                          nn.GroupNorm(8, 64), nn.GELU(), nn.Dropout(.2),
                          nn.Conv1d(64, 64, 3, padding=d, dilation=d))
            for d in (1, 2, 4)
        ])
        self.head = nn.Sequential(nn.Dropout(.3), nn.Linear(128, classes))

    def forward(self, x):
        x = ((x - self.mean) / self.scale).clamp(-8, 8)
        delta = torch.cat([torch.zeros_like(x[:, :, :1]), x[:, :, 1:] - x[:, :, :-1]], 2)
        x = self.project(torch.cat([x, delta], 1))
        for block in self.blocks:
            x = nn.functional.gelu(x + block(x))
        return self.head(torch.cat([x.mean(2), x.amax(2)], 1))


def augmented_batch(x):
    # Vary signing speed with a monotone, endpoint-preserving time warp.
    steps = torch.rand(len(x), 31, device=x.device) * .8 + .6
    times = torch.cat([torch.zeros(len(x), 1, device=x.device), steps.cumsum(1)], 1)
    times = times / times[:, -1:] * 31
    lo = times.floor().long().clamp(max=31)
    hi = (lo + 1).clamp(max=31)
    alpha = (times - lo).unsqueeze(1)
    warped = x.gather(2, lo[:, None].expand(-1, x.shape[1], -1)) * (1 - alpha)
    warped += x.gather(2, hi[:, None].expand(-1, x.shape[1], -1)) * alpha
    return warped + torch.randn_like(warped) * .01


def select(rows, probs):
    best = None
    for threshold, margin in itertools.product([.35, .5, .65, .8, .9, .97], [0, .1, .25, .4]):
        m = batch.trainer.metrics(rows, batch.trainer.outputs(rows, probs, threshold, margin))
        if best is None or batch.trainer.score(m) < batch.trainer.score(best['validation']):
            best = dict(threshold=threshold, margin=margin, validation=m)
    return best


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--body-tips', action='store_true')
    args = p.parse_args()
    baseline = json.loads((args.baseline / 'protocol.json').read_text())
    source = Path(baseline['source'])
    if hashlib.sha256(source.read_bytes()).hexdigest() != baseline['sourceSha256']:
        raise ValueError('Development source changed')
    labels = baseline['labels']
    train, val = batch.prepare(source, args.output, labels=labels, separate_negatives=True)
    protocol = json.loads((args.output / 'protocol.json').read_text())
    specification = dict(architecture='residual-motion-v1', seeds=[17, 29, 43], epochs=80,
                         validationEpochs=[20, 40, 80], learningRate=.001,
                         weightDecay=.02, labelSmoothing=.05,
                         implementationSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                         sourceSha256=protocol['sourceSha256'],
                         normalization='Training augmented feature mean/std only; std floor 0.1',
                         augmentation='Horizontal mirror and monotone time warp; additive noise 0.01',
                         releaseGate=protocol['releaseGate'])
    if args.body_tips:
        specification['featureEncoding'] = 'body-tips-v1'
        specification['featureImplementationSha256'] = hashlib.sha256(Path(body_tip_features.__file__).read_bytes()).hexdigest()
    spec_path = args.output / 'motion-protocol.json'
    if spec_path.exists() and json.loads(spec_path.read_text()) != specification:
        raise ValueError('Experiment changed; use a new directory')
    spec_path.write_text(json.dumps(specification, indent=2) + '\n')
    batch.trainer.LABELS = labels
    torch.set_num_threads(2)
    augmented = train + [batch.trainer.encoding.mirrored(r) for r in train]
    feature_fn = body_tip_features.features if args.body_tips else batch.trainer.encoding.features
    x = torch.tensor(np.stack([feature_fn(r) for r in augmented]))
    vx = torch.tensor(np.stack([feature_fn(r) for r in val]))
    output_labels = protocol['outputLabels']
    y = torch.tensor([output_labels.index(r['label']) for r in augmented])
    mean = x.mean((0, 2)); scale = x.std((0, 2)).clamp(min=.1)
    weights = 1 / torch.bincount(y, minlength=len(output_labels)).float().clamp(min=1)
    weights /= weights.mean()
    best = None
    trials = []
    final_states, final_probs = [], []
    started = time.monotonic()

    def consider(probs, states, info):
        nonlocal best
        entry = dict(**info, **select(val, probs))
        trials.append(entry)
        if best is None or batch.trainer.score(entry['validation']) < batch.trainer.score(best['validation']):
            best = copy.deepcopy(entry)
            torch.save(dict(states=states, selected=entry, outputLabels=output_labels), args.output / 'motion-private.pt')
        m = entry['validation']
        print(json.dumps(dict(**info, correct=m['correct'], wrong=m['wrong'],
                              negativeFalse=m['negativeFalse'], passesValidation=batch.trainer.gate(m))), flush=True)

    for seed in specification['seeds']:
        torch.manual_seed(seed)
        net = MotionNet(len(output_labels), mean, scale)
        opt = torch.optim.AdamW(net.parameters(), lr=.001, weight_decay=.02)
        schedule = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=80, eta_min=.00005)
        for epoch in range(1, 81):
            net.train()
            for ids in torch.randperm(len(x)).split(64):
                opt.zero_grad()
                loss = nn.functional.cross_entropy(net(augmented_batch(x[ids])), y[ids],
                                                   weight=weights, label_smoothing=.05)
                loss.backward()
                nn.utils.clip_grad_norm_(net.parameters(), 5)
                opt.step()
            schedule.step()
            if epoch not in specification['validationEpochs']:
                continue
            net.eval()
            with torch.no_grad():
                probs = net(vx).softmax(1).numpy()
            consider(probs, [copy.deepcopy(net.state_dict())], dict(seed=seed, epoch=epoch, members=1))
        final_states.append(copy.deepcopy(net.state_dict()))
        final_probs.append(probs)
    consider(np.mean(final_probs, axis=0), final_states, dict(seeds=specification['seeds'], epoch=80, members=3))
    # Reload the serialized winner and reproduce its screen before reporting.
    saved = torch.load(args.output / 'motion-private.pt', weights_only=True)
    reloaded = []
    for state in saved['states']:
        net = MotionNet(len(output_labels), mean, scale)
        net.load_state_dict(state); net.eval()
        with torch.no_grad():
            reloaded.append(net(vx).softmax(1).numpy())
    probs = np.mean(reloaded, axis=0)
    predicted = batch.trainer.outputs(val, probs, best['threshold'], best['margin'])
    if batch.trainer.metrics(val, predicted) != best['validation']:
        raise ValueError('Reloaded candidate failed reproducibility check')
    result = dict(selected=best, trials=trials, passesValidation=batch.trainer.gate(best['validation']),
                  checkpointSha256=hashlib.sha256((args.output / 'motion-private.pt').read_bytes()).hexdigest(),
                  sourceSha256=protocol['sourceSha256'], checkpointReloadVerified=True,
                  independentAccuracyPassed=False, deployed=False, elapsedSeconds=time.monotonic() - started,
                  errors=[dict(sha256=r['sha256'], expected=r['label'], predicted=p,
                               usable=r.get('sequence') is not None)
                          for r, p in zip(val, predicted)
                          if (r['label'] in labels and p != r['label']) or (r['label'] not in labels and p is not None)])
    for directory in (args.output, args.report):
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    m = best['validation']
    (args.report / 'README.md').write_text(
        '# Residual motion experiment\n\n'
        f"**Not deployed.** Development screen: {m['correct']}/{m['total']} correct, "
        f"{m['wrong']} wrong supported-word predictions, {m['missed']} misses, "
        f"{m['negativeFalse']}/{m['negativeTotal']} false accepts on other signs.\n\n"
        f"Passes unchanged validation gate: {result['passesValidation']}. Checkpoint reload reproduced the result.\n\n"
        'Uses the balanced development data and seven separate rejection classes. '
        'Adds training-only feature normalization, explicit frame differences, residual dilated '
        'convolutions, mean/max pooling, and time-warp augmentation. Multiple changes mean this '
        'experiment does not isolate the effect of any one change.\n\n'
        + ('This variant also retains explicit fingertip/body coordinates and hand/body scale.\n\n' if args.body_tips else '') +
        'Previously inspected validation, not independent accuracy. No ordinary movement negatives, '
        'browser parity, automatic-camera timing, or untouched final test was evaluated here. '
        'All release requirements still apply. Raw videos and checkpoints stay outside the website.\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('errors', 'trials')}), flush=True)


if __name__ == '__main__':
    main()
