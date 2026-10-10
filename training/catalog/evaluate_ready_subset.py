"""Freeze a development-selected subset and test fresh recordings once; never deploy."""
import concurrent.futures as futures
import argparse
import hashlib
import http.client
import json
import multiprocessing
from pathlib import Path
import re
import shutil
import tarfile
from urllib.parse import urlsplit

import numpy as np
import torch
from train_motion_residual import MotionNet, batch
import body_tip_features
import motion_window
import run_dynamic_pose_training as extractor

REPO = Path(__file__).resolve().parents[2]
ROOT = Path('/opt/handspeak-training/vocabulary-expansion-ready-fresh-v2')
SOURCE = Path('/opt/handspeak-training/vocabulary-expansion-masked-augmentation')
REPORT = REPO / 'reports/vocabulary-expansion/ready-fresh'
SELECT_FROM_VALIDATION = False
SELECTED_LABELS_FILE = None


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.partial')
    temp.write_text(json.dumps(value, indent=2) + '\n'); temp.replace(path)


def status(stage, **extra):
    value = dict(stage=stage, deployed=False, **extra)
    for root in (ROOT, REPORT):
        write(root / 'job-status.json', value)
    print(json.dumps(value), flush=True)


def predict(rows, probs, protocol):
    order = np.argsort(probs, axis=1)
    output = []
    for row, scores, ranked in zip(rows, probs, order):
        winner, second = ranked[-1], ranked[-2]
        label = protocol['outputLabels'][winner]
        output.append(label if label in protocol['labels'] and row.get('sequence') is not None
                      and scores[winner] >= protocol['threshold']
                      and scores[winner] - scores[second] >= protocol['margin'] else None)
    return output


def infer(rows, protocol):
    saved = torch.load(ROOT / 'frozen.pt', weights_only=True)
    if saved['outputLabels'] != protocol['outputLabels']:
        raise ValueError('Checkpoint output order differs')
    x = torch.tensor(np.stack([body_tip_features.features(r) for r in rows]))
    probs = []
    torch.set_num_threads(1)
    for state in saved['states']:
        net = MotionNet(len(protocol['outputLabels']), torch.zeros(175), torch.ones(175)).eval()
        net.load_state_dict(state)
        with torch.no_grad():
            probs.append(net(x).softmax(1).numpy())
    return predict(rows, np.mean(probs, axis=0), protocol)


def metrics(rows, predictions, labels):
    batch.trainer.LABELS = labels
    return batch.trainer.metrics(rows, predictions)


def verify():
    p = json.loads((ROOT / 'protocol.json').read_text())
    if sha(ROOT / 'protocol.json') != (ROOT / 'protocol.sha256').read_text().strip():
        raise ValueError('Frozen protocol changed')
    if sha(ROOT / 'frozen.pt') != p['checkpointSha256']:
        raise ValueError('Frozen checkpoint changed')
    if any(sha(REPO / name) != digest for name, digest in p['implementations'].items()):
        raise ValueError('Frozen evaluation implementation changed')
    if not batch.trainer.gate(json.loads((ROOT / 'validation.json').read_text())):
        raise ValueError('Subset failed development screen')
    return p


