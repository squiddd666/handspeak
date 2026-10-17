"""Re-run a frozen single-word candidate's fresh recorded-clip test with one explicitly
documented negative-label exclusion.

Why this file exists: `select()` in evaluate_ready_subset requires 2 eligible held-out
clips for every mapped label. The PopSign v1 test archive holds only 19 SHOWER clips from
a single signer, 18 of which are already in `knownNames`, so exactly 1 is eligible and
every fresh test now fails before download. See
reports/vocabulary-expansion/single-word/heldout-audit-20261017.md.

This variant keeps the frozen originals byte-identical (so previously published FISH/SICK
protocols stay reproducible), records the exclusion inside the generated protocol, and
only changes which negative labels are sampled. The model, its output order, thresholds
and every accuracy gate are untouched.
"""
import argparse
import concurrent.futures as futures
import json
import multiprocessing
from pathlib import Path
import shutil

import evaluate_calibrated_candidate as v1
from calibrate_word_thresholds import write, sha
from train_motion_residual import batch

REPO = Path(__file__).resolve().parents[2]
BASE = Path('/opt/handspeak-training/single-word-20261010')
WORDS = ['CALL', 'FIND', 'FISH', 'SEE', 'SICK', 'PAIN', 'NIGHT', 'MORNING']

# label -> reason it cannot supply the required held-out negatives
EXCLUDED_NEGATIVES = {
    'SHOWER': ('PopSign v1 test archive contains 19 SHOWER clips from a single signer; '
               '18 are already in knownNames, leaving 1 of the 2 required clips. '
               'See reports/vocabulary-expansion/single-word/heldout-audit-20261017.md'),
}


def configure(word):
    root = BASE / word.lower()
    v1.SOURCE = root / 'frozen'
    v1.ROOT = root / 'fresh-v2'
    v1.REPORT = REPO / 'reports/vocabulary-expansion/single-word' / word.lower() / 'fresh-v2'
    v1.base.ROOT = v1.ROOT
    v1.base.REPORT = v1.REPORT


def freeze():
    """Same as evaluate_calibrated_candidate.freeze, minus the excluded negative labels."""
    if (v1.ROOT / 'protocol.sha256').exists():
        return v1.verify()
    if (v1.ROOT / 'test-manifest.json').exists():
        raise ValueError('Test media preceded model freeze')
    p = json.loads((v1.SOURCE / 'protocol.json').read_text())
    screen = json.loads((v1.SOURCE / 'validation.json').read_text())
    if not screen['passesDevelopmentScreen'] or not all(
            batch.trainer.gate(x['metrics']) for x in screen['framingValidation']):
        raise ValueError('Development screen failed')
    if sha(v1.SOURCE / 'frozen.pt') != p['checkpointSha256'] or sha(p['source']) != p['sourceSha256']:
        raise ValueError('Calibration inputs changed')

    data = json.loads(Path(p['source']).read_text())
    mappings = {}
    for row in data:
        if row['label'] in EXCLUDED_NEGATIVES:
            continue
        if not row['source'].startswith('https://signdata.cc.gatech.edu/data/popsign_v1_0/game/'):
            continue
        url = row['source'].replace('/train/', '/test/').replace('/val/', '/test/')
        if row['label'] in mappings and mappings[row['label']] != url:
            raise ValueError('Ambiguous archive mapping')
        mappings[row['label']] = url
    expected = 57 - len(EXCLUDED_NEGATIVES)
    if len(mappings) != expected or not set(p['labels']) <= set(mappings):
        raise ValueError(f'Unexpected source coverage: {len(mappings)} != {expected}')

    known = {f.name for f in Path('/opt/handspeak-training').rglob('*.mp4') if v1.ROOT not in f.parents}
    hashes = {r['sha256'] for r in data}
    for path in Path('/opt/handspeak-training').rglob('*.json'):
        if v1.ROOT in path.parents or not ('manifest' in path.name or path.name == 'selection.json'):
            continue
        try:
            records = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(records, list):
            continue
        for row in records:
            if not isinstance(row, dict):
                continue
            if row.get('sha256'):
                hashes.add(row['sha256'])
            for key in ('file', 'member'):
                if row.get(key):
                    known.add(Path(row[key]).name)

    scripts = [Path(__file__), Path(v1.__file__), Path(v1.base.__file__),
               Path(v1.calibration.__file__), Path(v1.camera_framing.__file__),
               Path(v1.body_tip_features.__file__), Path(v1.motion_window.__file__),
               Path(v1.extractor.__file__),
               REPO / 'training/catalog/train_motion_residual.py',
               REPO / 'training/catalog/train_expansion_batch.py',
               REPO / 'training/accuracy/temporal.py',
               REPO / 'training/daily_words/train_citizen.py',
               REPO / 'gesture-model.js', REPO / 'motion-model.js']

    p.update(calibrationProtocolSha256=sha(v1.SOURCE / 'protocol.json'),
             calibrationValidationSha256=sha(v1.SOURCE / 'validation.json'),
             implementations={str(f.relative_to(REPO)): sha(f) for f in scripts},
             mappings=mappings, knownNames=sorted(known), knownHashes=sorted(hashes),
             excludedSigners=sorted({str(r['participant']) for r in data}),
             excludedNegativeLabels=sorted(EXCLUDED_NEGATIVES),
             exclusionNotes={k: EXCLUDED_NEGATIVES[k] for k in sorted(EXCLUDED_NEGATIVES)},
             negativeLabelCount=len(mappings) - len(p['labels']),
             targetClipsPerWord=4, negativeClipsPerWord=2, clipsPerSignerCap=2,
             scope=('Fresh recordings from existing held-out signer pool. No newly recruited people, '
                    'ordinary-action or live-camera accuracy claim. SHOWER excluded from the negative '
                    'panel: the archive cannot supply the required 2 clips.'),
             deployed=False)

    v1.ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(v1.SOURCE / 'frozen.pt', v1.ROOT / 'frozen.pt')
    for f in scripts:
        destination = v1.ROOT / 'source-snapshot' / f.relative_to(REPO)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, destination)
    write(v1.ROOT / 'protocol.json', p)
    (v1.ROOT / 'protocol.sha256').write_text(sha(v1.ROOT / 'protocol.json') + '\n')
    write(v1.REPORT / 'protocol.json', {k: v for k, v in p.items()
                                        if k not in ('knownNames', 'knownHashes', 'source', 'implementations')})
    return p


