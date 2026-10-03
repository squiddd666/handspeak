"""Cross-check frozen Python predictions against browser JavaScript and measure desktop inference."""
import json,time
from pathlib import Path
import quickjs
from playwright.sync_api import sync_playwright
ROOT=Path('/opt/handspeak-training/vocabulary-v7');SITE=Path('/opt/handspeak/repository')
if __name__=='__main__':
 index=json.loads((SITE/'models/motion-categories/index.json').read_text());rows=json.loads((ROOT/'test-features.json').read_text());reg=json.loads(Path('/opt/handspeak-training/accuracy-v4/test-features.json').read_text());lookup={r['sha256']:r for r in rows+reg};reports=json.loads((ROOT/'test-report.json').read_text())['groups'];checks=[]
 # Fixed first positive and first negative for each model, not chosen by correctness.
 with sync_playwright() as p:
  b=p.chromium.launch(args=['--no-sandbox']);page=b.new_page();page.goto('http://127.0.0.1:8002',wait_until='domcontentloaded')
  for group in index['groups']:
   
   if group.get('experiment') in ['dense-recovery-v8','broad-negatives-v9']:
    dense=Path('/opt/handspeak-training/vocabulary-v8');experiment=Path('/opt/handspeak-training/vocabulary-v9') if group.get('experiment')=='broad-negatives-v9' else dense;report=json.loads((experiment/'regression.json').read_text())['groups'][group['id']];lookup={r['sha256']:r for r in json.loads((dense/'test-features.json').read_text())+reg}
   else:
    report=reports[group['id']];lookup={r['sha256']:r for r in rows+reg}
   preds=report['predictions'];selected=[next(r for r in preds if r['expected'] in group['labels']),next(r for r in preds if r['expected'] not in group['labels'])]
   for row in selected:
    sample=lookup[row['sha256']];out=page.evaluate('''async data=>{const {recognizeMotion}=await import('./motion-model.js');const model=await(await fetch(data.file)).json();const start=performance.now();const prediction=data.sequence?recognizeMotion(data.sequence,model.samples,model.parameters):null;return {label:prediction&&prediction.label!=='OTHER MOVEMENT'?prediction.label:null,milliseconds:performance.now()-start};}''',{'file':group['file'],'sequence':sample.get('sequence')})
    assert out['label']==row['suggested'],(group['id'],row,out)
    checks.append({'category':group['id'],'expected':row['expected'],'suggested':out['label'],'javascriptMs':out['milliseconds'],'tracked':bool(sample.get('sequence'))})
  b.close()
 Path('/opt/handspeak/live-test-results/catalog-prediction-check.json').write_text(json.dumps({'method':'One fixed positive and one fixed out-of-category reserved example per preview. Browser/Python agreement and server-hosted desktop Chromium classifier timing only; not phone or webcam performance.','checks':checks,'allAgree':True},indent=2));print('Python/browser prediction checks passed:',len(checks))
