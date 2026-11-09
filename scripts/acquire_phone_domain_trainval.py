"""Acquire the frozen official-phone TRAIN/VAL originals for camera-domain fitting.

Frozen selection comes from hs-eval/phone-domain-development-20261108. This step
only locates each exact frozen member inside its publisher archive, verifies
archive membership and byte extent, and downloads the ORIGINAL bytes with range
and ETag checks. No decoding, prediction, capture, or training happens here.
Failures are preserved, never retried into a different recording.
"""
from __future__ import annotations

import argparse, collections, concurrent.futures, datetime, hashlib, http.client, json, ssl, sys, tarfile, threading, time, urllib.error, urllib.request
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from scripts.run_online_native_audit import sha, verify
from scripts.prepare_online_motion_audit import HOST, MAX_CLIP, validate_range

DATASET = 'popsign_v1_0'


def write_new(path, data):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')


def frozen_selection(manifest_path):
    rows = json.loads(manifest_path.read_text(encoding='utf-8'))
    if not rows:
        raise ValueError('Empty frozen selection')
    if len({r['originalName'] for r in rows}) != len(rows):
        raise ValueError('Duplicate original names in frozen selection')
    for r in rows:
        if r['split'] not in ('train', 'val'):
            raise ValueError('Frozen selection must be train/val only')
        url = 'https://{}/data/{}/game/{}/{}.tar'.format(HOST, DATASET, r['split'], r['publisherLabel'])
        if r['archive'] != url:
            raise ValueError('Frozen archive URL does not match split/label: ' + r['originalName'])
    return rows


class Fetcher:
    """Range reads over a persistent, per-thread keep-alive TLS connection.

    A fresh TLS handshake per 512-byte TAR header dominates the walk cost, so
    each thread keeps its own connection. Opt-in unverified TLS is limited to
    this single public publisher host; no credentials or cookies are used.
    """
    def __init__(self, unverified):
        self.context = ssl._create_unverified_context() if unverified else ssl.create_default_context()
        self._local = threading.local()

    def _connection(self):
        conn = getattr(self._local, 'connection', None)
        if conn is None:
            conn = http.client.HTTPSConnection(HOST, timeout=60, context=self.context)
            self._local.connection = conn
        return conn

    def _close(self):
        conn = getattr(self._local, 'connection', None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._local.connection = None

    def read(self, url, start, end):
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.netloc != HOST or parsed.query or parsed.fragment:
            raise ValueError('Only the public publisher HTTPS host is permitted')
        if not parsed.path.startswith('/data/{}/game/'.format(DATASET)) or not parsed.path.endswith('.tar'):
            raise ValueError('Only original official archives are permitted')
        if start < 0 or end < start or end - start + 1 > MAX_CLIP:
            raise ValueError('Invalid or excessive range')
        path = parsed.path
        headers = {'Range': 'bytes={}-{}'.format(start, end), 'Accept-Encoding': 'identity', 'Connection': 'keep-alive'}
        last = None
        for attempt in range(3):
            try:
                conn = self._connection()
                conn.request('GET', path, headers=headers)
                response = conn.getresponse()
                if response.status != 206:
                    raise ValueError('Range not honored')
                payload = response.read(end - start + 2)
                total = validate_range(response.status, response.headers, payload, start, end)
                return payload, total, response.headers.get('ETag')
            except (TimeoutError, urllib.error.URLError, http.client.HTTPException, ConnectionError, OSError) as error:
                last = error
                self._close()
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)
        raise last  # pragma: no cover

