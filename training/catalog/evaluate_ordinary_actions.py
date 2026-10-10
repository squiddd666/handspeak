"""Test a frozen candidate on reviewed ordinary-action clips; no training/deployment."""
import concurrent.futures as futures
import argparse
import hashlib
import json
import multiprocessing
from pathlib import Path
import shutil

import evaluate_ready_subset as candidate
import evaluate_hands_only_candidate as hands_candidate
import run_dynamic_pose_training as extractor
from motion_window import align_window

ROOT=Path('/opt/handspeak-training/ordinary-movement-ucf101')
MODEL=Path('/opt/handspeak-training/vocabulary-expansion-expanded-fresh')
REPORT=Path('/opt/handspeak/repository/reports/vocabulary-expansion/ordinary-actions')


def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.partial');temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(path)


def main():
    global ROOT, MODEL, REPORT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',type=Path,default=MODEL)
    parser.add_argument('--output',type=Path,default=ROOT)
    parser.add_argument('--report',type=Path,default=REPORT)
    parser.add_argument('--media',type=Path,default=ROOT)
    parser.add_argument('--hands-only',action='store_true')
    parser.add_argument('--fresh',action='store_true')
    args=parser.parse_args()
    ROOT,MODEL,REPORT=args.output.resolve(),args.model.resolve(),args.report.resolve()
    media=args.media.resolve()
    ROOT.mkdir(parents=True,exist_ok=True)
    candidate.ROOT=MODEL
    def verify_model():
        if not args.hands_only:return candidate.verify()
        value=json.loads((MODEL/'protocol.json').read_text())
        if value.get('featureMode')!='hands-only' or candidate.sha(MODEL/'frozen.pt')!=value['checkpointSha256']:
            raise ValueError('Hands-only model changed')
        if any(candidate.sha(path)!=digest for path,digest in value['implementations'].items()):
            raise ValueError('Hands-only implementation changed')
        return value
    p=verify_model()
    manifest=media/'manifest.json';rows=json.loads(manifest.read_text())
    review=json.loads((media/'content-review.json').read_text())
    if not review['acceptedForOrdinaryActionScreen'] or review['manifestSha256']!=candidate.sha(manifest):
        raise ValueError('Media review missing or stale')
    if args.fresh:
        selection=json.loads((media/'protocol.json').read_text())
        if (selection.get('checkpointSha256')!=p['checkpointSha256'] or
                selection.get('frozenModelProtocolSha256')!=candidate.sha(MODEL/'protocol.json')):
            raise ValueError('Fresh media must be selected after model freeze')
    protocol=dict(modelProtocolSha256=candidate.sha(MODEL/'protocol.json'),
                  checkpointSha256=p['checkpointSha256'],manifestSha256=candidate.sha(manifest),
                  implementationSha256=candidate.sha(__file__),labels=p['labels'],
                  gate='Zero suggestions and at least one usable tracked clip per action',
                  mediaPreviouslyUsedForEvaluation=not args.fresh,
                  scope='Whole recorded clips, not rolling windows, real-time camera paths, or broad everyday-movement accuracy',deployed=False)
    path=ROOT/'evaluation-protocol.json'
    if path.exists() and json.loads(path.read_text())!=protocol:raise ValueError('Frozen ordinary-action evaluation changed')
    write(path,protocol);shutil.copyfile(__file__,ROOT/'evaluation-source.py')
    ep=json.loads(Path('/opt/handspeak-training/vocabulary-expansion-dynamic-pose/extraction-protocol.json').read_text())
    write(ROOT/'extraction-protocol.json',ep);(ROOT/'frames').mkdir(exist_ok=True)
    samples=[]
    with futures.ProcessPoolExecutor(max_workers=1,mp_context=multiprocessing.get_context('spawn')) as pool:
        for path in pool.map(extractor.extract,[(r,str(ROOT),extractor.protocol_digest(ep)) for r in rows]):
            samples.append(align_window(json.loads(Path(path).read_text())))
    verify_model()
    predicted=(hands_candidate.predict(samples,MODEL/'frozen.pt',p) if args.hands_only else candidate.infer(samples,p))
    actions=sorted({r['action'] for r in rows})
    coverage={a:sum(r['action']==a and r['sequence'] is not None for r in samples) for a in actions}
    result=dict(total=len(rows),falseSuggestions=sum(v is not None for v in predicted),
                usableTrackedClips=sum(coverage.values()),usablePerAction=coverage,
                passesWholeClipScreen=not any(predicted) and all(coverage.values()),
                scope=protocol['scope'],checkpointSha256=p['checkpointSha256'],deployed=False,
                predictions=[dict(action=r['action'],group=r['group'],sha256=r['sha256'],
                                  trackedFrames=r['trackedFrames'],usable=r['sequence'] is not None,predicted=v)
                             for r,v in zip(samples,predicted)])
    write(ROOT/'evaluation.json',result);write(REPORT/'evaluation.json',result)
    write(REPORT/'protocol.json',protocol);print(json.dumps(result),flush=True)


if __name__=='__main__':main()
