"""Frozen six-word candidate regression, only when validation improved."""
import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import fit
ROOT=Path('/opt/handspeak-training/vocabulary-v9');fit.ROOT=ROOT
if __name__=='__main__':
 validation=json.loads((ROOT/'core-validation.json').read_text())
 if not validation['eligible']:
  (ROOT/'core-regression.json').write_text(json.dumps({'evaluated':False,'reason':'Candidate did not pass paired validation improvement limits.'},indent=2));print('Core withheld: validation gate failed');sys.exit()
 path=ROOT/'core.json';assert hashlib.sha256(path.read_bytes()).hexdigest()==validation['sha256'];candidate=json.loads(path.read_text());baseline=json.loads((fit.SITE/'models/asl-words.json').read_text());labels=candidate['labels'];rows=json.loads(Path('/opt/handspeak-training/accuracy-v4/test-features.json').read_text())+json.loads(Path('/opt/handspeak-training/vocabulary-v8/test-features.json').read_text());result={}
 for name,model in [('baseline',baseline),('candidate',candidate)]:result[name]=fit.metrics(rows,fit.outputs(fit.matrix(rows,model['samples'],'core-'+name+'-regression'),model['samples'],model['parameters'],labels),labels)
 a,b=result['baseline'],result['candidate'];result['passesRegressionGate']=b['correct']>a['correct'] and b['wrong']<=a['wrong'] and b['negativeFalse']<=a['negativeFalse'];result['protocol']='Previously evaluated regression recordings. No independent high-accuracy claim. Browser automatic capture and prior extra-word behavior must be checked before any promotion.';(ROOT/'core-regression.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
