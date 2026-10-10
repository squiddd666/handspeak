"""Check stale-result rejection and queue overload with a deliberately slow worker."""
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
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(REPO)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    checks=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(args=['--no-sandbox','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream'])
            for delay,change in [(700,True),(3100,False)]:
                context=browser.new_context(permissions=['camera'])
                context.add_init_script('''
                window.Worker=class {
                  timers=[];stopped=false;
                  postMessage(data){
                    if(data.type==='init'){queueMicrotask(()=>this.onmessage({data:{type:'ready',delegate:'CPU'}}));return;}
                    if(data.type!=='frame')return;
                    window.workerReceived=true;
                    this.timers.push(setTimeout(()=>{if(!this.stopped)this.onmessage({data:{type:'frame',generation:data.generation,timestamp:data.timestamp,rawHands:0,usableHands:0,landmarks:[],active:false,processingMs:DELAY,result:{label:'CALL',validSequence:true,frames:12,trackedFrames:12,durationMs:1000,classifierMs:1}}});},DELAY));
                  }
                  terminate(){this.stopped=true;this.timers.forEach(clearTimeout);}
                };
                '''.replace('DELAY',str(delay)))
                page=context.new_page();page.set_default_timeout(30000)
                page.goto(f'http://127.0.0.1:{server.server_port}/motion-preview/index.html')
                page.wait_for_function('!document.querySelector("#start").disabled');page.click('#start');page.wait_for_function('window.workerReceived')
                if change:
                    page.select_option('#expected','HOME');page.wait_for_timeout(delay+150)
                else:page.wait_for_timeout(delay+300)
                page.click('#copy');report=json.loads(page.input_value('#report'))
                assert report['events']==[],report
                if not change:assert report['overloads']>=1,report
                page.click('#stop');assert page.is_enabled('#start')
                checks.append('Changed expected sign discards in-flight result' if change else 'Slow worker causes bounded-queue rejection, never stale suggestions')
                context.close()
            browser.close()
        result=dict(passed=True,checks=checks,scope='Injected slow-worker control tests, not model accuracy')
        (REPO/'reports/vocabulary-expansion/motion-preview/queue-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    finally:server.shutdown();server.server_close()
if __name__=='__main__':main()
