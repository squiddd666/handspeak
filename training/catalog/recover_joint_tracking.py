"""Retry failed, sparsely sampled development clips in an isolated cache.

Keeps the existing detector thresholds and quality gate. No video downloads,
test partition access, changes to prior caches, or deployment.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import os
from pathlib import Path

import dense_extract


def select_clips(data):
    if any(r['split'] not in ('train', 'val') for r in data):
        raise ValueError('Only development clips may be recovered')
    selected = [r for r in data if r.get('sequence') is None and len(r['rawFrames']) < 60]
    if any(r.get('bodyMode') != 'center-frame reference' or
           len(r['body']) != len(r['rawFrames']) or
           any(p != r['body'][0] for p in r['body']) for r in selected):
        raise ValueError('Recovery requires fixed body references')
    return selected


def recover(job):
    row, root = job
    source = Path(row['file'])
    if hashlib.sha256(source.read_bytes()).hexdigest() != row['sha256']:
        raise ValueError('Original video does not match recording hash')
    target = root / (row['sha256'] + source.suffix)
    if not target.exists():
        os.link(source, target)
    result = dense_extract.extract(dict(row, file=str(target)))
    # All input clips use a fixed center-frame body reference, retained here.
    pose = row['body'][0] if row['body'] else None
    result['body'] = [pose] * len(result['rawFrames'])
    result['originalFile'] = str(source)
    result['trackingRecovery'] = 'Up to 60 unique original frames; same detector and quality gate'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.source.read_text())
    selected = select_clips(data)
    args.output.mkdir(parents=True, exist_ok=True)
    cache = args.output / 'recovery'
    cache.mkdir(exist_ok=True)
    protocol = dict(source=str(args.source), sourceSha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),
        selected=[r['sha256'] for r in selected],
        rule='sequence is null and fewer than 60 frames; train/val only; detector thresholds unchanged',
        detectorSha256=hashlib.sha256(Path(dense_extract.MODEL).read_bytes()).hexdigest(),
        extractorSha256=hashlib.sha256(Path(dense_extract.__file__).read_bytes()).hexdigest(),
        encoderSha256={name: hashlib.sha256((dense_extract.ROOT / name).read_bytes()).hexdigest()
                      for name in ('gesture-model.js', 'motion-model.js')})
    path = args.output / 'recovery-protocol.json'
    if path.exists() and json.loads(path.read_text()) != protocol:
        raise ValueError('Existing recovery protocol differs')
    path.write_text(json.dumps(protocol, indent=2) + '\n')
    recovered = {}
    with ProcessPoolExecutor(max_workers=2) as pool:
        for result in pool.map(recover, [(r, cache) for r in selected]):
            recovered[result['sha256']] = result
            if len(recovered) % 10 == 0:
                print('Re-extracted', len(recovered), '/', len(selected), flush=True)
    combined = [recovered.get(r['sha256'], r) for r in data]
    output = args.output / 'development-features.json'
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(combined, separators=(',', ':')))
    temporary.replace(output)
    report = dict(attempted=len(selected), recovered=sum(r.get('sequence') is not None for r in recovered.values()),
        byPartition={s: dict(attempted=sum(r['split'] == s for r in selected),
            recovered=sum(r['split'] == s and r.get('sequence') is not None for r in recovered.values()))
            for s in ('train', 'val')},
        deployed=False, independentTest=False, dataSha256=hashlib.sha256(output.read_bytes()).hexdigest())
    (args.output / 'recovery-result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
