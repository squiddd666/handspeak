"""Stage frozen, evaluated preview models and provenance into the repository."""
import json,hashlib,shutil
from pathlib import Path
ROOT=Path('/opt/handspeak-training/vocabulary-v7');SITE=Path('/opt/handspeak/repository')
if __name__=='__main__':
 index=json.loads((ROOT/'evaluated-index.json').read_text());test=json.loads((ROOT/'test-report.json').read_text());catalog=json.loads((SITE/'models/motion-vocabulary.json').read_text());dest=SITE/'models/motion-categories';dest.mkdir(exist_ok=True)
 # A category with no correct validation match has not demonstrated even preview utility.
 # This rule does not tune or select thresholds from the reserved test outcomes.
 held=[g['id'] for g in index['groups'] if g['validation']['correct']==0]
 index['groups']=[g for g in index['groups'] if g['validation']['correct']>0]
 for g in index['groups']:
  source=ROOT/'models'/Path(g['file']).name
  assert hashlib.sha256(source.read_bytes()).hexdigest()==g['sha256']
  shutil.copy2(source,dest/source.name)
 (dest/'evaluation.json').write_text(json.dumps({'protocol':test['protocol'],'groups':{k:{'test':v['test'],'perWord':v['perWord'],'modelSha256':v['modelSha256']} for k,v in test['groups'].items()}},indent=2)+'\n')
 (dest/'index.json').write_text(json.dumps(index,indent=2)+'\n')
 for item in catalog['items']:
  item['cameraGroups']=[g['id'] for g in index['groups'] if item['label'] in g['labels']]
  if item['cameraGroups']:
   group=item['cameraGroups'][0];m=test['groups'][group]['perWord'][item['label']]
   item['testSummary']=f"Recorded check: {m['correct']}/{m['total']} reserved clips correctly matched this word. Experimental; this is not live-camera accuracy."
 (SITE/'models/motion-vocabulary.json').write_text(json.dumps(catalog,indent=2)+'\n')
 report=SITE/'reports/vocabulary-v7';report.mkdir(parents=True,exist_ok=True)
 for name in ['validation-report.json','test-report.json','frozen-index.json','video-sources.json']:
  shutil.copy2(ROOT/name,report/name)
 dev=json.loads((ROOT/'development-features.json').read_text());tests=json.loads((ROOT/'test-features.json').read_text());rows=dev+tests
 summary={'requestedUniqueEntries':len(catalog['items']),'categoryMemberships':sum(len(i['categories']) for i in catalog['items']),'trainingLabels':len({r['label'] for r in dev if r['split']=='train'}),'previewLabels':len({l for g in index['groups'] for l in g['labels']}),'previewCategories':len(index['groups']),'heldCategoriesNoValidationMatch':held,'newHostedClips':len(json.loads((ROOT/'video-sources.json').read_text())),'requestedEntriesWithVideo':sum(bool(i['video']) for i in catalog['items']),'partitions':{s:{'selected':sum(r['split']==s for r in rows),'usable':sum(r['split']==s and bool(r.get('sequence')) for r in rows),'signers':sorted({r['participant'] for r in rows if r['split']==s})} for s in ['train','val','test']},'defaultModelsUnchanged':True,'promotion':'Opt-in category previews only; not a replacement for the default six-word model.'}
 (report/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
