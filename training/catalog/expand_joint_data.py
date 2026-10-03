"""Expand established PopSign mappings across training signers; no test media access."""
import argparse
import collections
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import tarfile

import expand_batch_data as expansion
import dense_extract
from popsign_range import request


def write_json(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, separators=(',', ':')) + '\n')
    tmp.replace(path)


def select(label, base, root, target, heldout):
    existing = [r for r in base if r['split'] == 'train' and r['label'] == label]
    sources = {r['source'] for r in existing}
    if len(sources) != 1:
        raise ValueError(f'Expected one established source mapping for {label}')
    url = sources.pop()
    if not url.startswith('https://signdata.cc.gatech.edu/data/popsign_v1_0/game/train/'):
        raise ValueError('Source must be an official PopSign training archive')
    path = root / 'selection' / (label + '.json')
    if path.exists():
        return json.loads(path.read_text())
    counts = collections.Counter(str(r['participant']) for r in existing)
    seen = {r['member'] for r in existing}
    rows, offset = [], 0
    for _ in range(3000):
        if len(existing) + len(rows) >= target:
            break
        header = expansion.requests.request(url, offset, 512)
        if header == bytes(512):
            break
        member = tarfile.TarInfo.frombuf(header, 'utf-8', 'replace')
        start = offset + 512
        offset = start + ((member.size + 511) // 512) * 512
        who = re.search(r'4a\.(\d+)', member.name)
        if not member.isfile() or not member.name.endswith('.mp4') or not who or member.name in seen:
            continue
        signer = who.group(1)
        if signer in heldout:
            raise ValueError('Training archive contains a held-out signer')
        if counts[signer] >= 2:
            continue
        counts[signer] += 1
        seen.add(member.name)
        rows.append(dict(label=label, sourceLabel=Path(url).stem, split='train',
            participant=signer, source=url, member=member.name, offset=start, size=member.size,
            kind='supported', file=str(root / 'videos' / label / Path(member.name).name)))
    write_json(path, rows)
    print('Selected', label, len(rows), 'new;', len(existing) + len(rows), 'total;', len(counts), 'signers', flush=True)
    return rows


def initialize(root):
    expansion.ROOT = root
    expansion.requests.request = request


def extract(row):
    return expansion.add_body(expansion.extract(row))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--labels-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--target', type=int, default=48)
    parser.add_argument('--stage', choices=['download', 'extract'], required=True)
    args = parser.parse_args()
    if not 12 <= args.target <= 96:
        parser.error('Target must be between 12 and 96')
    base = json.loads(args.source.read_text())
    if any(r['split'] not in ('train', 'val') for r in base):
        raise ValueError('Base must contain development clips only')
    labels = json.loads(args.labels_file.read_text())
    heldout = {str(r['participant']) for r in base if r['split'] == 'val'}
    heldout_hashes = {r['sha256'] for r in base if r['split'] == 'val'}
    manifests = {}
    # Identity metadata only: no test landmarks, videos, predictions, or outcomes.
    for name in ('vocabulary-v7/test-manifest.json', 'accuracy-v4/fresh-test-manifest.json',
                 'vocabulary-expansion-fresh-test/test-manifest.json'):
        path = Path('/opt/handspeak-training') / name
        data = json.loads(path.read_text())
        if any(r['split'] != 'test' for r in data):
            raise ValueError('Unexpected identity manifest partition')
        heldout.update(str(r['participant']) for r in data)
        heldout_hashes.update(r['sha256'] for r in data)
        manifests[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    root = args.output
    root.mkdir(parents=True, exist_ok=True)
    (root / 'selection').mkdir(exist_ok=True)
    protocol = dict(source=str(args.source), sourceSha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),
        labels=labels, targetTrainingClipsPerWord=args.target, newClipsPerSignerCap=2,
        heldoutIdentityManifestHashes=manifests, testMediaAccess=False,
        rule='Established source mappings only; retain existing clips; add official training recordings; '
             'exclude held-out signers and recording hashes; keep validation unchanged.')
    path = root / 'expansion-protocol.json'
    if path.exists() and json.loads(path.read_text()) != protocol:
        raise ValueError('Frozen expansion protocol differs; use a fresh output directory')
    write_json(path, protocol)
    initialize(root)
    if args.stage == 'download':
        with ThreadPoolExecutor(max_workers=4) as pool:
            batches = pool.map(lambda label: select(label, base, root, args.target, heldout), labels)
            selected = [row for rows in batches for row in rows]
        expansion.validate_training_rows(selected, base)
        if {str(r['participant']) for r in selected} & heldout:
            raise ValueError('Cached selection overlaps held-out signers')
        write_json(root / 'selection.json', selected)
        result = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            for row in pool.map(expansion.download, selected):
                if row['sha256'] in heldout_hashes:
                    raise ValueError('Downloaded training recording duplicates held-out data')
                result.append(row)
                if len(result) % 50 == 0:
                    print('Downloaded', len(result), '/', len(selected), flush=True)
        write_json(root / 'additional-manifest.json', result)
        print('Download complete:', len(result), flush=True)
    else:
        rows = json.loads((root / 'additional-manifest.json').read_text())
        expansion.validate_training_rows(rows, base)
        if any(str(r['participant']) in heldout or r['sha256'] in heldout_hashes for r in rows):
            raise ValueError('Manifest overlaps held-out identities')
        for row in rows:
            if hashlib.sha256(Path(row['file']).read_bytes()).hexdigest() != row['sha256']:
                raise ValueError('Downloaded recording changed')
        extraction_protocol = dict(
            manifestSha256=hashlib.sha256((root / 'additional-manifest.json').read_bytes()).hexdigest(),
            expansionProtocolSha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            handDetectorSha256=hashlib.sha256(Path(dense_extract.MODEL).read_bytes()).hexdigest(),
            handExtractorSha256=hashlib.sha256(Path(dense_extract.__file__).read_bytes()).hexdigest(),
            bodyExtractorSha256=hashlib.sha256(Path(expansion.__file__).read_bytes()).hexdigest(),
            encoderSha256={name: hashlib.sha256((dense_extract.ROOT / name).read_bytes()).hexdigest()
                          for name in ('gesture-model.js', 'motion-model.js')},
            frameSampling='Up to 60 unique original frames; detector confidence and hand quality gates unchanged',
            bodyReference='Center-frame pose; static_image_mode=True, model_complexity=1')
        extraction_path = root / 'extraction-protocol.json'
        if extraction_path.exists() and json.loads(extraction_path.read_text()) != extraction_protocol:
            raise ValueError('Frozen extraction protocol differs')
        write_json(extraction_path, extraction_protocol)
        combined = {r['sha256']: r for r in base}
        with ProcessPoolExecutor(max_workers=3, initializer=initialize, initargs=(root,)) as pool:
            for count, row in enumerate(pool.map(extract, rows), 1):
                old = combined.get(row['sha256'])
                if old and any(str(old[k]) != str(row[k]) for k in ('label', 'split', 'participant')):
                    raise ValueError('Recording has conflicting identity or label')
                if old is None:
                    combined[row['sha256']] = row
                if count % 25 == 0:
                    print('Extracted', count, '/', len(rows), flush=True)
        output = list(combined.values())
        if [r for r in output if r['split'] == 'val'] != [r for r in base if r['split'] == 'val']:
            raise ValueError('Validation unexpectedly changed')
        write_json(root / 'development-features.json', output)
        coverage = {label: dict(
            train=sum(r['split'] == 'train' and r['label'] == label for r in output),
            usableTrain=sum(r['split'] == 'train' and r['label'] == label and r.get('sequence') is not None for r in output),
            trainSigners=len({str(r['participant']) for r in output if r['split'] == 'train' and r['label'] == label}))
            for label in labels}
        write_json(root / 'coverage.json', coverage)
        print('Extraction complete:', len(output), 'development clips', flush=True)


if __name__ == '__main__':
    main()
