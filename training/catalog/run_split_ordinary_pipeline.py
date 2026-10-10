"""Continue from reviewed negative extraction into training, without auto-deployment."""
import gc
import json
from pathlib import Path
import subprocess
import sys
import time
import calibrate_word_thresholds as common
SOURCE=Path('/opt/handspeak-training/vocabulary-expansion-split-ordinary-source')
ROOT=Path('/opt/handspeak-training/vocabulary-expansion-split-ordinary-rejection')
REPORT=Path('/opt/handspeak/repository/reports/vocabulary-expansion/split-ordinary-rejection')
REPO=Path(__file__).resolve().parents[2]
def status(stage,**extra):
    value=dict(stage=stage,deployed=False,**extra)
    for root in [ROOT,REPORT]:common.write(root/'pipeline-status.json',value)
    print(json.dumps(value),flush=True)
def main():
    try:
        status('waiting-for-reviewed-extraction',state='running')
        while True:
            value=json.loads((SOURCE/'job-status.json').read_text())
            if value['state']=='failed':raise ValueError('Reviewed extraction failed: '+value.get('error',''))
            if value['state']=='complete':break
            time.sleep(5)
        old=json.loads(Path('/opt/handspeak-training/vocabulary-expansion-ordinary-source/protocol.json').read_text());new=json.loads((SOURCE/'protocol.json').read_text())
        if common.sha(old['source'])!=old['sourceSha256'] or common.sha(new['source'])!=new['sourceSha256']:raise ValueError('Development source changed')
        original=json.loads(Path(old['source']).read_text());expanded=json.loads(Path(new['source']).read_text())
        if [r for r in original if r['label']!='OTHER MOVEMENT']!=[r for r in expanded if not r['label'].startswith('MOVEMENT: ')]:raise ValueError('An original ASL row changed')
        del original,expanded;gc.collect()
        status('training',state='running')
        subprocess.run([sys.executable,'training/catalog/train_split_ordinary_rejection.py'],cwd=REPO,check=True)
        result=json.loads((ROOT/'validation.json').read_text())
        status('complete',state='complete',passesDevelopmentScreen=result['passesValidation'],nextStep='Freeze and test only if all development conditions pass; never auto-deploy a failed model')
    except Exception as error:status('failed',state='failed',error=str(error));raise
if __name__=='__main__':main()