def locate(url, wanted, fetcher, max_headers=400000):
    """Walk TAR headers only, until every wanted member name is found."""
    found, observed, total, etag, offset, index = {}, [], None, None, 0, 0
    while index < max_headers:
        header, size, current = fetcher.read(url, offset, offset + 511)
        if total is not None and (size != total or current != etag):
            raise ValueError('Archive changed while locating members')
        total, etag = size, current
        if header == bytes(512):
            break
        info = tarfile.TarInfo.frombuf(header, 'utf-8', 'strict')
        start = offset + 512
        offset = start + ((info.size + 511) // 512) * 512
        if offset > total or info.size < 0:
            raise ValueError('Invalid TAR extent')
        if info.isdir():
            continue
        if not info.isfile():
            raise ValueError('Unsupported extended/link entry; do not guess member')
        if not info.name.endswith('.mp4'):
            continue
        index += 1
        name = PurePosixPath(info.name.replace('\\', '/')).name
        observed.append(name)
        if name in wanted:
            if not 0 < info.size <= MAX_CLIP:
                raise ValueError('Original exceeds declared size bound')
            found[name] = dict(byteStart=start, byteSize=info.size, archiveSize=total, archiveETag=etag)
            if len(found) == len(wanted):
                break
    return dict(found=found, observed=observed, total=total, etag=etag, headersWalked=index)


def main(args):
    out = args.out.resolve()
    out.relative_to((ROOT.parent / 'hs-eval').resolve())
    if 'phone-domain' not in out.name:
        raise ValueError('Use a dedicated phone-domain folder outside the served repository')
    if (out / 'protocol.json').exists():
        raise FileExistsError('Folder already frozen; do not silently reacquire')

    dev_protocol = args.manifest.resolve().parent / 'protocol.json'
    protocol = json.loads(dev_protocol.read_text(encoding='utf-8'))
    verify(protocol)  # every frozen input must be byte-identical before use

    rows = frozen_selection(args.manifest)
    if protocol['trainingAllowed'] is not True or protocol['downloadsPerformed'] is not False:
        raise ValueError('Source protocol is not in the expected pre-acquisition state')
    if sorted({r['label'] for r in rows}) != sorted(protocol['labels']):
        raise ValueError('Frozen selection labels differ from the source protocol')

    fetcher = Fetcher(args.allow_unverified_publisher_tls)
    out.mkdir(exist_ok=True)
    freeze = dict(protocol['frozenFilesSha256'])
    freeze[str(Path(__file__))] = sha(Path(__file__))

    archives = {}
    for r in rows:
        archives.setdefault(r['archive'], []).append(r)
    wanted_by_archive = {u: {r['originalName'] for r in v} for u, v in archives.items()}

    locations, locate_errors = [], []
    def walk(url):
        try:
            result = locate(url, wanted_by_archive[url], fetcher)
            print('located', len(result['found']), '/', len(wanted_by_archive[url]), 'in', url.split('/')[-1], flush=True)
            return url, result
        except Exception as error:
            print('locate failed', url.split('/')[-1], str(error), flush=True)
            return url, dict(error=str(error))
    # Archive walks are RTT-bound; fan out modestly across distinct archives.
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for url, result in pool.map(walk, sorted(archives)):
            if 'error' in result:
                locate_errors.append(dict(archive=url, error=result['error']))
                continue
            for row in archives[url]:
                loc = result['found'].get(row['originalName'])
                if not loc:
                    locate_errors.append(dict(archive=url, originalName=row['originalName'], error='frozen member absent from archive'))
                    continue
                locations.append(dict(row, **loc))

    write_new(out / 'protocol.json', dict(
        purpose='phone-domain-train-val-original-acquisition-only',
        frozenAtUtc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        frozenFilesSha256=freeze, sourceProtocol=str(dev_protocol), sourceManifest=str(args.manifest),
        expectedCount=len(rows), counts=dict(collections.Counter(r['split'] for r in rows)),
        selection='Frozen exact original names from the source protocol; no decode, prediction, or outcome-based choice.',
        license='PopSign v1 CC BY 4.0; public-use publisher dataset, originals only.',
        transportCertificateVerified=not args.allow_unverified_publisher_tls,
        transportLimitation='Public publisher certificate chain untrusted on this host; explicitly scoped unverified TLS, no credentials. Hashes are local checks, not publisher authentication.' if args.allow_unverified_publisher_tls else None,
        trainingAllowed=True, calibrationAllowed=True, predictionsRun=False,
        testSourcesAllowed=False, watchSourcesAllowed=False, auditSourcesAllowed=False,
        originalsOnly=True, maximumDownloadedBytes=2 * 1024 ** 3))

    write_new(out / 'frozen-archive-selection.json', dict(
        protocolSha256=sha(out / 'protocol.json'),
        locations=[{k: v for k, v in row.items() if k != 'archiveETag'} for row in locations],
        errors=locate_errors))

    if sum(r['byteSize'] for r in locations) > 2 * 1024 ** 3:
        raise ValueError('Frozen cohort exceeds the download budget; nothing downloaded')

    originals = out / 'originals'
    originals.mkdir(exist_ok=True)
    def download(pair):
        index, row = pair
        item = dict(row, acquisitionId='phone-{:04d}'.format(index), status='download-failed')
        try:
            payload, size, etag = fetcher.read(row['archive'], row['byteStart'], row['byteStart'] + row['byteSize'] - 1)
            if size != row['archiveSize'] or etag != row['archiveETag']:
                raise ValueError('Archive changed after location freeze')
            digest = hashlib.sha256(payload).hexdigest()
            path = originals / '{}-{}-{}.mp4'.format(item['acquisitionId'], row['publisherLabel'], row['split'])
            with path.open('xb') as sink:
                sink.write(payload)
            item.update(path=str(path), sha256=digest, status='downloaded')
            print('downloaded', item['acquisitionId'], row['label'], row['split'], len(payload), flush=True)
        except Exception as error:
            item['error'] = str(error)
            print('download failed', item['acquisitionId'], str(error), flush=True)
        return item
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(download, enumerate(locations, 1)))

    seen = set()
    for item in results:
        if item.get('sha256') in seen:
            item['duplicateContent'] = True
        if item.get('sha256'):
            seen.add(item['sha256'])
    write_new(out / 'downloads.json', results)

    checks = []
    for item in results:
        if item['status'] != 'downloaded':
            continue
        path = Path(item['path'])
        checks.append(dict(path=item['path'], bytes=path.stat().st_size, sha256=sha(path), recorded=item['sha256']))
    write_new(out / 'original-identity.json', dict(originals=checks,
        allMatch=all(c['bytes'] == Path(c['path']).stat().st_size for c in checks) and all(c['sha256'] == c['recorded'] for c in checks)))

    summary = dict(expected=len(rows), located=len(locations), locatedMissing=len(locate_errors),
        downloaded=sum(r['status'] == 'downloaded' for r in results),
        downloadFailures=sum(r['status'] != 'downloaded' for r in results),
        downloadedBytes=sum(r['byteSize'] for r in results if r['status'] == 'downloaded'),
        splitCounts=dict(collections.Counter(r['split'] for r in results if r['status'] == 'downloaded')),
        labelCounts=dict(collections.Counter(r['label'] for r in results if r['status'] == 'downloaded')),
        duplicateContent=sum(1 for r in results if r.get('duplicateContent')),
        predictionsRun=False, featuresCaptured=False, trainingStarted=False,
        productionFilesChanged=False)
    write_new(out / 'summary.json', summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--allow-unverified-publisher-tls', action='store_true')
    main(parser.parse_args())
