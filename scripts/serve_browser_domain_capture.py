"""Allowlisted loopback feature receiver: TRAIN/VAL landmarks, never images/APIs."""
import argparse,copy,hashlib,json,math,secrets,threading
from pathlib import Path
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import unquote,urlparse
from scripts.run_online_native_audit import verify
from scripts.serve_capture_throughput_dev import byte_range
from scripts.freeze_browser_domain_capture import ALLOWED_CAPTURE_PURPOSES

FIELDS={'number','id','sourceSha256','startedAt','finishedAt','status','error','rate','durationMs','sourceDuration',
    'playbackTruncated','start','deadline','sampledFrames','processedFrames','warmupFrames','poseWarmupFrames',
    'trackerExecutionContext','tracker','bodyTracker','realCameraCalls','microphoneCalls','checks','contractPassed','samples'}
CHECKS={'bodyOutputPreserved','sameEpoch','monotonicTimestamps','sameDimensions','pixelEquality',
    'pairedProcessing','productionSampling','recordingGeometry','workerExecution'}
SAMPLE={'epoch','timestamp','width','height','pixelEquality','body','usedHandFallback','manual'}

def finite(v):return type(v) in (int,float) and math.isfinite(v)

def validate_points(points,count,objects=False):
    if points is None:return
    if not isinstance(points,list) or len(points)!=count:raise ValueError('Wrong landmark dimensions')
    for point in points:
        if objects:
            if not isinstance(point,dict) or set(point)!={'x','y','z'}:raise ValueError('Only measured XYZ fields allowed')
            values=list(point.values())
        else:
            if not isinstance(point,list) or len(point)!=3:raise ValueError('Only XYZ arrays allowed')
            values=point
        if not all(finite(v) and abs(v)<100 for v in values):raise ValueError('Invalid landmark coordinate')

