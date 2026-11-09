"""Isolated production prediction endpoints and append-only scalar audit ledger."""
import argparse, copy, hashlib, json, math, os, secrets, threading
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse
from scripts.serve_capture_throughput_dev import byte_range
from scripts.run_online_native_audit import verify

MODES = ('beginner', 'capstone-core', 'capstone-extended', 'capstone-full')
RESULT_FIELDS = {'accepted', 'rejectionReason', 'error', 'httpStatus', 'checkpointSha256', 'auxiliarySha256'}
ATTEMPT_FIELDS = {'number','id','label','clipSha256','startedAt','durationMs','rate','sourceDuration','manualMode','status','error','finishedAt',
    'pairCount','bodyFrames','bodyOutputPreserved','manualFrames','manualTrackedFrames','sameEpoch','monotonicTimestamps',
    'sameDimensions','pixelEquality','sampledFrames','processedFrames','tracker','contractPassed','samples',
    'experimentalBodyPrediction','manualPredictions','candidateTracked','candidateDistance','candidateSeparation','candidateVotes',
    'playbackTruncated','trackerExecutionContext','bodyTracker','productionPredictions','manualEncodingUsable'}
SAMPLE_FIELDS = {'epoch','timestamp','width','height','pixelEquality','bodyHands','manualHands','bodyPose'}


def compact_result(data, status):
    return dict(accepted=(data.get('predictions') or [{}])[0].get('label') if status == 200 else None,
        rejectionReason=data.get('rejectionReason'), error=data.get('error'), httpStatus=status,
        checkpointSha256=data.get('checkpointSha256'), auxiliarySha256=data.get('auxiliarySha256'))


