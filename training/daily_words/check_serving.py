"""Parity against frozen research test outputs; does not refit or retune."""
import json,os,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from research_words import ResearchWords,ResearchError
root=Path('/opt/handspeak-training/daily-words/citizen-research')
os.environ['HANDSPEAK_RESEARCH_WORDS_MODEL']=str(root/'dtw-private.json')
service=ResearchWords();rows=json.loads((root/'test-features.json').read_text());expected={r['sha256']:r['baseline'] for r in json.loads((root/'test-predictions-private.json').read_text())};times=[];n=0
for row in rows:
 if row['sequence'] is None:continue
 start=time.perf_counter();out=service.predict(row['sequence']);times.append(time.perf_counter()-start)
 assert out['label']==expected[row['sha256']],(row['label'],out,expected[row['sha256']]);n+=1
for bad in [None,[],[[0]*128]*19,[[float('nan')]*128]*20,[[True]*128]*20]:
 try:service.predict(bad);raise AssertionError('accepted malformed data')
 except ResearchError as e:assert e.status==422
service.lock.acquire()
try:
 try:service.predict(rows[0]['sequence']);raise AssertionError('concurrent request admitted')
 except ResearchError as e:assert e.status==429
finally:service.lock.release()
print(json.dumps({'parityClips':n,'meanInferenceMs':1000*sum(times)/len(times),'maxInferenceMs':1000*max(times),'invalidInputsRejected':True,'busyRejected':True}))
