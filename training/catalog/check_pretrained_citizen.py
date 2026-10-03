"""Private development pilot of Microsoft's released ASL Citizen ST-GCN.

No training, public export, or reserved test data. Exact gloss mappings only.
Source/weights must first be downloaded and inspected into the private root.
"""
import argparse
import csv
import hashlib
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path('/opt/handspeak-training/pretrained-asl-citizen')
EDGES = [[2,0],[1,0],[0,3],[0,4],[3,5],[4,6],[5,7],[6,17],[7,8],[7,9],
         [9,10],[7,11],[11,12],[7,13],[13,14],[7,15],[15,16],[17,18],[17,19],
         [19,20],[17,21],[21,22],[17,23],[23,24],[17,25],[25,26]]
KEYPOINTS = [0,2,5,11,12,13,14,33,37,38,41,42,45,46,49,50,53,54,58,59,62,63,66,67,70,71,74]


def encode(data):
    """Match official downsampling, padding, shoulder normalization and hand order."""
    data = np.asarray(data, dtype=np.float64)
    if len(data) > 128:
        increment = 128 / len(data); current = 0.; count = 0; chosen = []
        for frame in data:
            current += increment
            if current > count:
                count += 1; chosen.append(frame)
        data = np.array(chosen[:128])
    if len(data) < 128:
        data = np.pad(data, ((0,128-len(data)),(0,0),(0,0)))
    left, right = data[:,11,:], data[:,12,:]
    center = ((right + left) / 2).mean(0)
    distance = np.sqrt(((left-right)**2).sum(-1)).mean()
    if distance:
        data = (data-center) / distance
    # Extraction stores pose, right hand, left hand; official graph swaps hands.
    data = np.concatenate([data[:,:33], data[:,54:75], data[:,33:54]], axis=1)
    return data[:,KEYPOINTS].transpose(2,0,1)


