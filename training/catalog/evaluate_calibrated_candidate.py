"""Freeze calibrated cutoffs, then select new held-out recordings without deployment."""
import concurrent.futures as futures
import json
import multiprocessing
from pathlib import Path
import shutil
import torch
import numpy as np
import evaluate_ready_subset as base
import calibrate_word_thresholds as calibration
import camera_framing
import body_tip_features
import motion_window
import run_dynamic_pose_training as extractor
from train_motion_residual import MotionNet, batch
REPO=Path(__file__).resolve().parents[2]
SOURCE=Path('/opt/handspeak-training/vocabulary-expansion-framing-calibrated')
ROOT=Path('/opt/handspeak-training/vocabulary-expansion-framing-fresh')
REPORT=REPO/'reports/vocabulary-expansion/framing-fresh'
base.ROOT=ROOT;base.REPORT=REPORT
sha=base.sha;write=base.write;status=base.status

def verify():
    p=json.loads((ROOT/'protocol.json').read_text())
    if sha(ROOT/'protocol.json')!=(ROOT/'protocol.sha256').read_text().strip() or sha(ROOT/'frozen.pt')!=p['checkpointSha256']:raise ValueError('Frozen inputs changed')
    if any(sha(REPO/name)!=value for name,value in p['implementations'].items()):raise ValueError('Frozen implementation changed')
    return p

def freeze():
    if (ROOT/'protocol.sha256').exists():return verify()
    if (ROOT/'test-manifest.json').exists():raise ValueError('Test media preceded model freeze')
    p=json.loads((SOURCE/'protocol.json').read_text());screen=json.loads((SOURCE/'validation.json').read_text())
    if not screen['passesDevelopmentScreen'] or not all(batch.trainer.gate(x['metrics']) for x in screen['framingValidation']):raise ValueError('Development screen failed')
    if sha(SOURCE/'frozen.pt')!=p['checkpointSha256'] or sha(p['source'])!=p['sourceSha256']:raise ValueError('Calibration inputs changed')
    data=json.loads(Path(p['source']).read_text());mappings={}
    for row in data:
        if not row['source'].startswith('https://signdata.cc.gatech.edu/data/popsign_v1_0/game/'):continue
        url=row['source'].replace('/train/','/test/').replace('/val/','/test/')
        if row['label'] in mappings and mappings[row['label']]!=url:raise ValueError('Ambiguous archive mapping')
        mappings[row['label']]=url
    if len(mappings)!=57 or not set(p['labels'])<=set(mappings):raise ValueError('Unexpected source coverage')
    known={f.name for f in Path('/opt/handspeak-training').rglob('*.mp4') if ROOT not in f.parents};hashes={r['sha256'] for r in data}
    for path in Path('/opt/handspeak-training').rglob('*.json'):
        if ROOT in path.parents or not ('manifest' in path.name or path.name=='selection.json'):continue
        try:records=json.loads(path.read_text())
        except (OSError,ValueError):continue
        if not isinstance(records,list):continue
        for row in records:
            if not isinstance(row,dict):continue
            if row.get('sha256'):hashes.add(row['sha256'])
            for key in ('file','member'):
                if row.get(key):known.add(Path(row[key]).name)
    scripts=[Path(__file__),Path(base.__file__),Path(calibration.__file__),Path(camera_framing.__file__),Path(body_tip_features.__file__),Path(motion_window.__file__),Path(extractor.__file__),REPO/'training/catalog/train_motion_residual.py',REPO/'training/catalog/train_expansion_batch.py',REPO/'training/accuracy/temporal.py',REPO/'training/daily_words/train_citizen.py',REPO/'gesture-model.js',REPO/'motion-model.js']
    p.update(calibrationProtocolSha256=sha(SOURCE/'protocol.json'),calibrationValidationSha256=sha(SOURCE/'validation.json'),implementations={str(f.relative_to(REPO)):sha(f) for f in scripts},mappings=mappings,knownNames=sorted(known),knownHashes=sorted(hashes),excludedSigners=sorted({str(r['participant']) for r in data}),targetClipsPerWord=4,negativeClipsPerWord=2,clipsPerSignerCap=2,scope='Fresh recordings from existing held-out signer pool. No newly recruited people, ordinary-action or live-camera accuracy claim.',deployed=False)
    ROOT.mkdir(parents=True,exist_ok=True);shutil.copyfile(SOURCE/'frozen.pt',ROOT/'frozen.pt')
    for f in scripts:
        destination=ROOT/'source-snapshot'/f.relative_to(REPO);destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,destination)
    write(ROOT/'protocol.json',p);(ROOT/'protocol.sha256').write_text(sha(ROOT/'protocol.json')+'\n');write(REPORT/'protocol.json',{k:v for k,v in p.items() if k not in ('knownNames','knownHashes','source','implementations')})
    return p

def infer(rows,p):
    saved=torch.load(ROOT/'frozen.pt',weights_only=True)
    if saved['outputLabels']!=p['outputLabels']:raise ValueError('Output order changed')
    inputs=torch.tensor(np.stack([body_tip_features.features(motion_window.align_window(dict(r,body=[None]*len(r['rawFrames'])))) for r in rows]));torch.set_num_threads(1)
    probabilities=[]
    for state in saved['states']:
        model=MotionNet(len(p['outputLabels']),torch.zeros(175),torch.ones(175)).eval();model.load_state_dict(state)
        with torch.no_grad():probabilities.append(model(inputs).softmax(1).numpy())
    return calibration.predictions(rows,np.mean(probabilities,axis=0),p)

def main():
    try:
        status('freeze',state='running');p=freeze();status('select-fresh-recordings',state='running')
        if not (ROOT/'test-manifest.json').exists():
            with futures.ThreadPoolExecutor(max_workers=2) as pool:rows=[row for part in pool.map(base.select,[(label,p) for label in p['mappings']]) for row in part]
            write(ROOT/'selection.json',rows);verify();status('download',state='running',total=len(rows))
            with futures.ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(base.download,rows))
            hashes=[r['sha256'] for r in rows]
            if len(set(hashes))!=len(rows) or set(hashes)&set(p['knownHashes']):raise ValueError('Previously used/duplicate recording')
            write(ROOT/'test-manifest.json',rows)
        rows=json.loads((ROOT/'test-manifest.json').read_text());ep=json.loads(Path('/opt/handspeak-training/vocabulary-expansion-dynamic-pose/extraction-protocol.json').read_text());write(ROOT/'extraction-protocol.json',ep);(ROOT/'frames').mkdir(exist_ok=True)
        status('extract',state='running',processed=0,total=len(rows));samples=[]
        with futures.ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context('spawn')) as pool:
            for path in pool.map(extractor.extract,[(r,str(ROOT),extractor.protocol_digest(ep)) for r in rows]):
                samples.append(json.loads(Path(path).read_text()));status('extract',state='running',processed=len(samples),total=len(rows))
        verify();pred=infer(samples,p);metrics=base.metrics(samples,pred,p['labels'])
        result=dict(metrics=metrics,passesRecordedClipGate=batch.trainer.gate(metrics),checkpointSha256=p['checkpointSha256'],scope=p['scope'],deployed=False,readyForDeployment=False,predictions=[dict(expected=r['label'],predicted=v,sha256=r['sha256']) for r,v in zip(samples,pred)])
        write(ROOT/'test-results.json',result);write(REPORT/'test-results.json',result);status('complete',state='complete',metrics=metrics,passesRecordedClipGate=result['passesRecordedClipGate'])
    except Exception as error:status('failed',state='failed',error=str(error));raise
if __name__=='__main__':main()
