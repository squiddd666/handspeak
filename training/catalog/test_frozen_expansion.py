"""Freeze an eight-word candidate and evaluate fresh PopSign test recordings.

Vocabulary selection uses development validation only. Masked classes are rejected
without renormalizing probabilities or falling back to another word. No deployment.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile

import numpy as np
import torch
import train_expansion_batch as batch
import expand_batch_data as preparation

ROOT = Path('/opt/handspeak-training/vocabulary-expansion-fresh-test')
SOURCE = Path('/opt/handspeak-training/vocabulary-expansion-batch2')
LABELS = [word for word in batch.LABELS if word not in ('MILK', 'GIVE')]
NEGATIVES = ['MILK', 'GIVE', 'CAR', 'LIKE', 'HELLO', 'WATER', 'PLEASE', 'FINISH']
GLOSSES = {'CALL': 'callonphone'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def predict(rows, probabilities, threshold, margin):
    # Keep all original logits/classes: excluded winners mean rejection.
    if probabilities.shape != (len(rows), len(batch.LABELS) + 1):
        raise ValueError('Original classifier output shape differs')
    order = np.argsort(probabilities, axis=1)
    outputs = []
    for row, scores, ranked in zip(rows, probabilities, order):
        winner, second = ranked[-1], ranked[-2]
        word = batch.LABELS[winner] if winner < len(batch.LABELS) else None
        outputs.append(word if word in LABELS and row.get('sequence') is not None
                       and scores[winner] >= threshold and scores[winner] - scores[second] >= margin else None)
    return outputs


def metrics(rows, outputs):
    result = batch.trainer.fit.metrics(rows, outputs, LABELS)
    result['perWord'] = {label: dict(
        total=sum(row['label'] == label for row in rows),
        correct=sum(row['label'] == label and output == label
                    for row, output in zip(rows, outputs))) for label in LABELS}
    return result


def freeze():
    selected = json.loads((SOURCE / 'temporal-validation.json').read_text())['selected']
    if sha(SOURCE / 'temporal-private.pt') != selected['sha256']:
        raise ValueError('Source checkpoint changed')
    ROOT.mkdir(exist_ok=True)
    protocol = dict(labels=LABELS, originalOutputLabels=batch.LABELS,
        rejectedOutputLabels=['MILK', 'GIVE', 'OTHER MOVEMENT'],
        selection='MILK and GIVE excluded based on development validation errors, before fresh test access.',
        checkpointSha256=selected['sha256'], width=selected['width'],
        threshold=selected['threshold'], margin=selected['margin'],
        testLabels=LABELS + NEGATIVES, requestedClipsPerLabel=6, maxClipsPerSigner=2,
        screeningGate='At least 50% correct target clips, zero wrong words and other-sign accepts, at least one correct per target.',
        deploymentGate='Fresh clip testing alone is insufficient. Also require ordinary-movement negatives, runtime feature parity, and live automatic-camera/browser tests.',
        limitations='Test uses fresh recordings from the official test signer pool. That signer pool has appeared in earlier experiments; do not call it a never-inspected population. Train, validation, and test participants remain separate.',
        sourceDevelopmentSha256=sha(SOURCE / 'body-development-features.json'))
    path = ROOT / 'protocol.json'
    if path.exists() and json.loads(path.read_text()) != protocol:
        raise ValueError('Frozen protocol differs; cannot alter after test selection')
    path.write_text(json.dumps(protocol, indent=2) + '\n')
    checkpoint = ROOT / 'frozen.pt'
    if checkpoint.exists() and sha(checkpoint) != protocol['checkpointSha256']:
        raise ValueError('Frozen checkpoint differs')
    if not checkpoint.exists():
        shutil.copyfile(SOURCE / 'temporal-private.pt', checkpoint)
    rows = [r for r in json.loads((SOURCE / 'body-development-features.json').read_text()) if r['split'] == 'val']
    # Recompute rather than trusting row alignment in a prior cached prediction file.
    probabilities = infer(rows, protocol)
    result = metrics(rows, predict(rows, probabilities, protocol['threshold'], protocol['margin']))
    (ROOT / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    if not batch.trainer.gate(result):
        raise ValueError('Subset did not pass validation; do not open test recordings')
    (ROOT / 'protocol.sha256').write_text(sha(path) + '\n')
    print('Frozen validation', json.dumps(result), flush=True)


def verify():
    protocol = json.loads((ROOT / 'protocol.json').read_text())
    if sha(ROOT / 'protocol.json') != (ROOT / 'protocol.sha256').read_text().strip():
        raise ValueError('Frozen protocol changed')
    if not batch.trainer.gate(json.loads((ROOT / 'validation.json').read_text())):
        raise ValueError('Validation did not pass')
    if protocol['labels'] != LABELS or sha(ROOT / 'frozen.pt') != protocol['checkpointSha256']:
        raise ValueError('Frozen candidate changed')
    return protocol


def infer(rows, protocol):
    model = batch.trainer.Net(protocol['width'], num_classes=len(batch.LABELS) + 1)
    model.load_state_dict(torch.load(ROOT / 'frozen.pt', weights_only=True)['state'])
    model.eval()
    with torch.no_grad():
        return model(torch.tensor(np.stack([batch.trainer.encoding.features(r) for r in rows]))).softmax(1).numpy()


def exclusions():
    known = {p.name for p in Path('/opt/handspeak-training').rglob('*.mp4') if ROOT not in p.parents}
    hashes = set()
    for path in Path('/opt/handspeak-training').rglob('*.json'):
        if ROOT in path.parents or not ('manifest' in path.name or path.name == 'selection.json'):
            continue
        try:
            rows = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    if row.get('sha256'):
                        hashes.add(row['sha256'])
                    for key in ('file', 'member'):
                        if row.get(key):
                            known.add(Path(row[key]).name)
    return known, hashes


def select(job):
    label, excluded = job
    path = ROOT / 'selection' / (label + '.json')
    if path.exists():
        return json.loads(path.read_text())
    gloss = GLOSSES.get(label, label.lower())
    url = f'https://signdata.cc.gatech.edu/data/popsign_v1_0/game/test/{gloss}.tar'
    rows, counts, offset = [], {}, 0
    for _ in range(2000):
        if len(rows) == 6:
            break
        header = preparation.requests.request(url, offset, 512)
        if header == bytes(512):
            break
        info = tarfile.TarInfo.frombuf(header, 'utf-8', 'replace')
        start = offset + 512
        offset = start + ((info.size + 511) // 512) * 512
        match = re.search(r'4a\.(\d+)', info.name)
        if not info.isfile() or not info.name.endswith('.mp4') or not match or Path(info.name).name in excluded:
            continue
        signer = match.group(1)
        if counts.get(signer, 0) >= 2:
            continue
        counts[signer] = counts.get(signer, 0) + 1
        rows.append(dict(label=label, sourceLabel=gloss, split='test', participant=signer,
            source=url, member=info.name, offset=start, size=info.size,
            file=str(ROOT / 'videos' / gloss / Path(info.name).name)))
    if len(rows) != 6:
        raise ValueError(f'Insufficient fresh test clips for {label}: {len(rows)}')
    path.write_text(json.dumps(rows, indent=2) + '\n')
    print('Selected fresh', label, len(rows), flush=True)
    return rows


def download():
    verify()
    (ROOT / 'selection').mkdir(exist_ok=True)
    known, previous_hashes = exclusions()
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = [row for part in pool.map(select, [(label, known) for label in LABELS + NEGATIVES]) for row in part]
    development = json.loads((SOURCE / 'body-development-features.json').read_text())
    if {str(r['participant']) for r in rows} & {str(r['participant']) for r in development}:
        raise ValueError('Fresh test signers overlap development')
    preparation.ROOT = ROOT
    with ThreadPoolExecutor(max_workers=3) as pool:
        downloaded = list(pool.map(preparation.download, rows))
    hashes = [r['sha256'] for r in downloaded]
    if len(hashes) != len(set(hashes)) or set(hashes) & ({r['sha256'] for r in development} | previous_hashes):
        raise ValueError('Duplicate test content or development leakage')
    (ROOT / 'test-manifest.json').write_text(json.dumps(downloaded, indent=2) + '\n')
    print('Fresh downloads complete', len(downloaded), flush=True)


def extract(row):
    preparation.ROOT = ROOT
    return preparation.add_body(preparation.extract(row))


def extract_all():
    protocol = verify()
    rows = json.loads((ROOT / 'test-manifest.json').read_text())
    known, prior_hashes = exclusions()
    development = json.loads((SOURCE / 'body-development-features.json').read_text())
    if sha(SOURCE / 'body-development-features.json') != protocol['sourceDevelopmentSha256']:
        raise ValueError('Development data changed after freezing')
    if {str(r['participant']) for r in rows} & {str(r['participant']) for r in development}:
        raise ValueError('Test/development signer overlap')
    hashes = [r['sha256'] for r in rows]
    if len(set(hashes)) != len(rows) or set(hashes) & prior_hashes:
        raise ValueError('Previously used or duplicate recording in test manifest')
    if len(rows) != len(protocol['testLabels']) * protocol['requestedClipsPerLabel']:
        raise ValueError('Incomplete test manifest')
    for label in protocol['testLabels']:
        if sum(r['label'] == label for r in rows) != protocol['requestedClipsPerLabel']:
            raise ValueError(f'Test coverage differs for {label}')
    for row in rows:
        if row['split'] != 'test' or '/game/test/' not in row['source']:
            raise ValueError('Recording is not from the official test partition')
        if Path(row['member']).name in known or sha(Path(row['file'])) != row['sha256']:
            raise ValueError('Reused or modified test recording')
    result = []
    with ProcessPoolExecutor(max_workers=3) as pool:
        for row in pool.map(extract, rows):
            result.append(row)
            if len(result) % 10 == 0:
                print('Extracted fresh', len(result), '/', len(rows), flush=True)
    (ROOT / 'test-features.json').write_text(json.dumps(result, separators=(',', ':')))


def evaluate():
    protocol = verify()
    rows = json.loads((ROOT / 'test-features.json').read_text())
    manifest = json.loads((ROOT / 'test-manifest.json').read_text())
    identity = lambda records: [(r['sha256'], r['label'], str(r['participant'])) for r in records]
    if identity(rows) != identity(manifest):
        raise ValueError('Test features omit, reorder, or relabel frozen recordings')
    probabilities = infer(rows, protocol)
    outputs = predict(rows, probabilities, protocol['threshold'], protocol['margin'])
    result = dict(test=metrics(rows, outputs), checkpointSha256=protocol['checkpointSha256'],
                  testFeaturesSha256=sha(ROOT / 'test-features.json'), deployed=False,
                  evaluation='Fresh recording test; frozen vocabulary, checkpoint, and rejection settings.')
    result['passesFreshClipScreen'] = batch.trainer.gate(result['test'])
    result['errors'] = [dict(actual=r['label'], suggested=p, sha256=r['sha256'])
                        for r, p in zip(rows, outputs) if p is not None and p != r['label']]
    (ROOT / 'test-result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['freeze', 'download', 'extract', 'evaluate'])
    args = parser.parse_args()
    {'freeze': freeze, 'download': download, 'extract': extract_all, 'evaluate': evaluate}[args.stage]()
