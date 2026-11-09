"""Freeze the repaired runtime, then acquire metadata-selected unused originals.

This successor leaves earlier acquisition/audit evidence and the stricter
new-signer intake validator untouched. No recognition runs in this command.
"""
import argparse, datetime, json, shutil
from pathlib import Path
from scripts import prepare_online_motion_audit as acquisition

ROOT = acquisition.ROOT
WORKER_FILES = ['landmark-capture.js', 'holistic-worker-tracker.js', 'holistic-body-worker.js',
                'legacy-holistic-worker-context.js', 'body-hand-recovery.js', 'hand-recovery-worker.js',
                'landmark-frame-geometry.js', 'camera-performance.js', 'app.js', 'index.html',
                'beginner-recognition.js', 'capstone-recognition.js', 'server.py', 'sign_features.py',
                'handshape_features.py', 'handshape_inference.py', 'handshape_model.py']


def main(args):
    out = args.out.resolve(); batch = args.batch.resolve()
    for folder in (out, batch):
        folder.relative_to((ROOT.parent / 'hs-eval').resolve())
        folder.mkdir(exist_ok=False)
    dev_path = ROOT.parent / 'hs-eval/capture-throughput-dev-20261108/capture-final-smoke/config.json'
    dev = json.loads(dev_path.read_text('utf-8'))
    frozen = dict(dev['modelAndGateSha256'])
    if any(acquisition.sha(Path(p)) != d for p, d in frozen.items()):
        raise ValueError('Classifier artifacts changed since the capture repair')
    frozen.update({str(ROOT / n): acquisition.sha(ROOT / n) for n in WORKER_FILES})
    import torch, beginner_asl, capstone_asl_v3
    torch.set_num_threads(1)
    status = {'beginner': beginner_asl.status(), 'capstone': capstone_asl_v3.status()}
    if not all(s.get('available') and s.get('runtimeReady') for s in status.values()):
        raise ValueError('Actual deployed model could not load')
    for model in (beginner_asl, capstone_asl_v3):
        p = Path(model._runtime_metadata['path']).resolve()
        frozen[str(p)] = acquisition.sha(p)
    for p in (ROOT / 'third_party/microsoft_asl_citizen/architecture').rglob('*.py'):
        frozen[str(p)] = acquisition.sha(p)
    acquisition.write_new(out / 'pre-acquisition-freeze.json', {
        'frozenAtUtc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'purpose': 'audit-only', 'frozenFilesSha256': frozen, 'productionStatus': status,
        'classifierArtifactsSha256': dev['modelAndGateSha256'],
        'developmentManifest': str(dev_path), 'developmentManifestSha256': acquisition.sha(dev_path),
        'developmentVideoSha256': {i['path']: i['sha256'] for i in dev['fixture']['items']},
        'selectionOffset': args.min_archive_video_index, 'predictionsRun': False,
        'trainingAllowed': False, 'calibrationAllowed': False,
    })
    publisher = batch / 'publisher'; publisher.mkdir()
    source = ROOT.parent / 'hs-eval/online-motion-audit-20261107/publisher'
    for p in source.iterdir():
        if p.is_file(): shutil.copy2(p, publisher / p.name)
    original_inventory = acquisition.inventory
    def expanded_inventory():
        keys, hashes, fitting, inputs = original_inventory()
        for item in dev['fixture']['items']:
            if acquisition.sha(Path(item['path'])) != item['sha256']:
                raise ValueError('Development recording changed')
            hashes.add(item['sha256'])
        inputs[str(dev_path)] = acquisition.sha(dev_path)
        inputs[str(out / 'pre-acquisition-freeze.json')] = acquisition.sha(out / 'pre-acquisition-freeze.json')
        acquisition.write_new(out / 'excluded-identity-inventory.json', {
            'recordingKeys': sorted(keys), 'hashes': sorted(hashes),
            'fittingSignerIds': sorted(fitting), 'sourceInputsSha256': inputs,
            'scope': 'Available local provenance plus all prior downloaded online clips, Watch clips and explicit development clips; not all historic private data.'})
        return keys, hashes, fitting, inputs
    acquisition.inventory = expanded_inventory
    acquisition.main(argparse.Namespace(out=batch, min_archive_video_index=args.min_archive_video_index,
                                       allow_unverified_publisher_tls=args.allow_unverified_publisher_tls))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True); p.add_argument('--batch', type=Path, required=True)
    p.add_argument('--min-archive-video-index', type=int, default=90)
    p.add_argument('--allow-unverified-publisher-tls', action='store_true')
    main(p.parse_args())
