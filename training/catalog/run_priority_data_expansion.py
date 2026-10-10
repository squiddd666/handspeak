"""Add training signers for weak words, retaining validation and sealed test splits."""
import concurrent.futures as futures
import hashlib
import json
import multiprocessing
from pathlib import Path
import shutil
import subprocess
import sys

import run_dynamic_pose_training as extraction
from motion_window import align_window
import train_expansion_batch as batch

REPO = Path(__file__).resolve().parents[2]
BASE = Path('/opt/handspeak-training/vocabulary-expansion-dynamic-pose')
ROOT = Path('/opt/handspeak-training/vocabulary-expansion-priority-data-v2')
REPORT = REPO / 'reports/vocabulary-expansion/priority-data'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.partial'); tmp.write_text(json.dumps(value) + '\n'); tmp.replace(path)


def status(stage, **extra):
    value = dict(stage=stage, deployed=False, **extra)
    write(ROOT/'job-status.json', value); write(REPORT/'job-status.json', value)
    print(json.dumps(value), flush=True)


def main():
    try:
        ROOT.mkdir(parents=True, exist_ok=True)
        bp=json.loads((BASE/'protocol.json').read_text())
        source=Path(bp['source'])
        if sha(source)!=bp['sourceSha256']: raise ValueError('Development source changed')
        labels_path=ROOT/'training-labels.json'
        labels=json.loads((REPO/'reports/vocabulary-expansion/release-readiness/training-labels.json').read_text())
        metadata_only=Path('/opt/handspeak-training/vocabulary-expansion-ready-fresh-v2/test-manifest.json')
        identities=json.loads(metadata_only.read_text())
        forbidden_signers={str(r['participant']) for r in identities}
        forbidden_hashes={r['sha256'] for r in identities}
        scripts=[Path(__file__), Path(extraction.__file__),REPO/'training/catalog/motion_window.py',
                 REPO/'training/catalog/expand_joint_data.py',REPO/'training/catalog/expand_batch_data.py',
                 REPO/'training/catalog/train_motion_residual.py',REPO/'training/catalog/body_tip_features.py',
                 REPO/'training/catalog/train_expansion_batch.py',REPO/'training/daily_words/train_citizen.py',
                 REPO/'training/accuracy/temporal.py',REPO/'training/catalog/check_residual_browser.py',
                 REPO/'training/accuracy/temporal-browser.js',REPO/'training/accuracy/motion-residual-browser.js',
                 REPO/'gesture-model.js',REPO/'motion-model.js']
        hashes={str(p.relative_to(REPO)):sha(p) for p in scripts}
        frozen=dict(sourceSha256=bp['sourceSha256'],labels=labels,target=72,extractionWorkers=3,implementations=hashes,
                    heldOutIdentityManifestSha256=sha(metadata_only),testMediaOpened=False,
                    change='Additional training signers only; unchanged validation and model settings')
        path=ROOT/'continuation-protocol.json'
        if path.exists() and json.loads(path.read_text())!=frozen: raise ValueError('Frozen experiment changed')
        write(path,frozen);write(labels_path,labels)
        for p in scripts:
            dest=ROOT/'source-snapshot'/p.relative_to(REPO);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)

        def verify():
            if any(sha(REPO/name)!=digest for name,digest in hashes.items()): raise ValueError('Implementation changed during job')

        status('download-training-only',state='running')
        subprocess.run([sys.executable,'training/catalog/expand_joint_data.py','--source',str(source),
                        '--labels-file',str(labels_path),'--output',str(ROOT),'--target','72','--stage','download'],cwd=REPO,check=True)
        verify()
        rows=json.loads((ROOT/'additional-manifest.json').read_text())
        if not rows: raise ValueError('No additional eligible training recordings were found')
        if any(r['split']!='train' or str(r['participant']) in forbidden_signers or r['sha256'] in forbidden_hashes for r in rows):
            raise ValueError('Training additions overlap frozen test identities')
        ep=json.loads((BASE/'extraction-protocol.json').read_text())
        ep.update(source=str(ROOT/'additional-manifest.json'),sourceSha256=sha(ROOT/'additional-manifest.json'))
        write(ROOT/'extraction-protocol.json',ep);(ROOT/'frames').mkdir(exist_ok=True)
        paths=[]
        status('extract-new-training',state='running',processed=0,total=len(rows))
        with futures.ProcessPoolExecutor(max_workers=3,mp_context=multiprocessing.get_context('spawn')) as pool:
            for path in pool.map(extraction.extract,[(r,str(ROOT),extraction.protocol_digest(ep)) for r in rows]):
                paths.append(path);status('extract-new-training',state='running',processed=len(paths),total=len(rows))
        verify()
        data=json.loads(source.read_text());known={r['sha256'] for r in data}
        validation=[r for r in data if r['split']=='val']
        for path in paths:
            row=align_window(json.loads(Path(path).read_text()))
            if row['sha256'] in known: raise ValueError('Duplicate development content')
            known.add(row['sha256']);data.append(row)
        if validation != [r for r in data if r['split']=='val']: raise ValueError('Validation changed')
        if any(str(r['participant']) in forbidden_signers or r['sha256'] in forbidden_hashes for r in data): raise ValueError('Development/test overlap')
        dest=ROOT/'development-features.json';write(dest,data)
        coverage={label:dict(recordings=sum(r['label']==label and r['split']=='train' for r in data),
                    signers=len({str(r['participant']) for r in data if r['label']==label and r['split']=='train'})) for label in labels}
        write(REPORT/'coverage.json',coverage)
        del data,validation
        batch.prepare(dest,ROOT,labels=bp['labels'],separate_negatives=True)
        status('train',state='running')
        subprocess.run([sys.executable,'training/catalog/train_motion_residual.py','--baseline',str(ROOT),
                        '--output',str(ROOT),'--report',str(REPORT),'--body-tips','--masked-augmentation'],cwd=REPO,check=True)
        verify();status('browser-parity',state='running')
        subprocess.run([sys.executable,'training/catalog/check_residual_browser.py','--experiment',str(ROOT),
                        '--report',str(REPORT)],cwd=REPO,check=True)
        verify();result=json.loads((ROOT/'validation.json').read_text())
        status('complete',state='complete',passesValidation=result['passesValidation'],validation=result['selected']['validation'],
               independentAccuracyPassed=False,nextStep='Independent release tests required; no automatic deployment')
    except Exception as exc:
        status('failed',state='failed',error=str(exc));raise


if __name__=='__main__': main()
