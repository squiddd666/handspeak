"""Offline browser parity and inference timing for a frozen residual candidate."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import torch
from playwright.sync_api import sync_playwright
from train_motion_residual import MotionNet, batch
import body_tip_features


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--experiment', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    args = p.parse_args()
    protocol = json.loads((args.experiment / 'protocol.json').read_text())
    report = json.loads((args.experiment / 'validation.json').read_text())
    source = Path(protocol['source']); checkpoint = args.experiment / 'motion-private.pt'
    if (hashlib.sha256(source.read_bytes()).hexdigest() != protocol['sourceSha256'] or
            hashlib.sha256(checkpoint.read_bytes()).hexdigest() != report['checkpointSha256']):
        raise ValueError('Frozen inputs changed')
    saved = torch.load(checkpoint, weights_only=True)
    if saved['outputLabels'] != protocol['outputLabels'] or json.loads(json.dumps(saved['selected'])) != report['selected']:
        raise ValueError('Checkpoint metadata mismatch')
    rows = json.loads(source.read_text())
    if any(r['split'] not in ('train', 'val') for r in rows):
        raise ValueError('Development data only')
    samples = {}
    for row in rows:
        if row['split'] == 'val':
            samples.setdefault((row['label'], row.get('sequence') is not None), row)
    samples = list(samples.values())
    motion_protocol = json.loads((args.experiment / 'motion-protocol.json').read_text())
    feature_encoding = motion_protocol.get('featureEncoding', 'legacy')
    if feature_encoding not in ('legacy', 'body-tips-v1'):
        raise ValueError('Unsupported feature encoding')
    if feature_encoding == 'body-tips-v1' and hashlib.sha256(Path(body_tip_features.__file__).read_bytes()).hexdigest() != motion_protocol['featureImplementationSha256']:
        raise ValueError('Frozen feature encoder changed')
    feature_fn = body_tip_features.features if feature_encoding == 'body-tips-v1' else batch.trainer.encoding.features
    inputs = np.stack([feature_fn(r) for r in samples])
    expected_logits, probabilities = [], []
    for state in saved['states']:
        net = MotionNet(len(saved['outputLabels']), torch.zeros(inputs.shape[1]), torch.ones(inputs.shape[1])).eval()
        net.load_state_dict(state)
        with torch.no_grad():
            logits = net(torch.tensor(inputs))
        expected_logits.append(logits.tolist()); probabilities.append(logits.softmax(1).numpy())
    selected = report['selected']; batch.trainer.LABELS = protocol['labels']
    expected = batch.trainer.outputs(samples, np.mean(probabilities, axis=0), selected['threshold'], selected['margin'])
    root = Path(__file__).resolve().parents[1] / 'accuracy'
    scripts = [root / 'temporal-browser.js', root / 'motion-residual-browser.js']
    payload = dict(rows=[{k: r[k] for k in ('rawFrames', 'body', 'imageAspect', 'sequence')} for r in samples],
                   weights=[{k: v.tolist() for k, v in state.items()} for state in saved['states']],
                   inputs=inputs.tolist(), logits=expected_logits, expected=expected,
                   threshold=selected['threshold'], margin=selected['margin'], labels=protocol['labels'], featureEncoding=feature_encoding)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=['--no-sandbox'])
        page = browser.new_page()
        for script in scripts:
            page.add_script_tag(content=script.read_text().replace('export ', ''))
        result = page.evaluate('''data => {
          let featureError=0, logitError=0; const predicted=[], timings=[];
          for(let n=0;n<data.rows.length;n++){
            const start=performance.now(), input=data.featureEncoding==='body-tips-v1'?bodyTipFeatures(data.rows[n]):temporalFeatures(data.rows[n]);
            input.forEach((row,c)=>row.forEach((v,t)=>{
              featureError=Math.max(featureError,Math.abs(v-data.inputs[n][c][t]));
            }));
            const probs=Array(data.logits[0][0].length).fill(0);
            data.weights.forEach((weights,m)=>{
              const logits=residualMotionLogits(input,weights), top=Math.max(...logits);
              const exp=logits.map(v=>Math.exp(v-top)), sum=exp.reduce((a,b)=>a+b,0);
              logits.forEach((v,c)=>{
                logitError=Math.max(logitError,Math.abs(v-data.logits[m][n][c]));
                probs[c]+=exp[c]/sum/data.weights.length;
              });
            });
            const order=probs.map((_,i)=>i).sort((a,b)=>probs[b]-probs[a]), best=order[0];
            predicted.push(data.rows[n].sequence!==null&&best<data.labels.length&&
              probs[best]>=data.threshold&&probs[best]-probs[order[1]]>=data.margin?data.labels[best]:null);
            timings.push(performance.now()-start);
          }
          timings.sort((a,b)=>a-b);
          return {maxFeatureError:featureError,maxLogitError:logitError,
            predictionsMatch:predicted.every((v,i)=>v===data.expected[i]),samples:predicted.length,
            offlineInferenceMedianMs:timings[Math.floor(timings.length*.5)],
            offlineInferenceP95Ms:timings[Math.floor(timings.length*.95)]};
        }''', payload)
        browser.close()
    if result['maxFeatureError'] >= 1e-5 or result['maxLogitError'] >= 1e-4 or not result['predictionsMatch']:
        raise ValueError(f'Browser parity failed: {result}')
    result.update(checkpointSha256=report['checkpointSha256'], outputClasses=len(saved['outputLabels']),
                  javascriptSha256={s.name: hashlib.sha256(s.read_bytes()).hexdigest() for s in scripts},
                  labelsCovered=len({r['label'] for r in samples}), deployed=False,
                  scope='Offline Chromium with cached development landmarks on this server. '
                        'Timing includes feature encoding and classifier only, while training may compete for CPU. '
                        'Not webcam throughput, body tracking, independent accuracy, or deployment.')
    args.report.mkdir(parents=True, exist_ok=True)
    (args.report / 'browser-parity.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
