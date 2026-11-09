"""Allowlisted loopback-only audit assets and append-only scalar checkpoints."""
import argparse,copy,hashlib,json,re,secrets,threading
from pathlib import Path
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,unquote
from scripts.run_online_native_audit import verify
ROOT=Path(__file__).resolve().parents[1]

class Store:
    def __init__(self,folder,cfg):
        self.folder=folder;folder.mkdir(exist_ok=False);self.cfg=cfg;self.previous=None;self.lock=threading.Lock()
    def save(self,report):
        if set(report)!={'schema','startedAt','fixtureSha256','scope','realCameraCalls','microphoneCalls','attempts'}:raise ValueError('Unexpected report fields')
        if any(isinstance(value,(dict,list)) for key,value in report.items() if key!='attempts'):raise ValueError('Only scalar report metadata is permitted')
        if report['schema']!=3 or report['fixtureSha256']!=self.cfg['fixtureSha256'] or report['realCameraCalls']!=0 or report['microphoneCalls']!=0:raise ValueError('Expected virtual-only frozen audit')
        attempts=report['attempts'];refs=self.cfg['items']
        if not 1<=len(attempts)<=len(refs):raise ValueError('Invalid attempt count')
        fields={'number','id','label','clipSha256','startedAt','durationMs','rate','sourceDuration','manualMode','status','error','finishedAt',
                'pairCount','bodyFrames','bodyOutputPreserved','manualFrames','manualTrackedFrames','sameEpoch','monotonicTimestamps',
                'sameDimensions','pixelEquality','sampledFrames','processedFrames','tracker','contractPassed','samples',
                'experimentalBodyPrediction','manualPredictions','candidateTracked','candidateDistance','candidateSeparation','candidateVotes','playbackTruncated'}
        sample_fields={'epoch','timestamp','width','height','pixelEquality','bodyHands','manualHands','bodyPose'}
        for index,(a,ref) in enumerate(zip(attempts,refs),1):
            if set(a)-fields or a.get('number')!=index or a.get('id')!=ref['id'] or a.get('label')!=ref['label'] or a.get('clipSha256')!=ref['videoSha256']:raise ValueError('Wrong cohort or order')
            if a.get('status') not in {'complete','failed','canceled'} or not a.get('finishedAt') or a.get('rate')!=1 or a.get('manualMode')!='all-four-frozen-modes':raise ValueError('Invalid completed attempt')
            if any(isinstance(v,(dict,list)) for k,v in a.items() if k not in {'samples','manualPredictions'}):raise ValueError('Only scalar telemetry is permitted')
            modes=a.get('manualPredictions',{})
            if set(modes)!={'default','expanded','daily','pack'} or any(v is not None and not isinstance(v,str) for v in modes.values()):raise ValueError('Invalid independent predictions')
            samples=a.get('samples',[])
            if len(samples)!=a.get('pairCount') or len(samples)>80:raise ValueError('Invalid paired samples')
            if any(not isinstance(s,dict) or set(s)!=sample_fields or any(isinstance(v,(dict,list)) for v in s.values()) for s in samples):raise ValueError('Raw images/landmarks prohibited')
            if a.get('contractPassed'):
                if a['status']!='complete' or not samples or a['pairCount']!=a['processedFrames'] or not all(a.get(k) for k in ('bodyOutputPreserved','sameEpoch','monotonicTimestamps','sameDimensions','pixelEquality')):raise ValueError('Invalid stream contract')
                if any(not s['pixelEquality'] or s['epoch']!=samples[0]['epoch'] or (s['width'],s['height'])!=(samples[0]['width'],samples[0]['height']) for s in samples):raise ValueError('Input identity differs')
                if any(s['timestamp']<=previous['timestamp'] for previous,s in zip(samples,samples[1:])):raise ValueError('Timestamps not increasing')
            elif a.get('experimentalBodyPrediction') is not None or any(modes.values()):raise ValueError('Failed contract cannot yield accepted predictions')
        with self.lock:
            old=self.previous
            if old and (report['startedAt']!=old['startedAt'] or len(attempts)<len(old['attempts']) or attempts[:len(old['attempts'])]!=old['attempts']):raise ValueError('Past outcomes cannot be replaced')
            for a in attempts[len(old['attempts']) if old else 0:]:
                with (self.folder/f"attempt-{a['number']:03}.json").open('x',encoding='utf-8') as stream:json.dump(a,stream,indent=2)
            temp=self.folder/'checkpoint.tmp';temp.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');temp.replace(self.folder/'checkpoint.json');self.previous=copy.deepcopy(report)
        return len(attempts)

def main(args):
    folder=args.protocol.resolve().parent;protocol=json.loads(args.protocol.read_text(encoding='utf-8'));verify(protocol)
    cfg=json.loads((folder/'fixture.json').read_text(encoding='utf-8'));cohort=json.loads(Path(protocol['cohort']).read_text(encoding='utf-8'))['clips']
    digest=cfg.pop('fixtureSha256')
    if hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()!=digest:raise ValueError('Fixture changed')
    cfg['fixtureSha256']=digest
    videos={ref['video'].lstrip('/'):Path(c['path']) for ref,c in zip(cfg['items'],cohort)}
    store=Store(folder/'browser-ledger',cfg)
    allowed={name:ROOT/name for name in cfg['filesSha256']};allowed.update(videos);allowed['fixture.html']=folder/'fixture.html'
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT),**kw)
        def do_GET(self):
            name=unquote(urlparse(self.path).path).lstrip('/')
            if name not in allowed:return self.send_error(404)
            self.audit_path=allowed[name];return super().do_GET()
        def do_HEAD(self):
            name=unquote(urlparse(self.path).path).lstrip('/')
            if name not in allowed:return self.send_error(404)
            self.audit_path=allowed[name];return super().do_HEAD()
        def translate_path(self,path):return str(self.audit_path)
        def do_POST(self):
            if urlparse(self.path).path!='/__dual_audit__/checkpoint' or self.headers.get('Origin')!=f'http://127.0.0.1:{args.port}' or not secrets.compare_digest(self.headers.get('X-Motion-Audit',''),cfg['token']):return self.send_error(403)
            try:
                size=int(self.headers.get('Content-Length',0))
                if not 0<size<=4000000:raise ValueError('Invalid scalar report size')
                count=store.save(json.loads(self.rfile.read(size)));payload=json.dumps({'saved':count}).encode()
            except (ValueError,KeyError,TypeError) as error:
                print('Checkpoint rejected:',str(error),flush=True);return self.send_error(422)
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
    with ThreadingHTTPServer(('127.0.0.1',args.port),Handler) as server:
        print('Frozen online browser audit:',f'http://127.0.0.1:{args.port}/fixture.html',flush=True);server.serve_forever()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--protocol',type=Path,required=True);p.add_argument('--port',type=int,default=8009);main(p.parse_args())