def freeze():
    if (ROOT / 'protocol.sha256').exists():
        return verify()
    if (ROOT / 'test-manifest.json').exists():
        raise ValueError('Test media already opened before freeze')
    base = json.loads((SOURCE / 'protocol.json').read_text())
    if sha(base['source']) != base['sourceSha256']:
        raise ValueError('Development source changed')
    data = json.loads(Path(base['source']).read_text())
    result = json.loads((SOURCE / 'validation.json').read_text())
    if SELECTED_LABELS_FILE:
        accepted_labels = json.loads(SELECTED_LABELS_FILE.read_text())
    elif SELECT_FROM_VALIDATION:
        wrong_labels = {r['predicted'] for r in result['errors'] if r['predicted'] is not None}
        accepted_labels = [label for label, counts in result['selected']['validation']['perWord'].items()
                           if counts['correct'] >= .75 * counts['total'] and label not in wrong_labels]
    else:
        accepted_labels = json.loads((REPO / 'reports/vocabulary-expansion/release-readiness/audit.json').read_text())['promising']
    if not accepted_labels:
        raise ValueError('No eligible development-selected labels')
    if len(set(accepted_labels)) != len(accepted_labels) or any(label not in base['labels'] for label in accepted_labels):
        raise ValueError('Accepted labels must be a unique subset of the original targets')
    if sha(SOURCE / 'motion-private.pt') != result['checkpointSha256']:
        raise ValueError('Source checkpoint changed')
    scripts = [Path(__file__), Path(body_tip_features.__file__), Path(motion_window.__file__),
               Path(extractor.__file__), REPO / 'training/catalog/train_motion_residual.py',
               REPO / 'training/catalog/train_expansion_batch.py',
               REPO / 'training/daily_words/train_citizen.py', REPO / 'training/accuracy/temporal.py',
               REPO / 'gesture-model.js', REPO / 'motion-model.js']
    mappings = {}
    for row in data:
        url = row['source'].replace('/train/', '/test/').replace('/val/', '/test/')
        if row['label'] in mappings and mappings[row['label']] != url:
            raise ValueError('Ambiguous source mapping')
        mappings[row['label']] = url
    known = {p.name for p in Path('/opt/handspeak-training').rglob('*.mp4') if ROOT not in p.parents}
    prior_hashes = {r['sha256'] for r in data}
    for path in Path('/opt/handspeak-training').rglob('*.json'):
        if ROOT in path.parents or not ('manifest' in path.name or path.name == 'selection.json'):
            continue
        try:
            records = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(records, list):
            for row in records:
                if not isinstance(row, dict): continue
                if row.get('sha256'): prior_hashes.add(row['sha256'])
                for key in ('file', 'member'):
                    if row.get(key): known.add(Path(row[key]).name)
    p = dict(labels=accepted_labels, outputLabels=base['outputLabels'],
             selectionReportSha256=sha(SOURCE / 'validation.json'),
             selectionRule=('Explicit development shortlist; new independent recordings required' if SELECTED_LABELS_FILE
                            else 'Reused validation: at least 75% per word and no incoming false suggestion'),
             selectedLabelsFileSha256=sha(SELECTED_LABELS_FILE) if SELECTED_LABELS_FILE else None,
             threshold=result['selected']['threshold'], margin=result['selected']['margin'],
             checkpointSha256=result['checkpointSha256'], developmentSha256=base['sourceSha256'],
             implementations={str(path.relative_to(REPO)): sha(path) for path in scripts},
             mappings=mappings, knownNames=sorted(known), knownHashes=sorted(prior_hashes),
             excludedSigners=sorted({str(r['participant']) for r in data}),
             targetClipsPerWord=4, negativeClipsPerWord=2, clipsPerSignerCap=2,
             scope='Fresh recordings from existing held-out signer pool; not newly recruited people, ordinary movements, continuous signing or webcam accuracy')
    ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE / 'motion-private.pt', ROOT / 'frozen.pt')
    rows = [r for r in data if r['split'] == 'val']
    m = metrics(rows, infer(rows, p), p['labels'])
    write(ROOT / 'validation.json', m)
    if not batch.trainer.gate(m):
        raise ValueError('Subset failed unchanged development gate')
    for path in scripts:
        dest = ROOT / 'source-snapshot' / path.relative_to(REPO)
        dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, dest)
    write(ROOT / 'protocol.json', p)
    (ROOT / 'protocol.sha256').write_text(sha(ROOT / 'protocol.json') + '\n')
    write(REPORT / 'development-screen.json', m)
    return p


def request(url, offset, size):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.netloc != 'signdata.cc.gatech.edu' or not parsed.path.startswith('/data/popsign_v1_0/game/test/'):
        raise ValueError('Only official held-out archive allowed')
    connection = http.client.HTTPSConnection(parsed.netloc, timeout=30)
    try:
        connection.request('GET', parsed.path, headers={'Range': f'bytes={offset}-{offset+size-1}'})
        response = connection.getresponse()
        match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.getheader('Content-Range', ''))
        if response.status != 206 or not match or tuple(map(int, match.groups()[:2])) != (offset, offset+size-1):
            raise ValueError('Incorrect range response')
        data = response.read(size+1)
        if len(data) != size: raise ValueError('Incomplete range')
        return data
    finally:
        connection.close()


