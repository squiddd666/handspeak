"""Expand the first batch using training-only PopSign range downloads.

Selection is checkpointed before downloading. Existing validation is retained,
and official test recordings are never requested. Raw files stay outside webroot.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import tarfile

from train_expansion_batch import LABELS
from dense_extract import extract

ROOT = Path('/opt/handspeak-training/vocabulary-expansion-batch2')
BASE = Path('/opt/handspeak-training/vocabulary-v8/development-features.json')
spec = importlib.util.spec_from_file_location('popsign_requests',
    Path(__file__).resolve().parents[1] / 'accuracy' / 'prepare.py')
requests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(requests)


def select(label):
    path = ROOT / 'selection' / (label + '.json')
    if path.exists():
        return json.loads(path.read_text())
    # Catalog English labels need not equal the dataset's source gloss.
    source_label = {'CALL': 'callonphone'}.get(label, label.lower())
    url = f'https://signdata.cc.gatech.edu/data/popsign_v1_0/game/train/{source_label}.tar'
    rows, signers, offset = [], {}, 0
    for _ in range(3000):
        if len(rows) >= 48:
            break
        header = requests.request(url, offset, 512)
        if header == bytes(512):
            break
        info = tarfile.TarInfo.frombuf(header, 'utf-8', 'replace')
        start = offset + 512
        offset = start + ((info.size + 511) // 512) * 512
        match = re.search(r'4a\.(\d+)', info.name)
        if not info.isfile() or not info.name.endswith('.mp4') or not match:
            continue
        participant = match.group(1)
        if signers.get(participant, 0) >= 2:
            continue
        signers[participant] = signers.get(participant, 0) + 1
        rows.append(dict(label=label, sourceLabel=source_label, split='train',
                         participant=participant, source=url, member=info.name,
                         offset=start, size=info.size, kind='supported',
                         file=str(ROOT / 'videos' / source_label / Path(info.name).name)))
    path.write_text(json.dumps(rows, indent=2) + '\n')
    print('Selected', label, len(rows), 'clips;', len(signers), 'signers', flush=True)
    return rows


def download(row):
    path = Path(row['file'])
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        if shutil.disk_usage(ROOT).free < 5_000_000_000:
            raise RuntimeError('Stopping to retain at least 5GB free space')
        data = requests.request(row['source'], row['offset'], row['size'])
        temp = path.with_suffix('.partial')
        temp.write_bytes(data)
        temp.replace(path)
    if path.stat().st_size != row['size']:
        raise ValueError(f'Incorrect downloaded size: {path}')
    return dict(row, sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def validate_training_rows(rows, base):
    validation_signers = {str(r['participant']) for r in base if r['split'] == 'val'}
    if any(r['split'] != 'train' or '/game/train/' not in r['source'] for r in rows):
        raise ValueError('Additional recordings must come from the official training split')
    if validation_signers & {str(r['participant']) for r in rows}:
        raise ValueError('New training selection overlaps validation signers')


def add_body(row):
    """Center-frame body reference for research; original hand frames preserved."""
    import cv2
    import mediapipe as mp
    global POSE
    cv2.setNumThreads(1)
    if 'POSE' not in globals():
        POSE = mp.solutions.pose.Pose(static_image_mode=True, model_complexity=1,
                                      enable_segmentation=False, min_detection_confidence=.5)
    cache = ROOT / 'body' / (row['sha256'] + '.json')
    cache.parent.mkdir(exist_ok=True)
    if cache.exists():
        points = json.loads(cache.read_text())
    else:
        source = next((row[key] for key in ('processedFile', 'file')
                       if row.get(key) and Path(row[key]).exists()), None)
        if source is None:
            raise FileNotFoundError(f"Missing source video for {row['sha256']}")
        cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG, [cv2.CAP_PROP_N_THREADS, 1])
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) // 2))
        ok, frame = cap.read()
        cap.release()
        if not ok:
            raise ValueError(f'Unable to decode body reference: {source}')
        height, width = frame.shape[:2]
        factor = min(1, 640 / max(height, width))
        rgb = cv2.cvtColor(cv2.resize(frame, (round(width * factor), round(height * factor))), cv2.COLOR_BGR2RGB)
        result = POSE.process(rgb).pose_landmarks
        points = [dict(x=result.landmark[i].x, y=result.landmark[i].y,
                       z=result.landmark[i].z, visibility=result.landmark[i].visibility)
                  for i in (0, 11, 12, 13, 14)] if result else None
        cache.write_text(json.dumps(points))
    return dict(row, body=[points] * len(row['rawFrames']), bodyMode='center-frame reference')


def main(stage, workers=2):
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / 'selection').mkdir(exist_ok=True)
    base = json.loads(BASE.read_text())
    lookup = {(r['source'], r['member']): r for r in base}
    if stage == 'download':
        with ThreadPoolExecutor(max_workers=3) as pool:
            selected = [r for rows in pool.map(select, LABELS) for r in rows]
        validate_training_rows(selected, base)
        # Cached members are reused; target 48 includes previous examples.
        new = [r for r in selected if (r['source'], r['member']) not in lookup]
        (ROOT / 'selection.json').write_text(json.dumps(selected, indent=2) + '\n')
        result = []
        with ThreadPoolExecutor(max_workers=3) as pool:
            for row in pool.map(download, new):
                result.append(row)
                if len(result) % 20 == 0:
                    print('Downloaded', len(result), '/', len(new), flush=True)
        (ROOT / 'additional-manifest.json').write_text(json.dumps(result, indent=2) + '\n')
        print('Additional training downloads complete:', len(result), flush=True)
    elif stage == 'extract':
        rows = json.loads((ROOT / 'additional-manifest.json').read_text())
        validate_training_rows(rows, base)
        result = []
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for row in pool.map(extract, rows):
                result.append(row)
                if len(result) % 10 == 0:
                    print('Extracted', len(result), '/', len(rows), flush=True)
        combined = base + result
        train_hashes = {r['sha256'] for r in combined if r['split'] == 'train'}
        val_hashes = {r['sha256'] for r in combined if r['split'] == 'val'}
        if train_hashes & val_hashes:
            raise ValueError('New training video duplicates validation content')
        # Multiple source members containing identical bytes are one example.
        for row in combined:
            conflicting = {r['label'] for r in combined if r['sha256'] == row['sha256']}
            if len(conflicting) > 1:
                raise ValueError(f"Conflicting labels for recording {row['sha256']}")
        unique = {(r['split'], r['sha256']): r for r in combined}
        if len(unique) != len(combined):
            print('Deduplicated', len(combined) - len(unique), 'recordings', flush=True)
        (ROOT / 'development-features.json').write_text(
            json.dumps(list(unique.values()), separators=(',', ':')))
        print('Complete:', len(unique), 'development clips', flush=True)
    else:
        rows = json.loads((ROOT / 'development-features.json').read_text())
        result = []
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for row in pool.map(add_body, rows):
                result.append(row)
                if len(result) % 50 == 0:
                    print('Body references', len(result), '/', len(rows), flush=True)
        (ROOT / 'body-development-features.json').write_text(json.dumps(result, separators=(',', ':')))
        print('Body extraction complete:', len(result), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['download', 'extract', 'body'], required=True)
    parser.add_argument('--workers', type=int, choices=[1, 2, 3], default=2)
    args = parser.parse_args()
    main(args.stage, args.workers)
