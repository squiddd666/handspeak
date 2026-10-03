"""Export a reviewable experiment decision without deploying model assets."""
import argparse
import hashlib
import json
from pathlib import Path


def report(root, output):
    protocol = json.loads((root / 'protocol.json').read_text())
    temporal = json.loads((root / 'temporal-validation.json').read_text())
    dtw = json.loads((root / 'dtw-validation.json').read_text())
    for result, filename in ((temporal['selected'], 'temporal-private.pt'),
                             (dtw, 'dtw-private.json')):
        if hashlib.sha256((root / filename).read_bytes()).hexdigest() != result['sha256']:
            raise ValueError(f'Checkpoint hash differs: {filename}')
    passing = [name for name, result in [('temporal', temporal['selected']), ('dtw', dtw)]
               if result['passesValidation']]
    decision = dict(status='needs-independent-testing' if passing else 'withheld',
                    deployed=False, labels=protocol['labels'], validationPassing=passing,
                    temporal=temporal['selected'], dtw=dtw, testSetOpened=False,
                    liveCameraTestPerformed=False,
                    reason='Validation screening does not authorize deployment. '
                           'Untouched signer testing, negative movements, existing-word '
                           'regression, and browser capture evaluation remain required.')
    output.mkdir(parents=True, exist_ok=True)
    for name, value in [('protocol', protocol), ('temporal-validation', temporal),
                        ('dtw-validation', dtw), ('decision', decision)]:
        (output / (name + '.json')).write_text(json.dumps(value, indent=2) + '\n')
    lines = ['# Expanded training experiment', '',
             '**Status: ' + decision['status'] + '. No new model deployed.**', '',
             'Words: ' + ', '.join(protocol['labels']) + '.', '',
             '| Model | Correct | Wrong word | Missed | Other-sign false accepts |',
             '| --- | ---: | ---: | ---: | ---: |']
    for name, value in [('Temporal', temporal['selected']), ('DTW', dtw)]:
        m = value['validation']
        lines.append(f"| {name} | {m['correct']}/{m['total']} | {m['wrong']} | "
                     f"{m['missed']} | {m['negativeFalse']}/{m['negativeTotal']} |")
    lines += ['', f"Training: {protocol['usableTrainingClips']} usable clips out of "
              f"{protocol['trainClips']}. Validation: {protocol['validationClips']} clips.", '',
              protocol['limitations'], '', protocol['releaseGate'], '',
              'These are validation model-selection results, not independent accuracy or '
              'real webcam measurements. Other-sign negatives do not cover ordinary hand '
              'movements. The first 10-word experiment and this experiment share validation '
              'recordings; changes are development comparisons only.', '',
              'Body positions use a single center-frame reference. New training clips sample '
              '60 frames; cached clips retain their earlier sampling. These changes mean '
              'any difference cannot be attributed solely to additional training data.', '',
              'Raw clips and checkpoints remain outside the served website. Source: '
              '[PopSign ASL v1.0](https://signdata.cc.gatech.edu/view/datasets/popsign_v1_0/index.html), '
              'Georgia Tech and DPAN, CC BY 4.0.', '',
              'The complete 201-entry recognition expansion remains unfinished. Entries '
              'without verified labeled sources require data acquisition and semantic '
              'review; phrases cannot be mapped to isolated signs by text alone.', '']
    (output / 'README.md').write_text('\n'.join(lines))
    print(json.dumps(decision, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report(args.root, args.output)
