"""Let the old in-memory queue finish its current evaluations, then apply the owner's release policy."""
import json
from pathlib import Path
import os
import subprocess
import sys
import time
import argparse

REPO = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--wait-unit', default='handspeak-single-word-queue-20261010.service')
parser.add_argument('--word', choices=['CALL', 'FIND', 'FISH', 'SEE', 'SICK', 'PAIN', 'NIGHT', 'MORNING'])
args = parser.parse_args()
while subprocess.run(['systemctl', 'is-active', '--quiet', args.wait_unit]).returncode == 0:
    time.sleep(15)
report = REPO/'reports/vocabulary-expansion/single-word'
status = json.loads((report/args.word.lower()/'release-status.json' if args.word else report/'queue-status.json').read_text())
if status['state'] == 'awaiting-final-checks' or (args.word and status.get('stage') == 'recording-check-complete' and status['state'] == 'complete'):
    os.execv(sys.executable, [sys.executable, '-u', str(Path(__file__).with_name('run_single_word_queue.py'))])
elif status['state'] != 'complete':
    raise RuntimeError('Earlier queue stopped unexpectedly; preserving failure for inspection: '+str(status))
