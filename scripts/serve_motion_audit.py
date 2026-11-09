"""Loopback-only test server with scalar, append-only audit checkpoints.

Not imported by production server.py. A fixture may save completed reference
outcomes here, never camera images/landmarks, accounts, or user messages.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import secrets
import sys
import threading

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.summarize_motion_virtual_camera import assert_scalar_telemetry, normalized

ENDPOINT = '/__motion_audit__/checkpoint'


class CheckpointStore:
    def __init__(self, root, fixture):
        self.root = Path(root)
        self.fixture = fixture
        self.lock = threading.Lock()
        self.previous = None
        if self.root.exists():
            raise FileExistsError('Use a new audit directory, not a previous run')
        self.root.mkdir(parents=True)

    def save(self, report):
        assert_scalar_telemetry(report)
        isolation = report.get('isolation', {})
        if (report.get('schema') != 1 or report.get('recognitionLabels') != 198 or
                isolation.get('host') != '127.0.0.1' or isolation.get('realCameraCalls') != 0 or
                isolation.get('microphoneCalls') != 0):
            raise ValueError('Expected an isolated scalar reference report')
        for key in ('indexSha256', 'bootstrapSha256', 'runtimeSha256', 'runnerSha256',
                    'activeModelSha256', 'activeAuxiliaryModelSha256', 'calibrationSha256'):
            if report.get(key) != self.fixture.get(key):
                raise ValueError('Fixture identity differs: ' + key)
        refs = {item['id']: item for item in self.fixture['items']}
        attempts = report.get('attempts', [])
        if not 1 <= len(attempts) <= 198 or len({a['id'] for a in attempts}) != len(attempts):
            raise ValueError('Expected one completed attempt per reference')
        for number, take in enumerate(attempts, 1):
            ref = refs.get(take['id'])
            if (not ref or take.get('number') != number or not take.get('finishedAt') or
                    take.get('stage') != 'baseline 1×' or take.get('rate') != 1 or
                    take.get('label') != ref['label'] or take.get('clip') != ref['video'] or
                    take.get('clipSha256') != ref['videoSha256']):
                raise ValueError('Incomplete or mismatched reference attempt')
            correct = bool(take.get('predicted')) and normalized(take['predicted']) == normalized(take['label'])
            if take.get('correct') != correct:
                raise ValueError('Actual output differs from claimed correctness')
        with self.lock:
            if self.previous:
                old = self.previous
                if report['startedAt'] != old['startedAt'] or len(attempts) < len(old['attempts']):
                    raise ValueError('Cannot replace an audit with a different or shorter run')
                if attempts[:len(old['attempts'])] != old['attempts']:
                    raise ValueError('Previously completed outcomes cannot be changed')
            first = len(self.previous['attempts']) if self.previous else 0
            for take in attempts[first:]:
                with (self.root / f"attempt-{take['number']:03}.json").open('x', encoding='utf-8') as out:
                    json.dump(take, out, ensure_ascii=False, indent=2)
                    out.write('\n')
            temporary = self.root / 'checkpoint.tmp'
            temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            temporary.replace(self.root / 'checkpoint.json')
            self.previous = report
        return len(attempts)


def run(args):
    import os
    import re
    from http.server import ThreadingHTTPServer
    from urllib.parse import urlparse
    cfg = re.search(r'^window\.HANDSPEAK_VIRTUAL_FIXTURE = (.*);\s*$', args.fixture.read_text(encoding='utf-8'), re.M)
    if not cfg:
        raise ValueError('Expected a frozen virtual fixture')
    fixture = json.loads(cfg.group(1))
    checkpoint = fixture.get('auditCheckpoint')
    if not checkpoint or checkpoint['endpoint'] != ENDPOINT:
        raise ValueError('Fixture checkpoint configuration missing')
    store = CheckpointStore(args.out, fixture)
    os.environ['HANDSPEAK_DATA_DIR'] = str(args.out / 'server-data')
    import server

    class Handler(server.HandSpeakHandler):
        def do_POST(self):
            if urlparse(self.path).path != ENDPOINT:
                return super().do_POST()
            if (self.client_address[0] != '127.0.0.1' or
                    self.headers.get('Origin') != f'http://127.0.0.1:{args.port}' or
                    not secrets.compare_digest(self.headers.get('X-Motion-Audit', ''), checkpoint['token'])):
                return self.json_response({'error': 'Isolated fixture authorization required'}, 403)
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 4_000_000:
                    raise ValueError('Invalid scalar report size')
                report = json.loads(self.rfile.read(size))
                count = store.save(report)
            except (ValueError, KeyError, TypeError) as error:
                return self.json_response({'error': str(error)}, 422)
            return self.json_response({'saved': count})

    server.initialize_database()
    server.interpreter.warmup()
    with ThreadingHTTPServer(('127.0.0.1', args.port), Handler) as http:
        print(f'Audit server: http://127.0.0.1:{args.port}/{args.fixture.name}#learn', flush=True)
        http.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8005)
    run(parser.parse_args())