def validate(outcome,ref,number):
    if not isinstance(outcome,dict) or set(outcome)!=FIELDS:raise ValueError('Unexpected feature fields; images/predictions prohibited')
    if type(outcome['number']) is not int or (outcome['number'],outcome['id'],outcome['sourceSha256'])!=(number,ref['id'],ref['videoSha256']):raise ValueError('Wrong source/order')
    if outcome['status'] not in ('complete','failed','canceled') or outcome['rate']!=1 or outcome['durationMs'] not in (4000,6000,8000):raise ValueError('Invalid capture metadata')
    if outcome['realCameraCalls']!=0 or outcome['microphoneCalls']!=0:raise ValueError('Physical devices prohibited')
    for k in FIELDS-{'checks','samples'}:
        if isinstance(outcome[k],(dict,list)):raise ValueError('Unexpected nested metadata')
        if type(outcome[k]) is float and not finite(outcome[k]):raise ValueError('Nonfinite metadata')
    if set(outcome['checks'])!=CHECKS or any(type(v) is not bool for v in outcome['checks'].values()):raise ValueError('Exact stream contract required')
    if type(outcome['contractPassed']) is not bool:raise ValueError('Invalid contract result')
    if not isinstance(outcome['samples'],list) or len(outcome['samples'])>80:raise ValueError('Sample cap exceeded')
    for k in ('sampledFrames','processedFrames','warmupFrames','poseWarmupFrames'):
        if type(outcome[k]) is not int or outcome[k]<0 or (k in ('sampledFrames','processedFrames') and outcome[k]>80):raise ValueError('Invalid capture counts')
    samples=outcome['samples']
    for s in samples:
        if not isinstance(s,dict) or set(s)!=SAMPLE:raise ValueError('Only landmark pair allowed')
        if not all(finite(s[k]) for k in ('epoch','timestamp','width','height')) or type(s['epoch']) is not int:raise ValueError('Invalid sample identity')
        if type(s['pixelEquality']) is not bool or type(s['usedHandFallback']) is not bool:raise ValueError('Invalid stream telemetry')
        if not isinstance(s['body'],dict) or set(s['body'])!={'pose','left','right'}:raise ValueError('Only body landmarks allowed')
        for key,count in (('pose',7),('left',21),('right',21)):validate_points(s['body'][key],count)
        if not isinstance(s['manual'],list) or len(s['manual'])!=2:raise ValueError('Two independent manual slots required')
        for hand in s['manual']:validate_points(hand,21,objects=True)
        if outcome['start'] is None or outcome['deadline'] is None or not outcome['start']<=s['timestamp']<=outcome['deadline']:raise ValueError('Warmup/out-of-window feature')
    first=samples[0] if samples else None
    measured=dict(sameEpoch=bool(first) and all(s['epoch']==first['epoch'] for s in samples),
        monotonicTimestamps=all(a['timestamp']<b['timestamp'] for a,b in zip(samples,samples[1:])),
        sameDimensions=bool(first) and all((s['width'],s['height'])==(first['width'],first['height']) for s in samples),
        pixelEquality=bool(first) and all(s['pixelEquality'] for s in samples),
        pairedProcessing=len(samples)==outcome['processedFrames'],
        productionSampling=bool(samples) and len(samples)==outcome['sampledFrames'],
        recordingGeometry=bool(first) and (first['width'],first['height'])==(640,480),
        workerExecution=outcome['trackerExecutionContext']=='worker')
    if any(outcome['checks'][k]!=v for k,v in measured.items()):raise ValueError('Claimed contract differs from measured stream')
    if outcome['contractPassed']!=(outcome['status']=='complete' and all(outcome['checks'].values())):raise ValueError('Invalid overall contract')
    if outcome['contractPassed']:
        if outcome['poseWarmupFrames']<1:raise ValueError('No real pose warmup')
        if not finite(outcome['sourceDuration']) or outcome['sourceDuration']<=0:raise ValueError('Invalid original duration')
        if abs(outcome['deadline']-outcome['start']-outcome['durationMs'])>1e-5:raise ValueError('Recording deadline changed')
    return dict(pairCount=len(samples),bodyFrames=sum(bool(s['body']['pose'] and (s['body']['left'] or s['body']['right'])) for s in samples),
        manualTrackedFrames=sum(any(s['manual']) for s in samples))

