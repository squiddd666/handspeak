"""Named-file-only loopback fixture server. Saves scalar outcomes, not images."""
import argparse,copy,hashlib,json,re,secrets,threading
from pathlib import Path
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,unquote
from scripts.summarize_motion_virtual_camera import assert_scalar_telemetry
ROOT=Path(__file__).resolve().parents[1]

class DualCaptureStore:
    def __init__(self,root,fixture):
        self.root=Path(root);self.fixture=fixture;self.previous=None;self.lock=threading.Lock()
        self.root.mkdir(parents=True,exist_ok=False)
    def save(self,report):
        assert_scalar_telemetry(report)
        top={'schema','startedAt','fixtureSha256','scope','realCameraCalls','microphoneCalls','attempts'}
        fields={'number','id','label','clipSha256','startedAt','durationMs','rate','sourceDuration','manualMode',
                'status','error','finishedAt','pairCount','bodyFrames','bodyOutputPreserved','manualFrames','manualTrackedFrames',
                'sameEpoch','monotonicTimestamps','sameDimensions','pixelEquality','sampledFrames','processedFrames','tracker',
                'contractPassed','samples','experimentalBodyPrediction','manualPrediction'}
        sample_fields={'epoch','timestamp','width','height','pixelEquality','bodyHands','manualHands','bodyPose'}
        if set(report)-top:raise ValueError('Unknown report field; only scalar diagnostics are permitted')
        if report.get('schema')!=2 or report.get('fixtureSha256')!=self.fixture['fixtureSha256'] or report.get('realCameraCalls')!=0 or report.get('microphoneCalls')!=0:
            raise ValueError('Expected frozen virtual-only dual-capture report')
        refs={r['id']:r for r in self.fixture['items']};attempts=report.get('attempts',[])
        if not 1<=len(attempts)<=400:raise ValueError('Invalid attempt count')
        for number,a in enumerate(attempts,1):
            if set(a)-fields or any(isinstance(value,(dict,list)) for key,value in a.items() if key!='samples'):
                raise ValueError('Unknown or nonscalar attempt field')
            ref=refs.get(a.get('id'))
            if not ref or a.get('number')!=number or a.get('label')!=ref['label'] or a.get('clipSha256')!=ref['videoSha256'] or not a.get('finishedAt') or a.get('rate')!=1 or a.get('status') not in ('complete','failed','canceled'):
                raise ValueError('Mismatched or incomplete diagnostic outcome')
            samples=a.get('samples',[])
            if any(not isinstance(s,dict) or set(s)-sample_fields or any(isinstance(v,(dict,list)) for v in s.values()) for s in samples):
                raise ValueError('Only named scalar sample diagnostics are permitted')
            if len(samples)!=a.get('pairCount') or len(samples)>80:raise ValueError('Paired frame count differs')
            if a.get('contractPassed'):
                if a['status']!='complete' or not samples or a['pairCount']!=a['processedFrames'] or not all(a.get(k) for k in ('bodyOutputPreserved','sameEpoch','monotonicTimestamps','sameDimensions','pixelEquality')):
                    raise ValueError('Claimed capture contract did not pass')
                if any(not s['pixelEquality'] or s['epoch']!=samples[0]['epoch'] or (s['width'],s['height'])!=(samples[0]['width'],samples[0]['height']) for s in samples):
                    raise ValueError('Cross-stream identity differs')
                if any(s['timestamp']<=before['timestamp'] for before,s in zip(samples,samples[1:])):
                    raise ValueError('Non-increasing source timestamps')
        with self.lock:
            if self.previous and (report['startedAt']!=self.previous['startedAt'] or len(attempts)<len(self.previous['attempts']) or attempts[:len(self.previous['attempts'])]!=self.previous['attempts']):
                raise ValueError('Past outcomes cannot be replaced')
            first=len(self.previous['attempts']) if self.previous else 0
            for a in attempts[first:]:
                with (self.root/f"attempt-{a['number']:03}.json").open('x',encoding='utf-8') as out:
                    out.write(json.dumps(a,indent=2)+'\n')
            temporary=self.root/'checkpoint.tmp';temporary.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');temporary.replace(self.root/'checkpoint.json')
            self.previous=copy.deepcopy(report)
        return len(attempts)

def main(args):
    match=re.search(r'window\.DUAL_CAPTURE_FIXTURE = (.*);</script>',args.fixture.read_text(encoding='utf-8'))
    if not match:raise ValueError('Missing frozen fixture')
    fixture=json.loads(match.group(1));digest=fixture.pop('fixtureSha256')
    if hashlib.sha256(json.dumps(fixture,sort_keys=True).encode()).hexdigest()!=digest:raise ValueError('Fixture identity differs')
    fixture['fixtureSha256']=digest
    for name,digest in fixture['filesSha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise ValueError('Frozen runtime changed: '+name)
    for ref in fixture['items']:
        if hashlib.sha256((ROOT/ref['video']).read_bytes()).hexdigest()!=ref['videoSha256']:raise ValueError('Reference clip changed')
    store=DualCaptureStore(args.out,fixture)
    allowed=set(fixture['filesSha256'])|{ref['video'] for ref in fixture['items']}|{args.fixture.name}
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT),**kw)
        def do_GET(self):
            if unquote(urlparse(self.path).path).lstrip('/') not in allowed:return self.send_error(404)
            return super().do_GET()
        def do_HEAD(self):
            if unquote(urlparse(self.path).path).lstrip('/') not in allowed:return self.send_error(404)
            return super().do_HEAD()
        def do_POST(self):
            if urlparse(self.path).path!='/__dual_audit__/checkpoint' or self.headers.get('Origin')!=f'http://127.0.0.1:{args.port}' or not secrets.compare_digest(self.headers.get('X-Motion-Audit',''),fixture['token']):return self.send_error(403)
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=4_000_000:raise ValueError('Invalid scalar report size')
                count=store.save(json.loads(self.rfile.read(size)))
                body=json.dumps(dict(saved=count)).encode()
            except (ValueError,KeyError,TypeError):return self.send_error(422)
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    with ThreadingHTTPServer(('127.0.0.1',args.port),Handler) as server:
        print(f'Virtual-only dual fixture: http://127.0.0.1:{args.port}/{args.fixture.name}',flush=True);server.serve_forever()
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--fixture',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--port',type=int,default=8008);main(p.parse_args())
