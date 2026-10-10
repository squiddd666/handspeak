"""Add development-only ordinary subwindows, then train with unchanged gates."""
import json
from pathlib import Path
import quickjs
from ordinary_windows import window_rows
from motion_window import align_window
from calibrate_word_thresholds import sha, write
import train_split_ordinary_rejection as trainer
REPO=Path(__file__).resolve().parents[2]
BASE=Path('/opt/handspeak-training/vocabulary-expansion-split-ordinary-source')
SOURCE=Path('/opt/handspeak-training/vocabulary-expansion-windowed-ordinary-source')
ROOT=Path('/opt/handspeak-training/vocabulary-expansion-windowed-ordinary-rejection')
REPORT=REPO/'reports/vocabulary-expansion/windowed-ordinary-rejection'


def main():
    if (SOURCE/'protocol.json').exists():
        raise ValueError('Frozen experiment exists; do not overwrite it')
    p=json.loads((BASE/'protocol.json').read_text())
    if sha(p['source'])!=p['sourceSha256']:
        raise ValueError('Parent source changed')
    data=json.loads(Path(p['source']).read_text())
    if any(r['split'] not in ('train','val') for r in data):
        raise ValueError('Development only')
    original_asl=[r for r in data if not r['label'].startswith('MOVEMENT: ')]
    plan=dict(parentSourceSha256=p['sourceSha256'],windowMs=3000,maxWindowsPerClip=4,
              originalRowsRetained=True,selection='Equally spaced starts, determined by timestamps only. No predictions or test recordings used.',
              scope='Cached detector frames; no interpolated or duplicated frames. Windows from one clip are correlated, not independent recordings. Existing train/validation partitions unchanged.',
              implementations={str(f):sha(f) for f in [Path(__file__),Path(__file__).with_name('ordinary_windows.py'),Path(trainer.__file__),REPO/'gesture-model.js',REPO/'motion-model.js']})
    write(SOURCE/'window-plan.json',plan)
    js=quickjs.Context()
    for name in ('gesture-model.js','motion-model.js'):
        js.eval((REPO/name).read_text().replace('export ',''))
    additions=[]
    for row in data:
        if not row['label'].startswith('MOVEMENT: '):continue
        for window in window_rows(row):
            window['sequence']=json.loads(js.eval('JSON.stringify(encodeMotion('+json.dumps(window['rawFrames'])+','+str(window['imageAspect'])+'))'))
            additions.append(align_window(window))
    combined=data+additions
    for key in ('participant','sha256'):
        if {str(r[key]) for r in combined if r['split']=='train'} & {str(r[key]) for r in combined if r['split']=='val'}:
            raise ValueError('Split overlap')
    if [r for r in combined if not r['label'].startswith('MOVEMENT: ')]!=original_asl:
        raise ValueError('ASL rows changed')
    dest=SOURCE/'development-features.json';write(dest,combined)
    p.update(source=str(dest),sourceSha256=sha(dest),windowPlanSha256=sha(SOURCE/'window-plan.json'),
             additionalWindows=len(additions),usableTrainingWindows=sum(r['split']=='train' and r['sequence'] is not None for r in additions),
             validationWindows=sum(r['split']=='val' for r in additions))
    write(SOURCE/'protocol.json',p);write(REPORT/'data-summary.json',p)
    print(json.dumps({k:p[k] for k in ('additionalWindows','usableTrainingWindows','validationWindows')}),flush=True)
    del combined,data,additions,original_asl
    trainer.SOURCE=SOURCE;trainer.ROOT=ROOT;trainer.REPORT=REPORT
    trainer.main()
    if any(sha(f)!=h for f,h in plan['implementations'].items()):raise ValueError('Frozen implementation changed')

if __name__=='__main__':main()
