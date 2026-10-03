"""Regression evaluation of frozen refinements; no test-based parameter tuning."""
import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from refine import ROOT,OUT,fit,converted
if __name__=='__main__':
 rows=json.loads((ROOT/'test-features.json').read_text());old=json.loads(Path('/opt/handspeak-training/accuracy-v4/test-features.json').read_text());index=json.loads((OUT/'frozen-index.json').read_text());prior=json.loads((ROOT/'test-report.json').read_text())['groups'];reports={}
 for group in index['groups']:
  path=OUT/(group['id']+'.json');assert hashlib.sha256(path.read_bytes()).hexdigest()==group['sha256'];m=json.loads(path.read_text());labels=m['labels'];test=rows+fit.balanced([r for r in old if r['label'] not in labels],18);c=m['featureTransform'];transformed=converted(test,c) if c else test;refs=converted(m['samples'],c) if c else m['samples']
  if c is None:stats=prior[group['id']]['test']
  else:stats=fit.metrics(test,fit.outputs(fit.matrix(transformed,refs,group['id']+'-refine-regression'),refs,m['parameters'],labels),labels)
  base=prior[group['id']]['test'];reports[group['id']]={'baseline':base,'candidate':stats,'featureTransform':c,'passesRegressionGate':stats['correct']>base['correct'] and stats['wrong']<=base['wrong'] and stats['negativeFalse']<=base['negativeFalse']};print(group['id'],reports[group['id']],flush=True)
 (OUT/'regression.json').write_text(json.dumps({'protocol':'Previously inspected v7 reserved clips; regression only. Refinement representation and thresholds selected on development validation and frozen before this run. No fresh accuracy claim.','groups':reports},indent=2))