def main(word, freeze_only=False):
    configure(word)
    try:
        v1.status('freeze', state='running')
        p = freeze()
        print(json.dumps(dict(frozen=True, labels=p['labels'], negatives=p['negativeLabelCount'],
                              excluded=p['excludedNegativeLabels'], threshold=p['threshold'])), flush=True)
        if freeze_only:
            return
        v1.status('select-fresh-recordings', state='running')
        if not (v1.ROOT / 'test-manifest.json').exists():
            with futures.ThreadPoolExecutor(max_workers=2) as pool:
                rows = [row for part in pool.map(v1.base.select, [(label, p) for label in p['mappings']])
                        for row in part]
            write(v1.ROOT / 'selection.json', rows)
            v1.verify()
            v1.status('download', state='running', total=len(rows))
            with futures.ThreadPoolExecutor(max_workers=2) as pool:
                rows = list(pool.map(v1.base.download, rows))
            hashes = [r['sha256'] for r in rows]
            if len(set(hashes)) != len(rows) or set(hashes) & set(p['knownHashes']):
                raise ValueError('Previously used/duplicate recording')
            write(v1.ROOT / 'test-manifest.json', rows)

        rows = json.loads((v1.ROOT / 'test-manifest.json').read_text())
        ep = json.loads(Path('/opt/handspeak-training/vocabulary-expansion-dynamic-pose/extraction-protocol.json').read_text())
        write(v1.ROOT / 'extraction-protocol.json', ep)
        (v1.ROOT / 'frames').mkdir(exist_ok=True)
        v1.status('extract', state='running', processed=0, total=len(rows))
        samples = []
        with futures.ProcessPoolExecutor(max_workers=2, mp_context=multiprocessing.get_context('spawn')) as pool:
            for path in pool.map(v1.extractor.extract, [(r, str(v1.ROOT), v1.extractor.protocol_digest(ep)) for r in rows]):
                samples.append(json.loads(Path(path).read_text()))
                v1.status('extract', state='running', processed=len(samples), total=len(rows))

        v1.verify()
        pred = v1.infer(samples, p)
        metrics = v1.base.metrics(samples, pred, p['labels'])
        result = dict(metrics=metrics, passesRecordedClipGate=batch.trainer.gate(metrics),
                      checkpointSha256=p['checkpointSha256'], scope=p['scope'],
                      excludedNegativeLabels=p['excludedNegativeLabels'],
                      negativeLabelCount=p['negativeLabelCount'],
                      deployed=False, readyForDeployment=False,
                      predictions=[dict(expected=r['label'], predicted=v, sha256=r['sha256'])
                                   for r, v in zip(samples, pred)])
        write(v1.ROOT / 'test-results.json', result)
        write(v1.REPORT / 'test-results.json', result)
        v1.status('complete', state='complete', metrics=metrics,
                  passesRecordedClipGate=result['passesRecordedClipGate'])
        print(json.dumps(dict(complete=True, metrics=metrics,
                              passes=result['passesRecordedClipGate'])), flush=True)
    except Exception as error:
        v1.status('failed', state='failed', error=str(error))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--word', required=True, choices=WORDS)
    parser.add_argument('--freeze-only', action='store_true')
    args = parser.parse_args()
    main(args.word, args.freeze_only)