def extract(row):
    import cv2
    import mediapipe as mp
    cv2.setNumThreads(1)
    path = Path(row['file'])
    if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
        raise ValueError('Source recording hash mismatch')
    cache = ROOT / 'pilot-poses' / (row['sha256'] + '.npz')
    if cache.exists():
        with np.load(cache, allow_pickle=False) as saved:
            return row['sha256'], saved['features'], int(saved['frames']), float(saved['seconds'])
    cap = cv2.VideoCapture(str(path), cv2.CAP_FFMPEG, [cv2.CAP_PROP_N_THREADS,1])
    frames = []; started = time.monotonic()
    with mp.solutions.holistic.Holistic(static_image_mode=False, min_detection_confidence=.5) as model:
        while True:
            ok, bgr = cap.read()
            if not ok:
                break
            h,w = bgr.shape[:2]; factor = min(1,640/max(h,w))
            rgb = cv2.cvtColor(cv2.resize(bgr,(round(w*factor),round(h*factor))),cv2.COLOR_BGR2RGB)
            result = model.process(rgb)
            data = np.zeros((75,2),np.float64)
            for offset, points in [(0,result.pose_landmarks),(33,result.right_hand_landmarks),(54,result.left_hand_landmarks)]:
                if points:
                    for i, point in enumerate(points.landmark):
                        data[offset+i] = [point.x,point.y]
            frames.append(data)
            if len(frames) > 2000:
                raise ValueError('Unexpectedly long pilot clip')
    cap.release()
    if not frames:
        raise ValueError('Video did not decode')
    features = encode(np.array(frames)); elapsed = time.monotonic()-started
    with cache.with_suffix('.partial').open('wb') as stream:
        np.savez_compressed(stream,features=features,frames=len(frames),seconds=elapsed)
    cache.with_suffix('.partial').replace(cache)
    return row['sha256'],features,len(frames),elapsed


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--workers',type=int,default=1,choices=[1,2])
    args=p.parse_args()
    protocol=json.loads((args.baseline/'protocol.json').read_text())
    source=Path(protocol['source'])
    if hashlib.sha256(source.read_bytes()).hexdigest()!=protocol['sourceSha256']:
        raise ValueError('Frozen development source changed')
    rows=json.loads(source.read_text())
    if any(r['split'] not in ('train','val') for r in rows):
        raise ValueError('Only development rows are allowed')
    selected={}
    for row in rows:
        if row['split']=='val':selected.setdefault(row['label'],row)
    selected=list(selected.values())
    for row in selected:
        if '/game/val/' not in row['source']:
            raise ValueError('Pilot must use official validation sources only')
    metadata=Path('/opt/handspeak-training/daily-words/metadata/ASL_Citizen/splits/train.csv')
    with metadata.open() as stream:
        labels=sorted({r['Gloss'].strip() for r in csv.DictReader(stream)})
    checkpoint=ROOT/'model.pt'; source_root=ROOT/'source'; manifest=json.loads((source_root/'source-manifest.json').read_text())
    for entry in manifest['files']:
        if hashlib.sha256((source_root/entry['path']).read_bytes()).hexdigest()!=entry['sha256']:
            raise ValueError('Reviewed upstream source changed')
    frozen=dict(sourceSha256=protocol['sourceSha256'],checkpointSha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                metadataSha256=hashlib.sha256(metadata.read_bytes()).hexdigest(),upstreamRevision=manifest['revision'],
                implementationSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                selection=[dict(label=r['label'],sha256=r['sha256']) for r in selected],
                targetLabels=protocol['labels'], outputClasses=len(labels), threshold=.5,margin=.2,
                extraction='Every original frame, max side 640, MediaPipe Holistic default complexity and detection 0.5. Pose and hands only; face points not retained.',
                limitations=['One deterministic validation recording per source label; diagnostic only, not a release screen.',
                'Pretrained population overlap with PopSign is unverified. No independent accuracy claim.',
                'Exact gloss matches only; unmapped target labels remain misses. No guessed variant/synonym mapping.',
                'Keep existing sequence-quality rejection for comparison. Not a live detector integration.',
                'Source code MIT; dataset has separate research terms. No public deployment or redistribution authorization is asserted.'])
    frozen_path=ROOT/'pilot-protocol.json'
    if frozen_path.exists() and json.loads(frozen_path.read_text())!=frozen:
        raise ValueError('Pilot protocol changed')
    frozen_path.write_text(json.dumps(frozen,indent=2)+'\n')
    (ROOT/'pilot-poses').mkdir(exist_ok=True)
    results={}
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for sha,features,count,elapsed in pool.map(extract,selected):
            results[sha]=(features,count,elapsed)
            print(f'Extracted {len(results)}/{len(selected)} pilot recordings',flush=True)
    import torch
    sys.path.insert(0,str(source_root/'ST-GCN'))
    from architecture.st_gcn import STGCN
    from architecture.fc import FC
    from architecture.network import Network
    torch.set_num_threads(2)
    model=Network(STGCN(2,dict(num_nodes=27,center=0,inward_edges=EDGES),True),FC(256,len(labels),dropout_ratio=.05)).double().eval()
    model.load_state_dict(torch.load(checkpoint,map_location='cpu',weights_only=True))
    predictions=[]
    for row in selected:
        started=time.monotonic()
        with torch.no_grad():
            probabilities=model(torch.tensor(results[row['sha256']][0][None])).softmax(1)[0].numpy()
        order=np.argsort(probabilities)[::-1]; best=int(order[0]); name=labels[best]
        accepted=name if name in protocol['labels'] and row.get('sequence') is not None and probabilities[best]>=.5 and probabilities[best]-probabilities[order[1]]>=.2 else None
        predictions.append(dict(expected=row['label'],sha256=row['sha256'],rawTop1=name,predicted=accepted,
                                top5=[labels[i] for i in order[:5]],inferenceMs=(time.monotonic()-started)*1000,
                                exactMappingAvailable=row['label'] in labels))
    targets=[r for r in predictions if r['expected'] in protocol['labels']]
    negatives=[r for r in predictions if r['expected'] not in protocol['labels']]
    result=dict(targets=len(targets),rawTop1Correct=sum(r['rawTop1']==r['expected'] for r in targets),
                correct=sum(r['predicted']==r['expected'] for r in targets),
                wrong=sum(r['predicted'] is not None and r['predicted']!=r['expected'] for r in targets),
                negativeFalse=sum(r['predicted'] is not None for r in negatives),negativeTotal=len(negatives),
                unmappedTargets=[r['expected'] for r in targets if not r['exactMappingAvailable']],
                predictions=predictions,protocol=frozen,passesRelease=False,deployed=False)
    args.report.mkdir(parents=True,exist_ok=True)
    (args.report/'pilot.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('predictions','protocol')}),flush=True)


if __name__=='__main__':main()