class Store:
    def __init__(self, folder, cfg, receipts):
        self.folder=folder; folder.mkdir(exist_ok=False)
        self.cfg=cfg; self.receipts=receipts; self.previous=None; self.lock=threading.Lock()

    def save(self, report):
        if set(report) != {'schema','startedAt','fixtureSha256','scope','realCameraCalls','microphoneCalls','attempts'}:
            raise ValueError('Unexpected report metadata')
        if any(isinstance(v,(dict,list)) for k,v in report.items() if k!='attempts'):
            raise ValueError('Scalar metadata required')
        if report['schema']!=4 or report['fixtureSha256']!=self.cfg['fixtureSha256'] or report['realCameraCalls']!=0 or report['microphoneCalls']!=0:
            raise ValueError('Frozen virtual-only schema 4 required')
        attempts=report['attempts']; refs=self.cfg['items']
        if not isinstance(attempts,list) or not 1<=len(attempts)<=len(refs): raise ValueError('Invalid attempt count')
        for i,(a,ref) in enumerate(zip(attempts,refs),1):
            if set(a)!=ATTEMPT_FIELDS or (a['number'],a['id'],a['label'],a['clipSha256']) != (i,ref['id'],ref['label'],ref['videoSha256']):
                raise ValueError('Wrong frozen cohort/order/fields')
            if a['status'] not in {'complete','failed','canceled'} or not a['finishedAt'] or a['rate']!=1 or a['durationMs'] not in (4000,6000,8000) or a['manualMode']!='all-four-frozen-modes':
                raise ValueError('Invalid completed capture')
            if any(isinstance(v,(dict,list)) for k,v in a.items() if k not in {'samples','manualPredictions','productionPredictions'}):
                raise ValueError('Raw payloads prohibited')
            if any(type(a[k]) is not int or not 0<=a[k]<=80 for k in ('pairCount','bodyFrames','manualFrames','manualTrackedFrames')):
                raise ValueError('Invalid capture counts')
            modes=a['manualPredictions']
            if set(modes)!={'default','expanded','daily','pack'} or any(v is not None and not isinstance(v,str) for v in modes.values()):
                raise ValueError('Invalid manual predictions')
            samples=a['samples']
            if not isinstance(samples,list) or len(samples)!=a['pairCount'] or any(not isinstance(s,dict) or set(s)!=SAMPLE_FIELDS for s in samples):
                raise ValueError('Invalid scalar samples')
            for s in samples:
                if any(isinstance(v,(dict,list)) for v in s.values()) or any(type(s[k]) not in (int,float) or not math.isfinite(s[k]) for k in ('timestamp','epoch','width','height','bodyHands','manualHands')):
                    raise ValueError('Invalid sample telemetry')
            if a['contractPassed']:
                if a['status']!='complete' or not samples or a['pairCount']!=a['processedFrames'] or not all(a[k] for k in ('bodyOutputPreserved','sameEpoch','monotonicTimestamps','sameDimensions','pixelEquality')):
                    raise ValueError('Invalid paired contract')
                if a['trackerExecutionContext']!='worker': raise ValueError('Updated supported-browser worker required')
                if any(s['pixelEquality'] is not True or s['epoch']!=samples[0]['epoch'] or (s['width'],s['height'])!=(samples[0]['width'],samples[0]['height']) for s in samples):
                    raise ValueError('Input identity changed')
                if any(b['timestamp']<=a['timestamp'] for a,b in zip(samples,samples[1:])): raise ValueError('Nonmonotonic timestamps')
                if sum(bool(s['bodyPose'] and s['bodyHands']) for s in samples)!=a['bodyFrames']:
                    raise ValueError('Body frames not preserved')
            elif a['experimentalBodyPrediction'] is not None or any(modes.values()):
                raise ValueError('Failed contract yielded recognition')
            production=a['productionPredictions']
            if set(production)!=set(MODES): raise ValueError('Every production mode must have an outcome')
            for mode,r in production.items():
                if set(r)!=RESULT_FIELDS or any(isinstance(v,(dict,list)) for v in r.values()): raise ValueError('Invalid production scalar result')
                receipt=self.receipts.get((a['id'],mode))
                should_request=a['contractPassed'] and a['bodyFrames']>=5
                if not should_request:
                    if receipt or r['accepted'] is not None or r['httpStatus'] is not None or r['rejectionReason']!='capture-unusable':
                        raise ValueError('Unusable capture cannot call/accept production API')
                elif receipt:
                    # A late server response cannot retroactively turn a client
                    # timeout into an acceptance. Preserve both scalar outcomes.
                    transport_failure=r['accepted'] is None and r['httpStatus'] is None and bool(r['error'])
                    if r!=receipt['result'] and not transport_failure:
                        raise ValueError('Browser result differs from actual production API receipt')
                elif r['accepted'] is not None or r['httpStatus'] is not None or not r['error']:
                    raise ValueError('Missing API receipt without retained request failure')
        with self.lock:
            old=self.previous
            if old and (report['startedAt']!=old['startedAt'] or report['scope']!=old['scope'] or attempts[:len(old['attempts'])]!=old['attempts']):
                raise ValueError('Prior outcomes are immutable')
            for a in attempts[len(old['attempts']) if old else 0:]:
                with (self.folder/f"attempt-{a['number']:03}.json").open('x',encoding='utf-8') as f: json.dump(a,f,indent=2)
            temp=self.folder/'checkpoint.tmp'; temp.write_text(json.dumps(report,indent=2)+'\n','utf-8'); temp.replace(self.folder/'checkpoint.json')
            self.previous=copy.deepcopy(report)
        return len(attempts)


