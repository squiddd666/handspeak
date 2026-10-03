"""Resumable dynamic-body extraction, training and verification; never deploys.

Uses only the frozen PopSign development recordings. Keeps the existing hand
detector thresholds and JavaScript sequence-quality rules. Unlike earlier caches,
body references are measured at each actual sampled frame, not copied from one
center frame. Raw recordings and feature caches stay outside the served website.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import fcntl
import hashlib
import json
import multiprocessing
from pathlib import Path
import shutil
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[2]
HAND_MODEL = Path('/opt/handspeak-training/hand_landmarker.task')


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def atomic_json(path, value):
    temp = path.with_suffix(path.suffix + '.partial')
    with temp.open('w') as stream:
        json.dump(value, stream, separators=(',', ':'))
    temp.replace(path)


def protocol_digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def extract(task):
    row, root_string, protocol_hash = task
    root = Path(root_string)
    protocol = json.loads((root/'extraction-protocol.json').read_text())
    if protocol_digest(protocol) != protocol_hash:
        raise ValueError('Frozen extraction protocol changed')
    if digest(__file__) != protocol['implementationSha256'] or any(digest(REPO/name) != sha for name,sha in protocol['encoders'].items()):
        raise ValueError('Extraction implementation changed while the job was running')
    if digest(row['file']) != row['sha256']:
        raise ValueError('Recording differs from its frozen hash')
    cache = root / 'frames' / (row['sha256'] + '.json')
    if cache.exists():
        result = json.loads(cache.read_text())
        if result.get('extractionProtocolSha256') != protocol_hash or result['sha256'] != row['sha256']:
            raise ValueError('Cached extraction protocol differs')
        if any(result.get(key) != row.get(key) for key in ('label','split','participant')):
            raise ValueError('Cached recording identity differs')
        if not (len(result['rawFrames']) == len(result['body']) == len(result['timestamps'])):
            raise ValueError('Cached hand/body frames are not aligned')
        return str(cache)
    if shutil.disk_usage(root).free < 5_000_000_000:
        raise RuntimeError('Extraction stopped to retain 5 GB free space')
    import cv2
    import mediapipe as mp
    import numpy as np
    import quickjs
    cv2.setNumThreads(1)
    js = quickjs.Context()
    for name in ('gesture-model.js', 'motion-model.js'):
        js.eval((REPO / name).read_text().replace('export ', ''))
    cap = cv2.VideoCapture(row['file'], cv2.CAP_FFMPEG, [cv2.CAP_PROP_N_THREADS, 1])
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); fps = cap.get(cv2.CAP_PROP_FPS)
    if count <= 0 or not np.isfinite(fps) or fps <= 0:
        raise ValueError('Missing recording frame count or frame rate')
    selected = set(np.unique(np.linspace(0, count - 1, 60).astype(int)))
    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(HAND_MODEL)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, num_hands=2,
        min_hand_detection_confidence=.65, min_hand_presence_confidence=.65,
        min_tracking_confidence=.6)
    frames, bodies, timestamps = [], [], []
    started = time.monotonic()
    try:
        with mp.tasks.vision.HandLandmarker.create_from_options(options) as hands, \
                mp.solutions.pose.Pose(static_image_mode=False, model_complexity=1,
                                      enable_segmentation=False, min_detection_confidence=.5,
                                      min_tracking_confidence=.5) as pose:
            for index in range(count):
                if not cap.grab():
                    raise ValueError('Recording ended before its declared frame count')
                if index not in selected:
                    continue
                ok, bgr = cap.retrieve()
                if not ok:
                    raise ValueError('Selected frame did not decode')
                height, width = bgr.shape[:2]; aspect = height / width
                factor = min(1, 640 / max(height, width))
                rgb = cv2.cvtColor(cv2.resize(bgr, (round(width * factor), round(height * factor))), cv2.COLOR_BGR2RGB)
                timestamp = round(index / fps * 1000)
                detection = hands.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp)
                data = dict(landmarks=[[dict(x=p.x, y=p.y, z=p.z) for p in h] for h in detection.hand_landmarks],
                            handedness=[[dict(categoryName=c.category_name) for c in h] for h in detection.handedness])
                js.eval('var d=' + json.dumps(data) + ';')
                frame = json.loads(js.eval('JSON.stringify(motionFrame({landmarks:d.landmarks.filter(isUsableHand),handedness:d.handedness.filter((_,i)=>isUsableHand(d.landmarks[i]))}))'))
                landmarks = pose.process(rgb).pose_landmarks
                body = [dict(x=landmarks.landmark[i].x, y=landmarks.landmark[i].y,
                             z=landmarks.landmark[i].z, visibility=landmarks.landmark[i].visibility)
                        for i in (0, 11, 12, 13, 14)] if landmarks else None
                frames.append(frame); bodies.append(body); timestamps.append(timestamp)
    finally:
        cap.release()
    sequence = json.loads(js.eval('JSON.stringify(encodeMotion(' + json.dumps(frames) + ',' + str(aspect) + '))'))
    if sequence is not None:
        sequence = np.round(sequence, 5).tolist()
    result = dict(row, rawFrames=frames, body=bodies, timestamps=timestamps,
                  sequence=sequence, imageAspect=aspect, frames=len(frames),
                  trackedFrames=sum(any(f) for f in frames), bodyMode='per-frame pose',
                  extractionProtocolSha256=protocol_hash, extractionSeconds=time.monotonic()-started,
                  frameOrigin='original source video')
    atomic_json(cache, result)
    return str(cache)


def run_command(root, name, arguments):
    with (root / (name + '.log')).open('a') as log:
        subprocess.run([sys.executable, *arguments], cwd=REPO, stdout=log, stderr=subprocess.STDOUT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--workers', type=int, choices=(1, 2, 3), default=2)
    args = parser.parse_args()
    root = args.output.resolve()
    if root.is_relative_to(REPO) or root.is_relative_to(Path('/opt/handspeak/releases').resolve()):
        raise ValueError('Raw training artifacts must remain outside the website and repository')
    root.mkdir(parents=True, exist_ok=True)
    lock = (root / '.job.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    baseline = json.loads((args.baseline / 'protocol.json').read_text())
    source = Path(baseline['source'])
    if digest(source) != baseline['sourceSha256']:
        raise ValueError('Baseline development input changed')
    import mediapipe as mp
    import cv2
    extraction_protocol = dict(source=str(source), sourceSha256=baseline['sourceSha256'],
        implementationSha256=digest(__file__), handModelSha256=digest(HAND_MODEL),
        encoders={name: digest(REPO/name) for name in ('gesture-model.js','motion-model.js')},
        mediapipe=mp.__version__, opencv=cv2.__version__,
        poseModels={str(p.relative_to(Path(mp.__file__).parent)):digest(p)
                    for folder in ('pose_landmark','pose_detection')
                    for p in (Path(mp.__file__).parent/'modules'/folder).glob('*.tflite')},
        trainingImplementations={name:digest(REPO/name) for name in (
            'training/catalog/train_motion_residual.py','training/catalog/body_tip_features.py',
            'training/catalog/train_expansion_batch.py','training/daily_words/train_citizen.py',
            'training/catalog/motion_window.py',
            'training/accuracy/temporal.py','training/catalog/check_residual_browser.py',
            'training/accuracy/temporal-browser.js','training/accuracy/motion-residual-browser.js')},
        sampledFrames=60, maxImageSide=640, handDetection=.65, handPresence=.65,
        handTracking=.6, poseDetection=.5, poseTracking=.5, bodyMode='per-frame pose',
        labels=baseline['labels'], independentTestOpened=False, deployed=False)
    extraction_protocol['datasetFeatureWindow']='Browser-compatible visible run, preserving the encoder quality decision'
    protocol_path = root / 'extraction-protocol.json'
    if protocol_path.exists() and json.loads(protocol_path.read_text()) != extraction_protocol:
        raise ValueError('Frozen extraction configuration changed')
    atomic_json(protocol_path, extraction_protocol)
    protocol_hash = protocol_digest(extraction_protocol)
    (root/'implementation-snapshot.py').write_bytes(Path(__file__).read_bytes())
    for name in set(extraction_protocol['encoders']) | set(extraction_protocol['trainingImplementations']):
        destination=root/'source-snapshot'/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(REPO/name,destination)
    rows = json.loads(source.read_text())
    if any(r['split'] not in ('train','val') for r in rows):
        raise ValueError('Only development recordings are allowed')
    for key in ('participant','sha256'):
        if {r[key] for r in rows if r['split']=='train'} & {r[key] for r in rows if r['split']=='val'}:
            raise ValueError('Training/validation overlap: '+key)
    if len({r['sha256'] for r in rows}) != len(rows):
        raise ValueError('Duplicate recordings')
    removed = {'rawFrames','body','sequence','processedFile','processedSha256','recoveryFile','recoverySha256'}
    rows = [dict({k:v for k,v in r.items() if k not in removed}, legacySequenceUsable=r.get('sequence') is not None) for r in rows]
    (root/'frames').mkdir(exist_ok=True)
    status = dict(state='running',stage='extract',total=len(rows),processed=0,deployed=False,independentAccuracyPassed=False)
    atomic_json(root/'job-status.json',status)
    try:
        files=[]
        with ProcessPoolExecutor(max_workers=args.workers, mp_context=multiprocessing.get_context('spawn')) as pool:
            for file in pool.map(extract, ((r,str(root),protocol_hash) for r in rows)):
                files.append(file);status['processed']=len(files)
                atomic_json(root/'job-status.json',status)
                if len(files)%20==0:print(f'Extracted {len(files)}/{len(rows)}',flush=True)
        if any(digest(REPO/name)!=sha for name,sha in extraction_protocol['trainingImplementations'].items()):
            raise ValueError('Training implementation changed during extraction')
        from motion_window import align_window
        data=[align_window(json.loads(Path(file).read_text())) for file in files]
        data_path=root/'development-features.json'; atomic_json(data_path,data)
        coverage=dict(total=len(data),usable=sum(r['sequence'] is not None for r in data),
            recovered=sum(not r['legacySequenceUsable'] and r['sequence'] is not None for r in data),
            newlyRejected=sum(r['legacySequenceUsable'] and r['sequence'] is None for r in data),
            bodyFrames=sum(sum(p is not None for p in r['body']) for r in data),
            featureFrames=sum(len(r['rawFrames']) for r in data),
            featureWindow=extraction_protocol['datasetFeatureWindow'],
            sourceSha256=digest(data_path), independentTestOpened=False,deployed=False)
        atomic_json(root/'coverage.json',coverage)
        del data
        if any(digest(REPO/name)!=sha for name,sha in extraction_protocol['trainingImplementations'].items()):
            raise ValueError('Training implementation changed during extraction')
        import train_expansion_batch as batch
        batch.prepare(data_path,root,labels=baseline['labels'],separate_negatives=True)
        status['stage']='train';atomic_json(root/'job-status.json',status)
        run_command(root,'train',['training/catalog/train_motion_residual.py','--baseline',str(root),
            '--output',str(root),'--report',str(args.report),'--body-tips'])
        status['stage']='browser-parity';atomic_json(root/'job-status.json',status)
        run_command(root,'browser',['training/catalog/check_residual_browser.py','--experiment',str(root),'--report',str(args.report)])
        result=json.loads((root/'validation.json').read_text())
        if any(digest(REPO/name)!=sha for name,sha in extraction_protocol['trainingImplementations'].items()):
            raise ValueError('Training or verification implementation changed during the run')
        status.update(state='complete',stage='complete',passesValidation=result['passesValidation'],
                      validation=result['selected']['validation'],
                      nextStep='Independent evaluation and live-camera integration still required.' if result['passesValidation'] else 'Accuracy screen failed; candidate must not be deployed.')
        args.report.mkdir(parents=True,exist_ok=True)
        for name in ('extraction-protocol.json','coverage.json'):
            shutil.copyfile(root/name,args.report/name)
    except Exception as error:
        status.update(state='failed',error=str(error))
        atomic_json(root/'job-status.json',status)
        raise
    atomic_json(root/'job-status.json',status)
    atomic_json(args.report/'job-status.json',status)
    print(json.dumps(status),flush=True)


if __name__=='__main__':main()
