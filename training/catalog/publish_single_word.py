"""Publish experimental words after recorded accuracy checks; camera/integration waived by owner."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

REPO = Path(__file__).resolve().parents[2]
BASE = Path('/opt/handspeak-training/single-word-20261010')
REPORT = REPO/'reports/vocabulary-expansion/single-word'
STAGE = Path('/opt/handspeak-staging/single-word-20261010/release-runtime')
LIVE = Path('/opt/handspeak/current')
ASSETS = ['app.js', 'index.html', 'guest-session.js', 'experience-ui.js', 'vocabulary-settings.js', 'experience.css', 'interpretation.js', 'research-words.js', 'sign-examples.js', 'motion-accuracy.js', 'models/motion-word-accuracy.json', 'motion-studio.js', 'vocabulary-library.js', 'automatic-motion.js',
          'face-tracker.js', 'temporal-word-model.js', 'camera-performance.js', 'temporal-camera.js',
          'hand-detection-worker.js'] + ['temporal-motion/'+name for name in
          ['classifier.js', 'runtime.js', 'temporal-features.js', 'temporal-window.js', 'motion-model.js', 'gesture-model.js']]
WORDS = ['CALL', 'FIND', 'FISH', 'SEE', 'SICK', 'PAIN', 'NIGHT', 'MORNING']
NOTICE = 'Experimental: camera and application integration checks were waived by the site owner; live-camera accuracy is unverified.'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name+'.publishing')
    temp.write_bytes(data); temp.chmod(0o644); temp.replace(path)


def encoded(value):
    return (json.dumps(value, indent=2)+'\n').encode()


def gate(word):
    root, report = BASE/word.lower(), REPORT/word.lower()
    # A candidate tested through evaluate_calibrated_candidate_v2.py writes its evidence to
    # fresh-v2/ (the v2 run excludes a negative label the archive cannot supply, see
    # reports/vocabulary-expansion/single-word/heldout-audit-20261017.md). Prefer it when
    # present; the recorded-clip limits below are identical for both paths.
    tested = 'fresh-v2' if (report/'fresh-v2/test-results.json').exists() else 'fresh'
    p = read(root/'frozen/protocol.json')
    if p['labels'] != [word] or sha(root/'frozen/frozen.pt') != p['checkpointSha256']:
        raise ValueError('Frozen candidate identity changed')
    development = read(root/'frozen/validation.json')
    if not development['passesDevelopmentScreen']:
        raise ValueError('Development accuracy failed')
    for filename, flag in [('regression.json', 'passesRegressionScreen'),
                           ('ordinary-window-regression.json', 'passesRegression'),
                           ('additional-ordinary-regression.json', 'passesRegression'),
                           (f'{tested}/test-results.json', 'passesRecordedClipGate')]:
        r = read(report/filename)
        if r.get(flag) is not True or r['checkpointSha256'] != p['checkpointSha256']:
            raise ValueError(f'Accuracy release gate failed: {filename}')
    result = read(report/tested/'test-results.json'); m = result['metrics']
    if m['total'] < 4 or m['correct'] / m['total'] < .5 or m['wrong'] or m['negativeTotal'] < 100 or m['negativeFalse']:
        raise ValueError('Recorded metrics fail release limits')
    fresh = read(root/tested/'protocol.json')
    if fresh['checkpointSha256'] != p['checkpointSha256'] or sha(root/tested/'protocol.json') != (root/tested/'protocol.sha256').read_text().strip():
        raise ValueError('Fresh-test freeze changed')
    return p, result


def prepare():
    if (STAGE/'manifest.json').exists():
        raise ValueError('Release snapshot already exists; do not silently replace it')
    manifest = {'policy': NOTICE, 'assets': {}}
    for name in ASSETS:
        source, target = REPO/name, STAGE/name
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target)
        manifest['assets'][name] = {'sha256': sha(target), 'previousLiveSha256': sha(LIVE/name) if (LIVE/name).exists() else None}
    atomic(STAGE/'manifest.json', encoded(manifest))


def publish(word):
    if word not in WORDS:
        raise ValueError('Unsupported word')
    p, results = gate(word)
    report = REPORT/word.lower(); receipt = report/'deployment.json'
    manifest = read(STAGE/'manifest.json')
    for name, info in manifest['assets'].items():
        if sha(STAGE/name) != info['sha256']:
            raise ValueError('Release snapshot changed')
        current = sha(LIVE/name) if (LIVE/name).exists() else None
        if current not in (info['previousLiveSha256'], info['sha256']):
            raise ValueError(f'Live file changed since snapshot: {name}')
    if receipt.exists():
        r = read(receipt)
        groups = read(LIVE/'models/motion-categories/index.json').get('groups', [])
        visible = any(g.get('id') == 'single-'+word.lower() and g.get('sha256') == r.get('modelSha256') for g in groups)
        if r.get('deployed') and visible and (LIVE/r['modelFile']).exists() and sha(LIVE/r['modelFile']) == r['modelSha256']:
            print(f'{word} already published'); return
    subprocess.run([sys.executable, str(REPO/'training/catalog/export_single_word.py'), '--word', word], check=True)
    slug = word.lower(); model_file = f'models/motion-categories/single-{slug}.json'
    model_path = STAGE.parent/slug/model_file; model = read(model_path)
    if model['checkpointSha256'] != p['checkpointSha256'] or model['labels'] != [word]:
        raise ValueError('Export identity mismatch')
    digest = sha(model_path)
    index_path, catalog_path = 'models/motion-categories/index.json', 'models/motion-vocabulary.json'
    index, catalog = read(LIVE/index_path), read(LIVE/catalog_path)
    items = [item for item in catalog['items'] if item['label'] == word]
    if len(items) != 1:
        raise ValueError('Expected one existing vocabulary entry')
    pack_id = 'single-'+slug
    pack = dict(id=pack_id, name=word, labels=[word], file=model_file, sha256=digest,
                status='experimental', test=results['metrics'], releaseNotice=NOTICE,
                checkpointSha256=p['checkpointSha256'], cameraTested=False, integrationTested=False)
    index['groups'] = [g for g in index.get('groups', []) if g['id'] != pack_id]+[pack]
    index.update(status='experimental', reason='Individual words passed recorded accuracy screens. '+NOTICE)
    item = items[0]; item['cameraGroups'] = list(dict.fromkeys(item.get('cameraGroups', [])+[pack_id]))
    item['recognition'] = 'category-preview'
    m = results['metrics']
    item['testSummary'] = f"Recorded screen: {m['correct']}/{m['total']} correct, {m['negativeFalse']}/{m['negativeTotal']} other signs falsely accepted. "+NOTICE
    files = {name: (STAGE/name).read_bytes() for name in ASSETS if name not in ('index.html', 'app.js')}
    files.update({model_file: model_path.read_bytes(), 'app.js': (STAGE/'app.js').read_bytes(), index_path: encoded(index), catalog_path: encoded(catalog),
                  'index.html': (STAGE/'index.html').read_bytes()})
    # Public assets only. No training data, reports, credentials or database files are copied.
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = Path('/opt/handspeak-staging/deployment-backups')/f'single-{slug}-{stamp}'
    backup.mkdir(parents=True, mode=0o700)
    previous = {}
    for name in files:
        path = LIVE/name; previous[name] = path.read_bytes() if path.exists() else None
        if previous[name] is not None:
            target = backup/name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(previous[name])
    atomic(backup/'manifest.json', encoded({'files': {n: v is not None for n, v in previous.items()}, 'policy': NOTICE}))
    subprocess.run(['systemctl', 'start', 'handspeak-backup.service'], check=True)
    try:
        for name, data in files.items():
            atomic(LIVE/name, data)
        # Delivery verification only; the owner explicitly waived camera/integration testing.
        request = urllib.request.Request('http://127.0.0.1:8000/'+model_file, headers={'Host': 'handspeak.cvsu.dev'})
        with urllib.request.urlopen(request, timeout=30) as response:
            if hashlib.sha256(response.read()).hexdigest() != digest:
                raise ValueError('Served model does not match the export')
    except Exception:
        for name, data in previous.items():
            if data is None:
                (LIVE/name).unlink(missing_ok=True)
            else:
                atomic(LIVE/name, data)
        raise
    atomic(REPO/index_path, encoded(index)); atomic(REPO/catalog_path, encoded(catalog))
    atomic(REPO/model_file, model_path.read_bytes())
    atomic(receipt, encoded(dict(word=word, deployed=True, deployedAt=stamp, modelFile=model_file,
                                modelSha256=digest, checkpointSha256=p['checkpointSha256'],
                                backup=str(backup), cameraTested=False, integrationTested=False,
                                policy=NOTICE, recordedMetrics=m)))
    print(f'Published {word} as an experimental selectable camera vocabulary', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--word', choices=WORDS); parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    with open('/opt/handspeak-staging/single-word-publish.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.prepare:
            prepare()
        elif args.word:
            publish(args.word)
        else:
            parser.error('Use --prepare or --word')


if __name__ == '__main__':
    main()
