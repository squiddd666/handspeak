"""Check offline JS/Python feature and frozen prediction parity on validation.

No training, acceptance-gate selection, test recordings, camera access, or model
installation. Coordinates stay in subprocess memory; only scalar diagnostics
are written. This is math parity, NOT browser capture or live-user accuracy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from body_manual_features import tensorize, mirrored, VERSION
from prepare_native_repair_v4 import read_rows, verify_splits
from train_body_manual_v5 import prepare, matrix, gate_statistics, gate_mask


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_js(rows, model=None, references=None, weights=None, node='node'):
    payload = dict(rows=rows)
    if model is not None:
        payload['model'] = model
    if references is not None:
        payload.update(references=references, weights=weights or {})
    process = subprocess.run([node, str(ROOT / 'scripts/verify_body_manual_runtime.mjs')],
                             input=json.dumps(payload, allow_nan=False), text=True,
                             encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             timeout=600, check=True)
    return json.loads(process.stdout)


def feature_error(expected, actual):
    if expected is None or actual is None:
        if (expected is None) != (actual is None):
            raise ValueError('Feature validity differs')
        return 0.0
    actual = np.asarray(actual)
    if actual.shape != expected.shape or not np.isfinite(actual).all():
        raise ValueError('Malformed JS feature output')
    error = float(np.max(np.abs(expected - actual)))
    if error > 1e-5:
        raise ValueError(f'Feature math differs: {error}')
    return error


def verify(args):
    if args.out.exists():
        raise FileExistsError(args.out)
    hashes = {str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path): sha(path)
              for path in [args.native, args.model, ROOT / 'body_manual_features.py', ROOT / 'handshape_features.py',
                           ROOT / 'training/experimental/body_manual_runtime.mjs', ROOT / 'scripts/verify_body_manual_runtime.mjs']}
    model = json.loads(args.model.read_text(encoding='utf-8'))
    selected = json.loads(args.model.with_suffix('.validation.json').read_text(encoding='utf-8'))
    if selected['modelSha256'] != sha(args.model) or selected['selectionSplit'] != 'val' or selected['testUsedForSelection']:
        raise ValueError('Only a validation-frozen candidate is allowed')
    if model['featureVersion'] != VERSION:
        raise ValueError('Unexpected feature version')
    raw = read_rows(args.native)
    watch = {source['originalFile'] for item in json.loads((ROOT / 'models/recognition-videos.json').read_text(encoding='utf-8'))['items']
             for source in item.get('sources', [])}
    verify_splits(raw, watch)  # Reject test or Watch sources before inference.
    if len({row['file'] for row in raw}) != len(raw) or any(row.get('error') for row in raw):
        raise ValueError('Duplicate source or failed native extraction')
    validation = [row for row in raw if row['split'] == 'val']
    if not validation:
        raise ValueError('No validation recordings')
    prepared = prepare(validation)
    # Match the frozen candidate contract. Manual Tasks rawFrames are NEVER
    # replaced with Holistic/recovered hands, or vice versa.
    inputs = [dict(imageAspect=row['imageAspect'], frames=[frame for frame in row['frames']
              if frame.get('pose') and (frame.get('left') or frame.get('right'))]) for row in validation]
    js = run_js(inputs, model=model, node=args.node)
    if len(js) != len(prepared):
        raise ValueError('Missing validation outcome')
    statistics = gate_statistics(matrix(prepared, model['samples'], model['featureParameters']), model['samples'], model['labels'])
    accepted = gate_mask(statistics, model['parameters'])
    records = []
    for index, (row, data) in enumerate(zip(prepared, js)):
        seq = row['sequence']
        err = feature_error(seq, data['sequence'])
        mirror_err = feature_error(mirrored(seq) if seq is not None else None, data['mirrored'])
        expected = str(statistics[0][index]) if accepted[index] else None
        if data['result']['prediction'] != expected or data['result']['tracked'] != (seq is not None):
            raise ValueError('Frozen prediction differs: ' + row['file'])
        distance_err = abs(float(statistics[2][index]) - data['result']['distance']) if seq is not None else 0.0
        if distance_err > 1e-5:
            raise ValueError('Distance math differs: ' + row['file'])
        records.append(dict(file=row['file'],prediction=expected,tracked=seq is not None,
                            featureMaxAbsError=err, mirrorMaxAbsError=mirror_err, distanceAbsError=distance_err))
    if sha(args.model) != selected['modelSha256'] or sha(args.native) != hashes[str(args.native.relative_to(ROOT)) if args.native.is_relative_to(ROOT) else str(args.native)]:
        raise ValueError('Frozen inputs changed during validation')
    result = dict(featureVersion=VERSION,validationRecordings=len(records),predictionMatches=len(records),
                  featureMaxAbsError=max(r['featureMaxAbsError'] for r in records),
                  mirrorMaxAbsError=max(r['mirrorMaxAbsError'] for r in records),
                  distanceMaxAbsError=max(r['distanceAbsError'] for r in records),
                  modelChangesInstalled=False,testUsedForSelection=False,watchExcluded=True,
                  sourcesAndParticipantsDisjoint=True,browserCaptureParityVerified=False,liveCameraAccuracyVerified=False,
                  inputsSha256=hashes,records=records,
                  scope='Validation-only deterministic JS/Python parity. Existing frozen v5 candidate remains offline. '
                        'No gate/policy/weight changes. Native Holistic body and Tasks manual streams stay separate. '
                        'This does not repair the known NO regression or establish browser capture parity.')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:value for key,value in result.items() if key not in ('records','inputsSha256')},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('native','model','out'):
        parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--node',default='node')
    verify(parser.parse_args())
