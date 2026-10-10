"""One-word regression followed by untouched recordings; no automatic deployment."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import check_split_regression as regression
import evaluate_calibrated_candidate as evaluation
from calibrate_word_thresholds import write,sha
BASE=Path('/opt/handspeak-training/single-word-20261010')
REPO=Path(__file__).resolve().parents[2]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--word',required=True,choices=['CALL','FIND','FISH','SEE','SICK','PAIN','NIGHT','MORNING']);args=parser.parse_args()
    slug=args.word.lower();root=BASE/slug;report=REPO/'reports/vocabulary-expansion/single-word'/slug
    def status(stage,**extra):write(report/'release-status.json',dict(word=args.word,stage=stage,deployed=False,**extra))
    try:
        status('waiting-for-training',state='running');deadline=time.monotonic()+7200
        while not (report/'completion.json').exists():
            if time.monotonic()>deadline:raise TimeoutError('Training did not complete')
            if subprocess.run(['systemctl','is-active','--quiet',f'handspeak-single-{slug}-20261010.service']).returncode!=0:raise RuntimeError('Training stopped before completion')
            time.sleep(5)
        completion=json.loads((report/'completion.json').read_text())
        if not completion['passesDevelopmentScreen']:status('development-failed',state='complete');return
        plan=json.loads((root/'plan.json').read_text())
        if any(sha(f)!=h for f,h in plan['implementations'].items()):raise ValueError('Frozen training sources changed')
        status('known-regression',state='running');regression.ROOT=root/'frozen';regression.REPORT=report;regression.main()
        for media,frames,name in [('ordinary-movement-fresh22','framing-ordinary-fresh22/frames','ordinary-window-regression.json'),('novel-eight-ordinary','novel-eight-ordinary-evaluation/frames','additional-ordinary-regression.json')]:
            subprocess.run([sys.executable,str(REPO/'training/catalog/check_ordinary_window_regression.py'),'--candidate',str(root/'frozen'),'--report',str(report),'--media-root',str(BASE.parent/media),'--frames-root',str(BASE.parent/frames),'--output-name',name],check=True)
        reports=['regression.json','ordinary-window-regression.json','additional-ordinary-regression.json']
        if not all(json.loads((report/name).read_text()).get('passesRegressionScreen',json.loads((report/name).read_text()).get('passesRegression',False)) for name in reports):status('regression-failed',state='complete');return
        status('fresh-sign-evaluation',state='running')
        evaluation.SOURCE=root/'frozen';evaluation.ROOT=root/'fresh';evaluation.REPORT=report/'fresh';evaluation.base.ROOT=evaluation.ROOT;evaluation.base.REPORT=evaluation.REPORT
        evaluation.main();result=json.loads((root/'fresh/test-results.json').read_text())
        status('recording-check-complete',state='complete',passesFreshSignGate=result['passesRecordedClipGate'],remaining='Fresh ordinary-action screen, actual browser camera and integration checks before publishing')
    except Exception as error:status('failed',state='failed',error=str(error));raise
if __name__=='__main__':main()
