"""Whole-clip ordinary-action screen for the frozen calibrated candidate."""
import concurrent.futures as futures
import json
import multiprocessing
from pathlib import Path
import evaluate_calibrated_candidate as candidate
import run_dynamic_pose_training as extractor
ROOT=Path('/opt/handspeak-training/ordinary-movement-fresh22')
OUTPUT=Path('/opt/handspeak-training/framing-ordinary-fresh22')
REPORT=Path('/opt/handspeak/repository/reports/vocabulary-expansion/framing-ordinary-fresh22')

def main():
    p=candidate.verify();rows=json.loads((ROOT/'manifest.json').read_text());review=json.loads((ROOT/'content-review.json').read_text());selection=json.loads((ROOT/'protocol.json').read_text())
    if not review['acceptedForOrdinaryActionScreen'] or review['manifestSha256']!=candidate.sha(ROOT/'manifest.json'):raise ValueError('Review absent or changed')
    if selection['checkpointSha256']!=p['checkpointSha256'] or selection['frozenModelProtocolSha256']!=candidate.sha(candidate.ROOT/'protocol.json'):raise ValueError('Model was not frozen before selection')
    if any(candidate.sha(r['file'])!=r['sha256'] for r in rows):raise ValueError('Recording changed')
    protocol=dict(checkpointSha256=p['checkpointSha256'],modelProtocolSha256=selection['frozenModelProtocolSha256'],manifestSha256=review['manifestSha256'],reviewSha256=candidate.sha(ROOT/'content-review.json'),implementationSha256=candidate.sha(__file__),scope='Fresh ordinary recording groups, not verified unique people or real-time camera accuracy',gate='Zero suggestions; at least one usable tracked clip per action',deployed=False)
    if (OUTPUT/'evaluation-protocol.json').exists():raise ValueError('Evaluation already frozen')
    candidate.write(OUTPUT/'evaluation-protocol.json',protocol);ep=json.loads(Path('/opt/handspeak-training/vocabulary-expansion-dynamic-pose/extraction-protocol.json').read_text());candidate.write(OUTPUT/'extraction-protocol.json',ep);(OUTPUT/'frames').mkdir(exist_ok=True)
    samples=[]
    with futures.ProcessPoolExecutor(max_workers=1,mp_context=multiprocessing.get_context('spawn')) as pool:
        for path in pool.map(extractor.extract,[(r,str(OUTPUT),extractor.protocol_digest(ep)) for r in rows]):samples.append(json.loads(Path(path).read_text()))
    candidate.verify();predicted=candidate.infer(samples,p);coverage={a:sum(r['action']==a and r['sequence'] is not None for r in samples) for a in sorted({r['action'] for r in samples})}
    result=dict(total=len(samples),falseSuggestions=sum(v is not None for v in predicted),usableTrackedClips=sum(coverage.values()),usablePerAction=coverage,passesWholeClipScreen=not any(predicted) and all(coverage.values()),checkpointSha256=p['checkpointSha256'],scope=protocol['scope'],deployed=False,predictions=[dict(action=r['action'],group=r['group'],sha256=r['sha256'],usable=r['sequence'] is not None,trackedFrames=r['trackedFrames'],predicted=v) for r,v in zip(samples,predicted)])
    candidate.write(OUTPUT/'evaluation.json',result);candidate.write(REPORT/'evaluation.json',result);candidate.write(REPORT/'protocol.json',protocol);print(json.dumps(result),flush=True)
if __name__=='__main__':main()
