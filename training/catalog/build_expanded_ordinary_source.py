"""Extract reviewed negatives and split ordinary actions into rejection classes."""
import concurrent.futures as futures
import json
import multiprocessing
from pathlib import Path
import run_dynamic_pose_training as extractor
from motion_window import align_window
import calibrate_word_thresholds as common
BASE=Path('/opt/handspeak-training/vocabulary-expansion-ordinary-source')
MEDIA=Path('/opt/handspeak-training/ordinary-training-expanded')
ROOT=Path('/opt/handspeak-training/vocabulary-expansion-split-ordinary-source')
REPORT=Path('/opt/handspeak/repository/reports/vocabulary-expansion/split-ordinary-source')
def status(stage,**extra):
    value=dict(stage=stage,deployed=False,**extra)
    for root in [ROOT,REPORT]:common.write(root/'job-status.json',value)
    print(json.dumps(value),flush=True)
def main():
    try:
        base=json.loads((BASE/'protocol.json').read_text());rows=json.loads((MEDIA/'manifest.json').read_text());review=json.loads((MEDIA/'content-review.json').read_text())
        if common.sha(base['source'])!=base['sourceSha256'] or not review['acceptedForTraining'] or review['manifestSha256']!=common.sha(MEDIA/'manifest.json'):raise ValueError('Source/review changed')
        plan=dict(parentSourceSha256=base['sourceSha256'],manifestSha256=review['manifestSha256'],reviewSha256=common.sha(MEDIA/'content-review.json'),implementationSha256=common.sha(__file__),rule='Original ASL rows unchanged. Existing/new ordinary rows become distinct internal action rejection labels. No test recordings enter training or validation.')
        path=ROOT/'expansion-protocol.json'
        if path.exists() and json.loads(path.read_text())!=plan:raise ValueError('Frozen source expansion changed')
        common.write(path,plan);ep=json.loads(Path('/opt/handspeak-training/vocabulary-expansion-dynamic-pose/extraction-protocol.json').read_text());common.write(ROOT/'extraction-protocol.json',ep);(ROOT/'frames').mkdir(exist_ok=True)
        status('extract',state='running',processed=0,total=len(rows));new=[]
        with futures.ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context('spawn')) as pool:
            for filename in pool.map(extractor.extract,[(r,str(ROOT),extractor.protocol_digest(ep)) for r in rows]):
                row=align_window(json.loads(Path(filename).read_text()));row['body']=[None]*len(row['rawFrames']);new.append(row);status('extract',state='running',processed=len(new),total=len(rows))
        data=json.loads(Path(base['source']).read_text());original_asl=[r for r in data if r['label']!='OTHER MOVEMENT'];known={r['sha256'] for r in data}
        if any(r['sha256'] in known for r in new):raise ValueError('Duplicate new training content')
        data+=new
        for row in data:
            if row['label']=='OTHER MOVEMENT':row['label']='MOVEMENT: '+row['action']
        if [r for r in data if not r['label'].startswith('MOVEMENT: ')]!=original_asl:raise ValueError('ASL rows changed')
        for key in ['sha256','participant']:
            if {str(r[key]) for r in data if r['split']=='train'}&{str(r[key]) for r in data if r['split']=='val'}:raise ValueError('Training/validation overlap')
        if any(r['split'] not in ['train','val'] or any(b is not None for b in r['body']) for r in data):raise ValueError('Wrong partition/body mode')
        destination=ROOT/'development-features.json';common.write(destination,data)
        common.write(ROOT/'protocol.json',dict(source=str(destination),sourceSha256=common.sha(destination),featureMode='hands-only',parentSourceSha256=base['sourceSha256'],rejectionActions=sorted({r['label'] for r in data if r['label'].startswith('MOVEMENT: ')}),trainClips=sum(r['split']=='train' for r in data),validationClips=sum(r['split']=='val' for r in data),ordinaryGrouping='Recording groups, not verified unique persons'))
        status('complete',state='complete',additionalTrain=72,additionalValidation=6,total=len(data))
    except Exception as error:status('failed',state='failed',error=str(error));raise
if __name__=='__main__':main()
