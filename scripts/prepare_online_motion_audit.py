"""Acquire publisher-authorized ORIGINAL PopSign clips for audit, never fitting.

This is a recording-new regression cohort, not a new-signer declaration. The
user-supplied fresh-signer validator intentionally remains unchanged. Selection
uses archive metadata only and is frozen before downloading/decoding videos.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import hashlib
import json
import re
import ssl
import tarfile
import time
import urllib.request
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DATASET = 'popsign_v1_0'
HOST = 'signdata.cc.gatech.edu'
LABELS = {s: s.upper() for s in (
    'hello', 'thankyou', 'please', 'yes', 'no', 'finish', 'drink', 'water',
    'book', 'food', 'hungry', 'like', 'go', 'home', 'have', 'fish', 'see',
    'sick', 'night', 'apple', 'car', 'dog')}
LABELS['thankyou'] = 'THANK YOU'
NEGATIVES = {'apple', 'car', 'dog'}
MISSING_TARGETS = ['BABY', 'LOVE', 'NAME', 'PAIN', 'WANT']
MAX_CLIP = 64 * 1024 * 1024


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_new(path, data):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')


def recording_key(member):
    """Recognize legacy IDs; do not mistake re-anonymized v2 IDs for new people."""
    name = PurePosixPath(member.replace('\\', '/')).name
    match = re.fullmatch(r'(?:gtsignstudy)?4a\.(\d+)-(.+\.mp4)', name)
    return (match.group(1), match.group(2)) if match else None


def safe_member(member, slug):
    p = PurePosixPath(member)
    if p.is_absolute() or '..' in p.parts or '\\' in member or len(p.parts) != 2:
        raise ValueError('Unsafe or unexpected TAR member')
    if p.parts[0] != slug or not p.name.endswith('.mp4'):
        raise ValueError('Member does not belong to the requested sign')
    key = recording_key(member)
    if not key or not key[1].startswith(slug + '-'):
        raise ValueError('Missing legacy signer or mismatched publisher label')
    return key


def records(value):
    if isinstance(value, dict):
        yield value
        for key, child in value.items():
            if key not in {'sequence', 'frames', 'raw', 'weights', 'landmarks', 'features'}:
                yield from records(child)
    elif isinstance(value, list):
        for child in value:
            if isinstance(child, (dict, list)):
                yield from records(child)


def inventory():
    """Bounded inventory of available provenance, not all historic private data."""
    eval_root = ROOT.parent / 'hs-eval'
    paths = set(ROOT.joinpath('models').rglob('*sources*.json'))
    paths.update(ROOT.joinpath('media').rglob('*sources*.json'))
    paths.update(ROOT.joinpath('reports').rglob('*.json'))
    paths.update(eval_root.glob('*.json'))
    for folder in eval_root.iterdir():
        if folder.is_dir() and folder.name.startswith('online-motion-audit'):
            # Publisher catalogs list UNSEEN recordings too. Only prior actual
            # download manifests belong in the previously-used registry.
            if (folder / 'downloads.json').is_file():
                paths.add(folder / 'downloads.json')
        elif folder.is_dir() and (folder.name.startswith('motion-repair') or folder.name in {'daily-words', 'beginner-100'}):
            paths.update(folder.rglob('*.json'))
    known_keys, known_hashes, fitting_ids = set(), set(), set()
    inputs = {}
    for path in sorted(paths):
        if path.stat().st_size > 8 * 1024 * 1024:
            continue
        try:
            data = json.loads(path.read_text(encoding='utf-8-sig'))
        except (ValueError, UnicodeError):
            continue
        relevant = False
        for row in records(data):
            # Historic reports use several filename field names, including
            # nested "entry" fields. Recognize every scalar filename value.
            keys = [recording_key(value) for value in row.values() if isinstance(value, str)]
            keys = [key for key in keys if key]
            if keys:
                relevant = True
                known_keys.update(keys)
                if row.get('split') in {'train', 'val'}:
                    fitting_ids.update(key[0] for key in keys)
            for k in ('sha256', 'sourceSha256', 'videoSha256', 'derivedSha256'):
                digest = row.get(k)
                if isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{64}', digest):
                    known_hashes.add(digest)
                    relevant = True
        if relevant:
            inputs[str(path)] = sha(path)
    # Include every local Watch recording, even if its manifest omitted a digest.
    for path in ROOT.joinpath('media').rglob('*.mp4'):
        known_hashes.add(sha(path))
    return known_keys, known_hashes, fitting_ids, inputs


def validate_range(status, headers, payload, start, end):
    match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', headers.get('Content-Range', ''))
    if status != 206 or not match:
        raise ValueError('Server must honor byte ranges; refusing a whole-archive response')
    low, high, total = map(int, match.groups())
    if (low, high) != (start, end) or high >= total or len(payload) != end - start + 1:
        raise ValueError('Incomplete or mismatched Content-Range')
    return total


class Fetcher:
    def __init__(self, allow_unverified_tls=False):
        # Opt-in is limited to this public dataset host. No credentials/cookies.
        self.context = ssl._create_unverified_context() if allow_unverified_tls else ssl.create_default_context()

    def range(self, url, start, end):
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.netloc != HOST or parsed.query or parsed.fragment:
            raise ValueError('Only the public publisher HTTPS host is permitted')
        if not parsed.path.startswith('/data/popsign_v1_0/game/test/') or not parsed.path.endswith('.tar'):
            raise ValueError('Only original official-test archives are permitted')
        if start < 0 or end < start or end - start + 1 > MAX_CLIP:
            raise ValueError('Invalid or excessive range')
        request = urllib.request.Request(url, headers={'Range': f'bytes={start}-{end}', 'Accept-Encoding': 'identity'})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=50, context=self.context) as response:
                    if urlsplit(response.url).netloc != HOST:
                        raise ValueError('Unexpected redirect host')
                    if response.status != 206:
                        raise ValueError('Range not honored')
                    payload = response.read(end - start + 2)
                    total = validate_range(response.status, response.headers, payload, start, end)
                    return payload, total, response.headers.get('ETag')
            except (TimeoutError, urllib.error.URLError):
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)


def select_archive(slug, source_map, fetcher, known_keys, fitting_ids, count=3, max_headers=180, min_video_index=0):
    published = set(source_map['test']['orig_name'].values())
    url = f'https://{HOST}/data/{DATASET}/game/test/{slug}.tar'
    selected, observed, signers = [], [], set()
    offset, etag, total, video_index = 0, None, None, 0
    for _ in range(max_headers):
        header, size, current_etag = fetcher.range(url, offset, offset + 511)
        if total is not None and (total != size or etag != current_etag):
            raise ValueError('Archive changed during metadata selection')
        total, etag = size, current_etag
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
            raise ValueError('Unsupported extended/link TAR entry; do not guess its filename')
        if not info.name.endswith('.mp4'):
            continue
        video_index += 1
        key = safe_member(info.name, slug)
        if not (PurePosixPath(info.name).name in published or info.name in published):
            raise ValueError('TAR member is absent from the publisher source map')
        reason = ('before-fixed-archive-offset' if video_index <= min_video_index else
                  'known-recording' if key in known_keys else 'fitting-signer' if key[0] in fitting_ids
                  else 'signer-already-selected-for-word' if key[0] in signers else 'size-out-of-bounds' if not 0 < info.size <= MAX_CLIP else 'selected')
        observed.append(dict(member=info.name, signerId=key[0], archiveVideoIndex=video_index, reason=reason))
        if reason != 'selected':
            continue
        signers.add(key[0])
        selected.append(dict(label=LABELS[slug], publisherLabel=slug, publisherSplit='test',
                             negativeForFrozen24WordCandidate=slug in NEGATIVES,
                             participant=key[0], member=info.name, source=url,
                             recordingKey=list(key), byteStart=start, byteSize=info.size,
                             archiveSize=total, archiveETag=etag))
        if len(selected) == count:
            break
    return dict(slug=slug, selected=selected, observed=observed,
                requested=count, selectedCount=len(selected), headersBound=max_headers,
                incomplete=len(selected) != count)


def main(args):
    out = args.out.resolve()
    out.relative_to((ROOT.parent / 'hs-eval').resolve())
    if 'online-motion-audit' not in out.name:
        raise ValueError('Use a dedicated online-motion-audit folder outside the served repository')
    publisher = out / 'publisher'
    if not publisher.is_dir() or not (publisher / 'v1-datacard.html').is_file():
        raise ValueError('Save the official v1 data card and source-map snapshots first')
    if (out / 'protocol.json').exists():
        raise FileExistsError('Cohort already frozen; do not silently reselect')
    if not 0 <= args.min_archive_video_index <= 150:
        raise ValueError('Metadata-only selection offset must be between 0 and 150')
    keys, hashes, fitting, inputs = inventory()
    freeze_files = list(ROOT.joinpath('models').rglob('*.json')) + list(ROOT.joinpath('models').glob('*.pt'))
    freeze_files += [ROOT / n for n in ('app.js', 'landmark-capture.js', 'motion-studio.js', 'motion-model.js', 'expanded-motion.js',
                                        'hello-binary.js', 'beginner-recognition.js', 'capstone-recognition.js', 'research-words.js',
                                        'beginner_asl.py', 'capstone_asl_v3.py', 'motion_calibration.py', 'body_manual_features.py')]
    protocol = dict(purpose='audit-only', source=DATASET, publisher='Georgia Institute of Technology / Deaf Professional Arts Network',
                    license='CC BY 4.0', licenseUrl='https://creativecommons.org/licenses/by/4.0/',
                    consentEvidenceType='publisher-public-use-statement, not a user consent declaration',
                    consentEvidenceUrl=f'https://{HOST}/view/datasets/{DATASET}/index.html',
                    freshNewSignerAudit=False, newSignerDeclarationMade=False,
                    cohortType='recording-new known-signer regression, subject to available provenance checks',
                    crossDatasetSignerIdentityOverlap='unverified; anonymous IDs cannot prove separation from ASL Citizen',
                    selection='First eligible archive members after the fixed metadata-only offset, one per signer per word; no prediction or decode-based selection.',
                    minArchiveVideoIndex=args.min_archive_video_index,
                    offsetRationale='Avoid early members whose old audit hashes survived without source filenames. This is identity screening only; no predictions have run.' if args.min_archive_video_index else None,
                    requestedPerWord=3, slugs=list(LABELS), missingCandidateLabels=MISSING_TARGETS,
                    exclusions='Known source recording keys, available original/derived hashes, known PopSign fitting signer IDs. No inference from faces.',
                    provenanceInventorySha256=inputs, knownRecordingKeys=len(keys), knownHashes=len(hashes), excludedFittingSigners=sorted(fitting),
                    modelAndRuntimeSha256={str(p.relative_to(ROOT)): sha(p) for p in sorted(set(freeze_files))},
                    publisherSnapshotSha256={p.name: sha(p) for p in publisher.iterdir() if p.is_file()},
                    transportCertificateVerified=not args.allow_unverified_publisher_tls,
                    transportLimitation='Public publisher certificate chain was untrusted on this host; explicitly scoped unverified TLS, no credentials. Hashes are local checks, not publisher authentication.' if args.allow_unverified_publisher_tls else None,
                    trainingAllowed=False, calibrationAllowed=False, predictionsRun=False,
                    originalsOnly=True, videoChanges='None; no previews, crops, resizing, speed changes, or re-encoding.',
                    acquisitionScriptSha256=sha(Path(__file__)),
                    candidateRoutingPolicy='No candidate installed; production route policies unchanged. Freeze any future inference protocol before predicting.',
                    maximumDownloadedBytes=2 * 1024**3)
    write_new(out / 'protocol.json', protocol)
    fetcher = Fetcher(args.allow_unverified_publisher_tls)
    def select(slug):
        try:
            source_map = json.loads((publisher / f'v1-{slug}-source-map.json').read_text(encoding='utf-8'))
            result = select_archive(slug, source_map, fetcher, keys, fitting, min_video_index=args.min_archive_video_index)
            print('selected', slug, result['selectedCount'], 'recordings', flush=True)
            return result
        except Exception as error:
            print('selection failed', slug, str(error), flush=True)
            return dict(slug=slug, selected=[], incomplete=True, error=str(error))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        selections = list(pool.map(select, LABELS))
    rows = [r for selection in selections for r in selection['selected']]
    if sum(r['byteSize'] for r in rows) > protocol['maximumDownloadedBytes']:
        raise ValueError('Frozen cohort exceeds the download budget; nothing downloaded')
    write_new(out / 'frozen-selection.json', dict(protocolSha256=sha(out / 'protocol.json'), selections=selections))
    videos = out / 'originals'
    videos.mkdir(exist_ok=False)
    def download(pair):
        index, row = pair
        item = dict(row, auditId=f'online-{index:04d}', split='audit-only', status='download-failed')
        try:
            payload, size, etag = fetcher.range(row['source'], row['byteStart'], row['byteStart'] + row['byteSize'] - 1)
            if size != row['archiveSize'] or etag != row['archiveETag']:
                raise ValueError('Archive changed after selection freeze')
            digest = hashlib.sha256(payload).hexdigest()
            path = videos / f"{item['auditId']}-{row['publisherLabel']}.mp4"
            with path.open('xb') as stream:
                stream.write(payload)
            item.update(path=str(path), sha256=digest, status='downloaded', auditEligible=digest not in hashes)
            if not item['auditEligible']:
                item['exclusionReason'] = 'Previously known clip content; retained but not described as recording-new'
            print('downloaded', item['auditId'], item['label'], len(payload), 'bytes', flush=True)
        except Exception as error:
            item['error'] = str(error)
            item['auditEligible'] = False
            print('download failed', item['auditId'], str(error), flush=True)
        return item
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(download, enumerate(rows, 1)))
    seen = set()
    for item in results:
        if item.get('sha256') in seen:
            item.update(auditEligible=False, exclusionReason='Duplicate content inside frozen cohort')
        if item.get('sha256'):
            seen.add(item['sha256'])
    write_new(out / 'downloads.json', results)
    eligible = [r for r in results if r['auditEligible']]
    summary = dict(selected=len(rows), downloaded=sum(r['status'] == 'downloaded' for r in results),
                   downloadedBytes=sum(r['byteSize'] for r in results if r['status'] == 'downloaded'),
                   recordingNewEligible=len(eligible), uniqueSignerIds=sorted({r['participant'] for r in eligible}),
                   counts=dict(collections.Counter(r['label'] for r in eligible)),
                   positiveRecordings=sum(not r['negativeForFrozen24WordCandidate'] for r in eligible),
                   unsupportedSignRecordings=sum(r['negativeForFrozen24WordCandidate'] for r in eligible),
                   missingCandidateLabels=MISSING_TARGETS, selectionFailures=[r['slug'] for r in selections if r.get('incomplete')],
                   downloadFailures=sum(r['status'] != 'downloaded' for r in results),
                   knownOrDuplicateContent=sum(r['status'] == 'downloaded' and not r['auditEligible'] for r in results),
                   modelAndRuntimeUnchanged=all(sha(ROOT / p) == digest for p, digest in protocol['modelAndRuntimeSha256'].items()),
                   protocolSha256=sha(out / 'protocol.json'), selectionSha256=sha(out / 'frozen-selection.json'),
                   downloadsSha256=sha(out / 'downloads.json'), freshNewSignerAudit=False, predictionsRun=False,
                   recognitionImprovementClaimed=False, trainingOrCalibrationAllowed=False)
    write_new(out / 'summary.json', summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--min-archive-video-index', type=int, default=0, help='Fixed metadata-only offset, frozen before downloading videos')
    parser.add_argument('--allow-unverified-publisher-tls', action='store_true', help='Explicit, public publisher-host-only fallback; never use credentials')
    main(parser.parse_args())
