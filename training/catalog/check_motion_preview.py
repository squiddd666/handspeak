"""Exercise the static preview UI with a generated test camera, not sign accuracy."""
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
    url=f'http://127.0.0.1:{server.server_port}/motion-preview/index.html'
    output=REPO/'reports/vocabulary-expansion/motion-preview';output.mkdir(parents=True,exist_ok=True)
    checks=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(args=['--no-sandbox','--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
            context=browser.new_context(viewport=dict(width=390,height=844),permissions=['camera'])
            page=context.new_page();page.set_default_timeout(120000);errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(url);page.wait_for_function('!document.querySelector("#start").disabled')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.select_option('#expected','CALL');page.click('#start')
            page.wait_for_function('document.querySelector("#metrics").textContent.includes("processed frames")')
            page.click('#stop');page.click('#copy')
            report=json.loads(page.input_value('#report'))
            assert not report['cameraActive'] and report['expected']=='CALL' and report['checkpoint']
            assert report['input'] not in ('','0x0')
            assert all(event['label'] is None for event in report['events'])
            assert page.is_enabled('#start') and page.is_disabled('#stop')
            assert not errors,errors
            page.screenshot(path=str(output/'mobile.png'),full_page=True)
            checks.append('Camera start/stop, model integrity, local diagnostic report, no-hand rejection, mobile overflow')
            context.close()
            context=browser.new_context();page=context.new_page()
            context.route('https://cdn.jsdelivr.net/**',lambda route:route.abort())
            page.goto(url);page.wait_for_function('!document.querySelector("#start").disabled');page.click('#start')
            page.wait_for_function('document.querySelector("#status").textContent.includes("Recognition stopped")')
            assert page.is_enabled('#start');checks.append('Worker dependency download failure is visible and permits retry');context.close()
            context=browser.new_context();context.add_init_script("navigator.mediaDevices.getUserMedia=()=>Promise.reject(new DOMException('denied','NotAllowedError'))")
            page=context.new_page();page.goto(url);page.wait_for_function('!document.querySelector("#start").disabled')
            page.click('#start');page.wait_for_function('document.querySelector("#status").textContent.includes("permission was denied")')
            assert page.is_enabled('#start');checks.append('Permission denial permits retry');context.close()
            context=browser.new_context(permissions=['camera']);page=context.new_page()
            page.route('**/motion-preview/model.json',lambda route:route.fulfill(status=200,content_type='application/json',body='{}'))
            page.goto(url);page.wait_for_function('!document.querySelector("#start").disabled');page.click('#start')
            page.wait_for_function('document.querySelector("#status").textContent.includes("Model verification failed")')
            assert page.evaluate('document.querySelector("video").srcObject===null')
            checks.append('Corrupt model is rejected and camera stopped');context.close();browser.close()
        result=dict(passed=True,checks=checks,scope='UI/control tests with generated camera frames; not sign recognition accuracy')
        (output/'browser-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    finally:server.shutdown();server.server_close()


if __name__=='__main__':main()
