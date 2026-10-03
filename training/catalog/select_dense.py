"""Stage only category replacements that pass the paired regression gate.
Does not promote the six-word default or claim independent high accuracy.
"""
import json,hashlib,shutil
from pathlib import Path
ROOT=Path('/opt/handspeak-training/vocabulary-v8');SITE=Path('/opt/handspeak/repository')
if __name__=='__main__':
 regression=json.loads((ROOT/'regression.json').read_text());frozen=json.loads((ROOT/'frozen-index.json').read_text());index=json.loads((SITE/'models/motion-categories/index.json').read_text());evaluation=json.loads((SITE/'models/motion-categories/evaluation.json').read_text());catalog=json.loads((SITE/'models/motion-vocabulary.json').read_text());selected=[]
 for i,g in enumerate(index['groups']):
  report=regression['groups'][g['id']]
  if not report['passesRegressionGate']:continue
  candidate=next(x for x in frozen['groups'] if x['id']==g['id'])
  if candidate['validation']['correct']<g['validation']['correct'] or candidate['validation']['wrong']>g['validation']['wrong'] or candidate['validation']['negativeFalse']>g['validation']['negativeFalse']:continue
  path=ROOT/'models'/Path(candidate['file']).name;assert hashlib.sha256(path.read_bytes()).hexdigest()==candidate['sha256'];shutil.copy2(path,SITE/candidate['file']);candidate={**candidate,'test':report['candidate'],'experiment':'dense-recovery-v8'};index['groups'][i]=candidate;selected.append(g['id']);evaluation['groups'][g['id']]={'test':report['candidate'],'perWord':report['perWord'],'modelSha256':candidate['sha256'],'experiment':'dense-recovery-v8'}
 evaluation['protocol']='Opt-in category previews. Initial v7 reserved test and paired v8 regression results are mixed by category. Dense replacements use more sampled frames for prior tracking failures and are selected only if correct matches increase without increased wrong or unsupported suggestions. Previously evaluated clips are not a fresh independent accuracy test. These results do not validate physical webcam or continuous-ASL use.'
 for item in catalog['items']:
  item['cameraGroups']=[g['id'] for g in index['groups'] if item['label'] in g['labels']]
  if item['cameraGroups']:
   g=item['cameraGroups'][0];m=evaluation['groups'][g]['perWord'][item['label']];item['testSummary']=f"Recorded check: {m['correct']}/{m['total']} clips correctly matched this word. Experimental; this is not live-camera accuracy."
 (SITE/'models/motion-categories/index.json').write_text(json.dumps(index,indent=2)+'\n');(SITE/'models/motion-categories/evaluation.json').write_text(json.dumps(evaluation,indent=2)+'\n');(SITE/'models/motion-vocabulary.json').write_text(json.dumps(catalog,indent=2)+'\n')
 reportdir=SITE/'reports/vocabulary-v8';reportdir.mkdir(exist_ok=True)
 for name in ['validation-report.json','regression.json','frozen-index.json']:shutil.copy2(ROOT/name,reportdir/name)
 fields=['total','correct','wrong','missed','negativeTotal','negativeFalse'];before={k:sum(r['baseline'][k] for r in regression['groups'].values()) for k in fields};after={k:sum((r['candidate'] if key in selected else r['baseline'])[k] for key,r in regression['groups'].items()) for k in fields}
 summary={'selectedCategoryReplacements':selected,'baselineRegression':before,'selectedRegression':after,'recoveredDevelopmentSequences':sum(bool(r.get('sequence')) for r in json.loads((ROOT/'development-features.json').read_text()))-sum(bool(r.get('sequence')) for r in json.loads(Path('/opt/handspeak-training/vocabulary-v7/development-features.json').read_text())),'recoveredTestSequences':regression['recoveredTestSequences'],'pretrainedRequestedLabels':len({l for g in index['groups'] for l in g['labels']}),'defaultSixWordModelReplaced':False,'highAccuracyDemonstrated':False,'limitations':'Repeated category-negative evaluations, previously inspected regression clips, offline dense sampling, and no physical webcam or ordinary non-sign benchmark.'}
 (reportdir/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