class FeatureStore:
    def __init__(self,folder,cfg,sources):
        self.folder=folder;folder.mkdir(exist_ok=False);self.cfg=cfg;self.sources=sources
        if len(sources)!=len(cfg['items']) or any(r['split'] not in ('train','val') for r in sources):raise ValueError('Only frozen TRAIN/VAL sources')
        self.records=[];self.lock=threading.Lock()

    def save(self,outcome):
        with self.lock:
            number=len(self.records)+1
            if number>len(self.sources):raise ValueError('Frozen capture already complete')
            ref=self.cfg['items'][number-1];source=self.sources[number-1]
            counts=validate(outcome,ref,number)
            record=dict(source=source,capture=outcome,trainingAllowed=source['split']=='train' and outcome['contractPassed'],
                calibrationAllowed=source['split']=='val' and outcome['contractPassed'])
            payload=json.dumps(record,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
            path=self.folder/f'feature-{number:03}.json'
            with path.open('xb') as sink:sink.write(payload)
            row=dict(number=number,id=ref['id'],file=source['file'],split=source['split'],participant=source['participant'],label=source['label'],
                status=outcome['status'],error=outcome['error'],contractPassed=outcome['contractPassed'],
                playbackTruncated=outcome['playbackTruncated'],path=str(path),sha256=hashlib.sha256(payload).hexdigest(),**counts)
            self.records.append(copy.deepcopy(row))
            tmp=self.folder/'checkpoint.tmp';tmp.write_text(json.dumps(self.records,indent=2)+'\n','utf-8');tmp.replace(self.folder/'checkpoint.json')
            return dict(saved=number,id=ref['id'],sha256=row['sha256'])

def main(args):
    folder=args.protocol.resolve().parent;p=json.loads(args.protocol.read_text('utf-8'));verify(p)
    if p['purpose'] not in ALLOWED_CAPTURE_PURPOSES:raise ValueError('Wrong protocol')
    cfg=json.loads((folder/'fixture.json').read_text('utf-8'));digest=cfg.pop('fixtureSha256')
    if hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()!=digest:raise ValueError('Fixture changed')
    cfg['fixtureSha256']=digest;sources=json.loads(Path(p['sourceManifest']).read_text('utf-8'))
    store=FeatureStore(folder/'features',cfg,sources);allowed={k:Path(v) for k,v in cfg['allowedFiles'].items()}
    origin=f"http://127.0.0.1:{p['port']}"
    class Handler(SimpleHTTPRequestHandler):
        def send_head(self):
            name=unquote(urlparse(self.path).path)
            if name not in allowed:return self.send_error(404)
            path=allowed[name];size=path.stat().st_size;self._byte_range=None
            try:self._byte_range=byte_range(self.headers['Range'],size) if self.headers.get('Range') else None
            except ValueError:
                self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.send_header('Content-Length','0');self.end_headers();return
            start,end=self._byte_range or (0,size-1)
            self.send_response(206 if self._byte_range else 200);self.send_header('Content-Type',self.guess_type(str(path)))
            self.send_header('Content-Length',str(end-start+1));self.send_header('Accept-Ranges','bytes')
            if self._byte_range:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
            self.end_headers();stream=path.open('rb');stream.seek(start);return stream
        def copyfile(self,source,output):
            # Do not stream the rest of the original past the declared Range.
            remaining=self._byte_range[1]-self._byte_range[0]+1 if self._byte_range else None
            while remaining is None or remaining>0:
                chunk=source.read(65536 if remaining is None else min(65536,remaining))
                if not chunk:break
                output.write(chunk)
                if remaining is not None:remaining-=len(chunk)
        def do_POST(self):
            if urlparse(self.path).path!='/__domain__/feature':return self.send_error(404)
            if self.headers.get('Origin')!=origin or not secrets.compare_digest(self.headers.get('X-Domain-Capture',''),cfg['token']):return self.send_error(403)
            value=None;raw=b''
            try:
                size=int(self.headers.get('Content-Length',0))
                if not 0<size<=5000000:raise ValueError('Feature request too large')
                def bad_constant(v):raise ValueError('Nonfinite JSON')
                raw=self.rfile.read(size);value=json.loads(raw,parse_constant=bad_constant);result=store.save(value)
                status=200
            except (ValueError,KeyError,TypeError) as error:
                print('Feature rejected:',error,flush=True);result={'error':str(error)};status=422
                # Scalar failure receipt only. Never persist a rejected request
                # that might contain images or unexpected non-landmark fields.
                info=dict(reason=str(error),payloadSha256=hashlib.sha256(raw).hexdigest())
                if isinstance(value,dict):
                    ident=value.get('id')
                    if ident in {r['id'] for r in cfg['items']}:info['id']=ident
                    info['sampleCount']=len(value['samples']) if isinstance(value.get('samples'),list) else None
                    checks=value.get('checks')
                    if isinstance(checks,dict) and set(checks)==CHECKS and all(type(v) is bool for v in checks.values()):info['claimedChecks']=checks
                with (folder/f'rejected-feature-{secrets.token_hex(6)}.json').open('x',encoding='utf-8') as sink:json.dump(info,sink,indent=2)
            payload=json.dumps(result).encode();self.send_response(status);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
        def do_DELETE(self):return self.send_error(404)
        def do_PUT(self):return self.send_error(404)
    with ThreadingHTTPServer(('127.0.0.1',p['port']),Handler) as http:
        print('Local TRAIN/VAL feature capture:',origin+'/fixture.html',flush=True);http.serve_forever()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--protocol',type=Path,required=True);main(parser.parse_args())