def main(args):
    folder=args.protocol.resolve().parent; protocol=json.loads(args.protocol.read_text('utf-8')); verify(protocol)
    cfg=json.loads((folder/'fixture.json').read_text('utf-8'))
    digest=cfg.pop('fixtureSha256')
    if hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()!=digest: raise ValueError('Fixture changed')
    cfg['fixtureSha256']=digest
    data=folder/'isolated-data'; data.mkdir(exist_ok=False)
    os.environ['HANDSPEAK_DATA_DIR']=str(data); os.environ.pop('HANDSPEAK_MYSQL_CONFIG',None)
    import torch; torch.set_num_threads(1)
    import server as production
    actual={'beginner':production.beginner_status(),'capstone':production.capstone_status()}
    if actual!=protocol['productionStatus']: raise ValueError('Loaded production identity/status changed')
    (folder/'loaded-production-status.json').write_text(json.dumps(actual,indent=2)+'\n','utf-8')
    receipt_folder=folder/'api-receipts'; receipt_folder.mkdir(exist_ok=False)
    receipts={}; requested=set(); request_hashes={}; lock=threading.Lock()
    store=Store(folder/'browser-ledger',cfg,receipts)
    allowed={n:Path(p) for n,p in cfg['allowedFiles'].items()}
    refs={r['id']:r for r in cfg['items']}; origin=f'http://127.0.0.1:{args.port}'
    class Handler(production.HandSpeakHandler):
        def send_head(self):
            name=unquote(urlparse(self.path).path)
            if name not in allowed: return self.send_error(404)
            path=allowed[name]; size=path.stat().st_size; self._byte_range=None
            try: self._byte_range=byte_range(self.headers['Range'],size) if self.headers.get('Range') else None
            except ValueError:
                self.send_response(416); self.send_header('Content-Range',f'bytes */{size}'); self.send_header('Content-Length','0'); self.end_headers(); return
            start,end=self._byte_range or (0,size-1)
            self.send_response(206 if self._byte_range else 200); self.send_header('Content-Type',self.guess_type(str(path)))
            self.send_header('Accept-Ranges','bytes'); self.send_header('Content-Length',str(end-start+1))
            if self._byte_range: self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
            self.end_headers(); stream=path.open('rb'); stream.seek(start); return stream

        def do_GET(self):
            if urlparse(self.path).path in ('/api/beginner-asl/status','/api/capstone-asl/status'): return super().do_GET()
            return SimpleHTTPRequestHandler.do_GET(self)

        def do_HEAD(self): return SimpleHTTPRequestHandler.do_HEAD(self)
        def do_DELETE(self): return self.send_error(404)
        def do_PUT(self): return self.send_error(404)
        def do_POST(self):
            name=urlparse(self.path).path
            if self.headers.get('Origin')!=origin or not secrets.compare_digest(self.headers.get('X-Motion-Audit',''),cfg['token']): return self.send_error(403)
            if name=='/__worker_audit__/checkpoint':
                try:
                    size=int(self.headers.get('Content-Length',0))
                    if not 0<size<=4000000: raise ValueError('Invalid scalar checkpoint size')
                    count=store.save(json.loads(self.rfile.read(size)))
                except (ValueError,KeyError,TypeError) as e:
                    print('Checkpoint rejected:',e,flush=True); return self.json_response({'error':str(e)},422)
                return self.json_response({'saved':count})
            if name not in ('/api/beginner-asl','/api/capstone-asl'): return self.send_error(404)
            ident=self.headers.get('X-Audit-Clip'); mode=self.headers.get('X-Audit-Mode')
            if ident not in refs or mode not in MODES or (mode=='beginner')!=(name=='/api/beginner-asl'): return self.send_error(422)
            with lock:
                if (ident,mode) in requested: return self.send_error(409)
                requested.add((ident,mode))
            self.audit_request=(ident,mode)
            return super().do_POST()  # Actual production consent/error/predictor paths.

        def read_json(self):
            value=super().read_json()
            if not hasattr(self,'audit_request'): return value
            ident,mode=self.audit_request
            expected={'consent','frames'} if mode=='beginner' else {'consent','frames','vocabulary'}
            if set(value)!=expected or value.get('consent') is not True or not isinstance(value.get('frames'),list) or len(value['frames'])<5:
                raise production.APIError(422,'Only unchanged production landmark payloads are permitted')
            if mode!='beginner' and value['vocabulary']!=mode.split('-')[1]: raise production.APIError(422,'Wrong frozen vocabulary')
            digest=hashlib.sha256(json.dumps(value['frames'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
            with lock:
                if ident in request_hashes and request_hashes[ident]!=digest: raise production.APIError(422,'Capture frames changed between modes')
                request_hashes[ident]=digest
            return value

        def json_response(self,value,status=200):
            if hasattr(self,'audit_request'):
                ident,mode=self.audit_request
                receipt=dict(id=ident,mode=mode,framesSha256=request_hashes.get(ident),result=compact_result(value,status))
                with lock:
                    receipts[(ident,mode)]=receipt
                    with (receipt_folder/f'{ident}-{mode}.json').open('x',encoding='utf-8') as f: json.dump(receipt,f,indent=2)
            return super().json_response(value,status)
    with ThreadingHTTPServer(('127.0.0.1',args.port),Handler) as http:
        print('Frozen worker audit:',origin+'/fixture.html',flush=True); http.serve_forever()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--protocol',type=Path,required=True)
    p.add_argument('--port',type=int,default=8011); main(p.parse_args())
