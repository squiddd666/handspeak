"""Wait for this fixed experiment, freeze a passing model, and run regression only."""
import json
from pathlib import Path
import subprocess
import sys
import time
import freeze_split_candidate as freeze
import check_split_regression as regression
from calibrate_word_thresholds import write, sha
BASE=Path('/opt/handspeak-training')
ROOT=BASE/'vocabulary-expansion-windowed-ordinary-rejection'
FROZEN=BASE/'vocabulary-expansion-windowed-ordinary-frozen'
REPORT=Path('/opt/handspeak/repository/reports/vocabulary-expansion/windowed-ordinary-rejection')


def status(stage,**extra):
    value=dict(stage=stage,deployed=False,**extra)
    write(REPORT/'continuation-status.json',value)
    print(json.dumps(value),flush=True)


def main():
    try:
        status('waiting-for-training',state='running')
        deadline=time.monotonic()+7200
        while subprocess.run(['systemctl','is-active','--quiet','handspeak-windowed-ordinary-training-20261005.service']).returncode==0:
            if time.monotonic()>deadline:raise TimeoutError('Training deadline exceeded')
            time.sleep(5)
        source=BASE/'vocabulary-expansion-windowed-ordinary-source'
        plan=json.loads((source/'window-plan.json').read_text())
        if any(sha(f)!=h for f,h in plan['implementations'].items()):raise ValueError('Training implementation changed')
        result=json.loads((ROOT/'validation.json').read_text())
        if not result['passesValidation']:
            status('development-screen-failed',state='complete',passesDevelopmentScreen=False,nextStep='No promotion. Review failures and data coverage.');return
        status('freeze-and-regression',state='running')
        freeze.SOURCE=ROOT;freeze.ROOT=FROZEN;freeze.REPORT=REPORT
        freeze.main()
        regression.ROOT=FROZEN;regression.REPORT=REPORT
        regression.main()
        subprocess.run([sys.executable,str(Path(__file__).with_name('check_ordinary_window_regression.py')),'--candidate',str(FROZEN),'--report',str(REPORT)],check=True)
        result=json.loads((FROZEN/'regression.json').read_text())
        windows=json.loads((REPORT/'ordinary-window-regression.json').read_text())
        passed=result['passesRegressionScreen'] and windows['passesRegression']
        status('complete',state='complete',passesDevelopmentScreen=True,passesRegressionScreen=passed,
               nextStep='Fresh recording, short-window negative and real-camera tests still required; no automatic deployment.' if passed else 'Regression failed; no deployment.')
    except Exception as error:
        status('failed',state='failed',error=str(error));raise

if __name__=='__main__':main()