def select(job):
    label, p = job
    wanted = p['targetClipsPerWord'] if label in p['labels'] else p['negativeClipsPerWord']
    rows = []; counts = {}; offset = 0
    for _ in range(3000):
        header = request(p['mappings'][label], offset, 512)
        if header == bytes(512): break
        info = tarfile.TarInfo.frombuf(header, 'utf-8', 'replace')
        if info.size < 0: raise ValueError('Invalid tar size')
        start = offset+512; offset = start+((info.size+511)//512)*512
        match = re.search(r'4a\.(\d+)', info.name)
        if not info.isfile() or not info.name.endswith('.mp4') or not match: continue
        signer = match.group(1)
        if Path(info.name).name in p['knownNames'] or signer in p['excludedSigners'] or counts.get(signer, 0) >= p['clipsPerSignerCap']: continue
        counts[signer] = counts.get(signer, 0) + 1
        rows.append(dict(label=label, split='test', participant=signer, source=p['mappings'][label],
                         member=info.name, offset=start, size=info.size,
                         file=str(ROOT/'videos'/label/Path(info.name).name)))
        if len(rows) == wanted: break
    if len(rows) != wanted: raise ValueError(f'Insufficient held-out recordings for {label}: {len(rows)}/{wanted}')
    return rows


def download(row):
    if shutil.disk_usage(ROOT).free < 5_000_000_000: raise ValueError('Retain 5GB free space')
    path = Path(row['file']); path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temp = path.with_suffix('.partial'); temp.write_bytes(request(row['source'], row['offset'], row['size'])); temp.replace(path)
    return dict(row, sha256=sha(path))


def main():
    try:
        status('freeze', state='running')
        p = freeze()
        status('select-fresh-recordings', state='running')
        if not (ROOT/'test-manifest.json').exists():
            with futures.ThreadPoolExecutor(max_workers=2) as pool:
                rows = [row for part in pool.map(select, [(label,p) for label in p['outputLabels']]) for row in part]
            write(ROOT/'selection.json', rows)
            verify()
            status('download', state='running', total=len(rows))
            with futures.ThreadPoolExecutor(max_workers=2) as pool: rows=list(pool.map(download,rows))
            hashes = [r['sha256'] for r in rows]
            if len(set(hashes)) != len(rows) or set(hashes) & set(p['knownHashes']): raise ValueError('Duplicate or previously used content')
            write(ROOT/'test-manifest.json', rows)
        rows=json.loads((ROOT/'test-manifest.json').read_text())
        ep=json.loads(Path('/opt/handspeak-training/vocabulary-expansion-dynamic-pose/extraction-protocol.json').read_text())
        write(ROOT/'extraction-protocol.json', ep)
        (ROOT/'frames').mkdir(parents=True, exist_ok=True)
        status('extract', state='running', processed=0, total=len(rows))
        samples=[]
        with futures.ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context('spawn')) as pool:
            for path in pool.map(extractor.extract,[(r,str(ROOT),extractor.protocol_digest(ep)) for r in rows]):
                samples.append(motion_window.align_window(json.loads(Path(path).read_text())))
                status('extract',state='running',processed=len(samples),total=len(rows))
        verify()
        predictions=infer(samples,p); m=metrics(samples,predictions,p['labels'])
        result=dict(metrics=m,passesRecordedClipGate=batch.trainer.gate(m),deployed=False,
                    readyForDeployment=False,scope=p['scope'],checkpointSha256=p['checkpointSha256'],
                    predictions=[dict(sha256=r['sha256'],expected=r['label'],predicted=v) for r,v in zip(samples,predictions)])
        write(ROOT/'test-results.json', result);write(REPORT/'test-results.json',result)
        status('complete',state='complete',metrics=m,passesRecordedClipGate=result['passesRecordedClipGate'],
               nextStep='Integration and real-time/ordinary-movement tests still required' if result['passesRecordedClipGate'] else 'Candidate failed; no deployment')
    except Exception as exc:
        status('failed',state='failed',error=str(exc)); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--output', type=Path, default=ROOT)
    parser.add_argument('--report', type=Path, default=REPORT)
    parser.add_argument('--select-from-validation', action='store_true')
    parser.add_argument('--labels-file', type=Path)
    args = parser.parse_args()
    SOURCE, ROOT, REPORT = args.source.resolve(), args.output.resolve(), args.report.resolve()
    if ROOT.is_relative_to(REPO) or ROOT.is_relative_to(Path('/opt/handspeak/releases')):
        raise ValueError('Test recordings and checkpoints must remain outside the website')
    SELECT_FROM_VALIDATION = args.select_from_validation
    SELECTED_LABELS_FILE = args.labels_file.resolve() if args.labels_file else None
    main()
