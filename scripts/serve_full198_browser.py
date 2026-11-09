"""Isolated full-app reference server; no interpreter warmup or user database."""
import argparse,hashlib,json,os,secrets,threading
from pathlib import Path
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import unquote,urlparse
from scripts.run_online_native_audit import verify
from scripts.serve_capture_throughput_dev import byte_range
from scripts.serve_motion_audit import CheckpointStore,ENDPOINT

POST_KEYS={'/api/beginner-asl':{'consent','frames'},'/api/capstone-asl':{'consent','frames','vocabulary'},'/api/research-words':{'consent','sequence'}}


def payload_allowed(endpoint,payload):
    return endpoint in POST_KEYS and isinstance(payload,dict) and set(payload)==POST_KEYS[endpoint] and payload.get('consent') is True


def main(args):
    folder=args.protocol.resolve().parent;p=json.loads(args.protocol.read_text('utf-8'));verify(p)
    cfg=json.loads((folder/'fixture.json').read_text('utf-8'));data=folder/'isolated-data';data.mkdir(exist_ok=False)
    os.environ['HANDSPEAK_DATA_DIR']=str(data);os.environ.pop('HANDSPEAK_MYSQL_CONFIG',None)
    import torch;torch.set_num_threads(1)
    import server as production
    actual=dict(beginner=production.beginner_status(),capstone=production.capstone_status())
    if actual!=p['productionStatus']:raise ValueError('Actual loaded models changed')
    (folder/'loaded-production-status.json').write_text(json.dumps(actual,indent=2),'utf-8')
    store=CheckpointStore(folder/'browser-ledger',cfg);receipts=folder/'api-receipts';receipts.mkdir(exist_ok=False)
    allowed={n:Path(v) for n,v in p['allowedFiles'].items()};origin=f'http://127.0.0.1:{args.port}'
    pending=set();lock=threading.Lock()
    class Handler(production.HandSpeakHandler):
        def send_head(self):
            name=unquote(urlparse(self.path).path)
            if name not in allowed:return self.send_error(404)
            path=allowed[name];size=path.stat().st_size;self._byte_range=None
            try:self._byte_range=byte_range(self.headers['Range'],size) if self.headers.get('Range') else None
            except ValueError:
                self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.send_header('Content-Length','0');self.end_headers();return
            start,end=self._byte_range or (0,size-1);self.send_response(206 if self._byte_range else 200)
            self.send_header('Content-Type',self.guess_type(str(path)));self.send_header('Content-Length',str(end-start+1));self.send_header('Accept-Ranges','bytes')
            if self._byte_range:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
            self.end_headers();stream=path.open('rb');stream.seek(start);return stream
        def do_GET(self):
            name=urlparse(self.path).path
            if name in {'/api/beginner-asl/status','/api/capstone-asl/status','/api/research-words/status','/api/vocabulary-settings','/api/auth/me','/api/health','/api/gestures','/api/metrics','/api/sessions'}:
                return super().do_GET()
            return SimpleHTTPRequestHandler.do_GET(self)
        def do_POST(self):
            name=urlparse(self.path).path
            if self.headers.get('Origin')!=origin or not secrets.compare_digest(self.headers.get('X-Motion-Audit',''),cfg['auditCheckpoint']['token']):return self.send_error(403)
            if name not in {*POST_KEYS,ENDPOINT}:return self.send_error(404)
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=4_000_000:raise ValueError('Invalid payload size')
                body=self.rfile.read(length);payload=json.loads(body)
                if name==ENDPOINT:return self.json_response(dict(saved=store.save(payload)))
                if not payload_allowed(name,payload):raise ValueError('Hints/unexpected recognition payload fields prohibited')
                identity=self.headers.get('X-Reference-ID','')
                if identity not in p['order']:raise ValueError('Unknown reference')
                key=(identity,name)
                with lock:
                    if key in pending:raise ValueError('One-pass request already recorded')
                    pending.add(key)
                self._receipt=(identity,name,hashlib.sha256(body).hexdigest())
                # Invoke the unchanged production handler with the ORIGINAL body.
                import io;self.rfile=io.BytesIO(body);return super().do_POST()
            except (ValueError,TypeError,KeyError) as error:return self.json_response(dict(error=str(error)),422)
        def json_response(self,value,status=200):
            if hasattr(self,'_receipt'):
                identity,endpoint,digest=self._receipt;del self._receipt
                result=dict(referenceId=identity,endpoint=endpoint,payloadSha256=digest,httpStatus=status,
                    accepted=(value.get('predictions') or [{}])[0].get('label') or value.get('label') if status==200 else None,
                    checkpointSha256=value.get('checkpointSha256'),auxiliarySha256=value.get('auxiliarySha256'),rejectionReason=value.get('rejectionReason'))
                with (receipts/(identity+'-'+endpoint.rsplit('/',1)[1]+'.json')).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
            return super().json_response(value,status)
        def do_DELETE(self):return self.send_error(404)
        def do_PUT(self):return self.send_error(404)
        def do_PATCH(self):return self.send_error(404)
    production.initialize_database()
    with ThreadingHTTPServer(('127.0.0.1',args.port),Handler) as http:
        print('Owned full-198 app regression server ready; no user database or real cameras.',flush=True);http.serve_forever()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--protocol',type=Path,required=True);parser.add_argument('--port',type=int,default=8012);main(parser.parse_args())
