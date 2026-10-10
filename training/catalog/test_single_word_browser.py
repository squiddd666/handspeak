"""Browser contract tests for one-word packs, rejection and default restoration."""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright
REPO=Path(__file__).resolve().parents[2]
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(REPO)));threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(args=['--no-sandbox']);page=browser.new_page();page.goto(f'http://127.0.0.1:{server.server_port}/motion-preview/index.html')
            result=page.evaluate('''async()=>{
              const {validTemporalWordModel,recognizeTemporalWord,TEMPORAL_ENCODING}=await import('/temporal-word-model.js');
              const template=await(await fetch('/motion-preview/model.json')).json();
              const model={...template,version:1,encoding:TEMPORAL_ENCODING,labels:['CALL'],threshold:0,margin:0,thresholdByLabel:{CALL:0}};
              if(!validTemporalWordModel(model))throw Error('Valid tensor layout rejected');
              const broken=structuredClone(model);broken.weights[0]['project.bias'][0]=NaN;
              if(validTemporalWordModel(broken))throw Error('NaN weights accepted');
              const wrong=structuredClone(model);wrong.weights[0]['head.1.weight'].pop();
              if(validTemporalWordModel(wrong))throw Error('Wrong tensor shape accepted');
              if(validTemporalWordModel({...model,labels:['CALL','FIND']}))throw Error('Multiple-word pack accepted');
              if(recognizeTemporalWord(model,Array(14).fill([null,null]),1)!==null)throw Error('No-hand frames accepted');
              return {passed:true,checks:['One-word tensor validation','Nonfinite and malformed weights rejected','Multiword pack rejected','No-hand rejection']};
            }''')
            cached=Path('/opt/handspeak-training/vocabulary-expansion-framing-fresh')
            manifest=json.loads((cached/'test-manifest.json').read_text())
            fixture=next(row for row in [json.loads((cached/'frames'/(r['sha256']+'.json')).read_text()) for r in manifest if r['label']=='CALL'] if row['sequence'] is not None)
            assert page.evaluate('''async row=>{
              const {recognizeTemporalWord,TEMPORAL_ENCODING}=await import('/temporal-word-model.js');
              const model=await(await fetch('/motion-preview/model.json')).json();
              Object.assign(model,{version:1,encoding:TEMPORAL_ENCODING,labels:['CALL'],threshold:0,margin:0,thresholdByLabel:{CALL:0}});
              const w=model.weights[0],call=model.outputLabels.indexOf('CALL'),other=model.outputLabels.findIndex(l=>l!=='CALL');
              w['head.1.weight']=w['head.1.weight'].map(r=>r.map(()=>0));w['head.1.bias']=w['head.1.bias'].map(()=>0);
              w['head.1.bias'][call]=100;
              if(recognizeTemporalWord(model,row.rawFrames,row.imageAspect)?.label!=='CALL')throw Error('Tracked test fixture unusable');
              w['head.1.bias'][other]=110;
              if(recognizeTemporalWord(model,row.rawFrames,row.imageAspect)!==null)throw Error('Excluded winner fell back to CALL');
              return true;
            }''',fixture)
            result['checks'].append('Controlled logits: excluded winner rejected without fallback (not accuracy evidence)')
            # Render the actual main-page DOM but instantiate only the component under test.
            html=(REPO/'index.html').read_text();page.route('**/app.js*',lambda route:route.fulfill(status=200,content_type='text/javascript',body=''))
            page.goto(f'http://127.0.0.1:{server.server_port}/index.html');page.evaluate('''async()=>{
              const {createMotionStudio}=await import('/motion-studio.js');
              window.testStudio=createMotionStudio({isRunning:()=>true,onWord:()=>true,onStatus:()=>{},speak:()=>{}});
            }''')
            page.wait_for_function("document.querySelector('#motionModelStatus').textContent.includes('6 pretrained')")
            lifecycle=page.evaluate('''async()=>{
              const {TEMPORAL_ENCODING}=await import('/temporal-word-model.js');
              const model=await(await fetch('/motion-preview/model.json')).json();
              Object.assign(model,{version:1,encoding:TEMPORAL_ENCODING,labels:['CALL'],thresholdByLabel:{CALL:model.threshold}});
              if(!testStudio.setVocabulary(model,'CALL'))throw Error('Could not select temporal pack');
              if(document.querySelector('#motionLibrary').textContent!=='CALL')throw Error('Word library mismatch');
              if(!document.querySelector('#expandedWords').disabled)throw Error('Other model not isolated');
              const broken=structuredClone(model);broken.weights=[];
              if(testStudio.setVocabulary(broken,'BROKEN'))throw Error('Malformed pack accepted');
              if(document.querySelector('#motionLibrary').textContent!=='CALL')throw Error('Invalid pack displaced current model');
              if(!testStudio.setVocabulary(null)||!document.querySelector('#motionLibrary').textContent.includes('HELLO'))throw Error('Defaults not restored');
              return true;
            }''');assert lifecycle
            result['checks']+=['Main motion component loads one-word pack','Other vocabulary isolated','Invalid replacement preserves current pack','Default six words restored']
            browser.close()
        target=REPO/'reports/vocabulary-expansion/single-word/browser-contract.json';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    finally:server.shutdown();server.server_close()
if __name__=='__main__':main()
