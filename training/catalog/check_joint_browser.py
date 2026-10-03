"""Offline Chromium/PyTorch parity for frozen one-bin joint classifiers.

Research-only check: no live endpoint, webcam, test set, or model publication.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from playwright.sync_api import sync_playwright
import torch
import train_expansion_batch as batch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads((args.experiment / 'protocol.json').read_text())
    selected = json.loads((args.experiment / 'temporal-validation.json').read_text())['selected']
    if protocol.get('temporalBins', 1) != 1 or selected.get('temporalBins', 1) != 1:
        raise ValueError('This browser evaluator supports one-bin pooling only')
    source = Path(protocol['source'])
    checkpoint = args.experiment / 'temporal-private.pt'
    if (hashlib.sha256(source.read_bytes()).hexdigest() != protocol['sourceSha256'] or
            hashlib.sha256(checkpoint.read_bytes()).hexdigest() != selected['sha256']):
        raise ValueError('Frozen data or checkpoint changed')
    rows = json.loads(source.read_text())
    if any(r['split'] not in ('train', 'val') for r in rows):
        raise ValueError('Only development examples may enter this check')
    # Deterministic coverage of every development label, plus every quality failure.
    samples = {}
    for row in rows:
        if row['split'] == 'val':
            samples.setdefault((row['label'], row.get('sequence') is not None), row)
    samples = list(samples.values())
    labels = protocol['labels']
    batch.trainer.LABELS = labels
    saved = torch.load(checkpoint, map_location='cpu', weights_only=True)
    net = batch.trainer.Net(selected['width'], num_classes=len(labels)+1).eval()
    net.load_state_dict(saved['state'])
    features = np.stack([batch.trainer.encoding.features(r) for r in samples])
    with torch.no_grad():
        logits = net(torch.tensor(features)).numpy()
        probabilities = torch.tensor(logits).softmax(1).numpy()
    expected = batch.trainer.outputs(samples, probabilities, selected['threshold'], selected['margin'])
    script = Path(__file__).resolve().parents[1] / 'accuracy/temporal-browser.js'
    payload = dict(rows=[{k: r[k] for k in ('rawFrames', 'body', 'imageAspect', 'sequence')} for r in samples],
        weights={k: v.tolist() for k, v in saved['state'].items()}, inputs=features.tolist(),
        expectedLogits=logits.tolist(), expected=expected, labels=labels,
        threshold=selected['threshold'], margin=selected['margin'])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=['--no-sandbox'])
        page = browser.new_page()
        page.set_default_timeout(120000)
        page.add_script_tag(content=script.read_text().replace('export ', ''))
        result = page.evaluate('''data => {
          let featureError=0, logitError=0;const predictions=[];
          for(let n=0;n<data.rows.length;n++){
            const input=temporalFeatures(data.rows[n]);
            for(let c=0;c<input.length;c++)for(let t=0;t<input[c].length;t++)
              featureError=Math.max(featureError,Math.abs(input[c][t]-data.inputs[n][c][t]));
            const logits=temporalLogits(input,data.weights);
            logits.forEach((v,i)=>{logitError=Math.max(logitError,Math.abs(v-data.expectedLogits[n][i]));});
            const max=Math.max(...logits),exps=logits.map(v=>Math.exp(v-max)),sum=exps.reduce((s,v)=>s+v,0);
            const probs=exps.map(v=>v/sum),order=probs.map((v,i)=>i).sort((a,b)=>probs[b]-probs[a]);
            const best=order[0],gap=probs[best]-probs[order[1]];
            predictions.push(data.rows[n].sequence!=null&&best<data.labels.length&&
              probs[best]>=data.threshold&&gap>=data.margin?data.labels[best]:null);
          }
          return {maxFeatureError:featureError,maxLogitError:logitError,
            predictionsMatch:predictions.every((v,i)=>v===data.expected[i]),samples:predictions.length};
        }''', payload)
        browser.close()
    if result['maxFeatureError'] >= 1e-5 or result['maxLogitError'] >= 1e-4 or not result['predictionsMatch']:
        raise ValueError(f'Browser parity failed: {result}')
    result.update(checkpointSha256=selected['sha256'], javascriptSha256=hashlib.sha256(script.read_bytes()).hexdigest(),
        labelsCovered=len({r['label'] for r in samples}), outputClasses=len(labels)+1,
        includesRejectedTracking=any(r.get('sequence') is None for r in samples),
        deployed=False, scope='Offline classifier parity on cached development landmarks. '
        'No camera, body-detector integration, live timing, independent accuracy, or deployment claim.')
    args.report.mkdir(parents=True, exist_ok=True)
    (args.report / 'browser-parity.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
