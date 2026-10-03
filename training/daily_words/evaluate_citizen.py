"""Evaluate frozen private candidates once on reserved source test signers."""
import json,hashlib,time
import numpy as np
import torch
from train_citizen import ROOT,LABELS,Net,encoding,outputs,metrics,gate,fit
if __name__=='__main__':
 rows=json.loads((ROOT/'test-features.json').read_text());dev=json.loads((ROOT/'development-features.json').read_text())
 assert not({r['participant'] for r in rows}&{r['participant'] for r in dev})
 assert not({r['sha256'] for r in rows}&{r['sha256'] for r in dev})
 frozen=json.loads((ROOT/'temporal-validation.json').read_text())['selected'];path=ROOT/'temporal-private.pt';assert hashlib.sha256(path.read_bytes()).hexdigest()==frozen['sha256']
 assert frozen['passesValidation'],'Do not open test gate for an ineligible model'
 saved=torch.load(path,map_location='cpu',weights_only=True);net=Net(saved['config']['width']);net.load_state_dict(saved['state']);net.eval()
 x=torch.tensor(np.stack([encoding.features(r) for r in rows]))
 with torch.no_grad():
  probs=net(x).softmax(1).numpy();out=outputs(rows,probs,frozen['threshold'],frozen['margin'])
  timings=[]
  for i in range(100):
   start=time.perf_counter();net(x[:1]);timings.append((time.perf_counter()-start)*1000)
 temporal=metrics(rows,out)
 baseline=json.loads((ROOT/'dtw-validation.json').read_text());modelpath=ROOT/'dtw-private.json';assert hashlib.sha256(modelpath.read_bytes()).hexdigest()==baseline['sha256'];model=json.loads(modelpath.read_text())
 mat=fit.matrix(rows,model['samples'],'citizen-reserved-test');pred=fit.outputs(mat,model['samples'],model['parameters'],LABELS);dtw=metrics(rows,pred)
 report={'method':'Untouched official ASL Citizen test partition, with signers and exact file hashes disjoint from development. One frozen evaluation; no test tuning.','testClips':len(rows),'usableTestSequences':sum(r['sequence'] is not None for r in rows),'temporal':temporal,'dtwBaseline':dtw,'passesTestGate':gate(temporal),'temporalSha256':frozen['sha256'],'dtwSha256':baseline['sha256'],'inferenceOnlyCpuP95Ms':float(np.percentile(timings,95)),'timingScope':'PyTorch CPU network only; excludes video decoding, landmark extraction, automatic segmentation and browser timing.','deployed':False,'limitations':['Small selected corpus subset; no independent physical-webcam study.','No ordinary non-sign movement recordings.','Whole-clip classification is not automatic-boundary recognition.','The research dataset restricts redistribution; models and landmarks remain private.','Model scores are not calibrated confidence percentages.']}
 (ROOT/'test-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)
 (ROOT/'test-predictions-private.json').write_text(json.dumps([{'sha256':r['sha256'],'label':r['label'],'prediction':o,'baseline':b} for r,o,b in zip(rows,out,pred)],indent=2))
