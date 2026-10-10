"""Prepare body-free ordinary negatives alongside unchanged ASL development data."""
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing
from pathlib import Path
import run_dynamic_pose_training as extractor
from motion_window import align_window

ROOT=Path('/opt/handspeak-training/ordinary-development-ucf101')
OUT=Path('/opt/handspeak-training/vocabulary-expansion-ordinary-source')
BASE=Path('/opt/handspeak-training/vocabulary-expansion-hands-only-source')


def write(path,data):
    temporary=path.with_suffix('.partial')
    temporary.write_text(json.dumps(data,indent=2)+'\n');temporary.replace(path)


def main():
    OUT.mkdir(exist_ok=True);(ROOT/'frames').mkdir(exist_ok=True)
    review=json.loads((ROOT/'content-review.json').read_text())
    if not review['acceptedForOrdinaryActionDevelopment'] or review['manifestSha256']!=extractor.digest(ROOT/'manifest.json'):
        raise ValueError('Development media review missing or changed')
    rows=json.loads((ROOT/'manifest.json').read_text())
    if any(r['split'] not in ('train','val') or not 4<=r['group']<=18 for r in rows):
        raise ValueError('Reserved/test media entered development')
    ep=json.loads(Path('/opt/handspeak-training/vocabulary-expansion-dynamic-pose/extraction-protocol.json').read_text())
    write(ROOT/'extraction-protocol.json',ep)
    samples=[]
    with ProcessPoolExecutor(max_workers=2,mp_context=multiprocessing.get_context('spawn')) as pool:
        for path in pool.map(extractor.extract,[(r,str(ROOT),extractor.protocol_digest(ep)) for r in rows]):
            row=align_window(json.loads(Path(path).read_text()))
            row['body']=[None]*len(row['rawFrames']);samples.append(row)
            write(OUT/'job-status.json',dict(stage='extract',state='running',processed=len(samples),total=len(rows),deployed=False))
    base=json.loads((BASE/'protocol.json').read_text())
    if extractor.digest(base['source'])!=base['sourceSha256']:raise ValueError('Base source changed')
    data=json.loads(Path(base['source']).read_text())
    if {r['sha256'] for r in data}&{r['sha256'] for r in samples}:raise ValueError('Duplicate content')
    source=OUT/'development-features.json'
    source.write_text(json.dumps(data+samples,separators=(',',':')))
    protocol=dict(base,source=str(source),sourceSha256=extractor.digest(source),
                  parentSourceSha256=base['sourceSha256'],ordinaryManifestSha256=extractor.digest(ROOT/'manifest.json'),
                  ordinaryReviewSha256=extractor.digest(ROOT/'content-review.json'),
                  change='Add 48 ordinary-action train clips and 12 validation clips as rejection examples. Original ASL rows unchanged. All body references null.',
                  ordinaryGrouping='Recording groups, not verified distinct persons',
                  implementationSha256=extractor.digest(__file__))
    write(OUT/'protocol.json',protocol)
    write(OUT/'job-status.json',dict(stage='complete',state='complete',ordinaryClips=len(samples),
          usableBySplit={split:sum(r['split']==split and r['sequence'] is not None for r in samples) for split in ('train','val')},deployed=False))


if __name__=='__main__':main()
