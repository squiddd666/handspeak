"""Loopback allowlist for independent capture development; never audit clips."""
import argparse,json,re
from pathlib import Path
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,unquote

def byte_range(header,size):
    match=re.fullmatch(r'bytes=(\d*)-(\d*)',header)
    if not match or not any(match.groups()):raise ValueError('Invalid single byte range')
    left,right=match.groups()
    if not left:
        count=int(right)
        if count<=0:raise ValueError('Invalid suffix range')
        return max(0,size-count),size-1
    start=int(left);end=min(int(right),size-1) if right else size-1
    if start>=size or end<start:raise ValueError('Range outside file')
    return start,end

def main(args):
    cfg=json.loads(args.config.read_text(encoding='utf-8'));allowed=cfg['allowedFiles']
    class Handler(SimpleHTTPRequestHandler):
        def send_head(self):
            path=Path(self.translate_path(self.path));size=path.stat().st_size
            header=self.headers.get('Range');self.range=None
            if header:
                try:self.range=byte_range(header,size)
                except ValueError:
                    self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.send_header('Content-Length','0');self.end_headers();return
            start,end=self.range if self.range else (0,size-1)
            self.send_response(206 if self.range else 200)
            self.send_header('Content-Type',self.guess_type(str(path)));self.send_header('Accept-Ranges','bytes')
            self.send_header('Content-Length',str(end-start+1))
            if self.range:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
            self.end_headers();stream=path.open('rb');stream.seek(start);return stream
        def copyfile(self,source,output):
            remaining=self.range[1]-self.range[0]+1 if self.range else None
            while remaining is None or remaining>0:
                chunk=source.read(min(65536,remaining) if remaining is not None else 65536)
                if not chunk:break
                output.write(chunk)
                if remaining is not None:remaining-=len(chunk)
        def translate_path(self,path):return allowed[unquote(urlparse(path).path)]
        def do_GET(self):
            if unquote(urlparse(self.path).path) not in allowed:return self.send_error(404)
            return super().do_GET()
        def do_HEAD(self):
            if unquote(urlparse(self.path).path) not in allowed:return self.send_error(404)
            return super().do_HEAD()
    with ThreadingHTTPServer(('127.0.0.1',8010),Handler) as server:
        print('Development fixture: http://127.0.0.1:8010/fixture.html',flush=True);server.serve_forever()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);main(p.parse_args())
