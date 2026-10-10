"""Resume the frozen selection after storage interruption without selecting new clips."""
import argparse
import collections
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tarfile
import evaluate_calibrated_candidate as evaluation
from calibrate_word_thresholds import sha,write
BASE=Path('/opt/handspeak-training/single-word-20261010')
REPO=Path(__file__).resolve().parents[2]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--word',required=True,choices=['CALL','FIND','FISH','SEE','SICK','PAIN','NIGHT','MORNING']);args=parser.parse_args();slug=args.word.lower();root=BASE/slug
    evaluation.SOURCE=root/'frozen';evaluation.ROOT=root/'fresh';evaluation.REPORT=REPO/'reports/vocabulary-expansion/single-word'/slug/'fresh';evaluation.base.ROOT=evaluation.ROOT;evaluation.base.REPORT=evaluation.REPORT
    p=evaluation.verify();selection=evaluation.ROOT/'selection.json';rows=json.loads(selection.read_text())
    write(evaluation.ROOT/'download-resumption.json',dict(selectionSha256=sha(selection),protocolSha256=sha(evaluation.ROOT/'protocol.json'),implementationSha256=sha(__file__),reason='Resume the exact frozen selection after disk reserve interruption; no outcomes used.'))
    counts=collections.Counter(r['label'] for r in rows)
    if set(counts)!=set(p['mappings']) or any(counts[label]!=(p['targetClipsPerWord'] if label in p['labels'] else p['negativeClipsPerWord']) for label in counts):raise ValueError('Selection coverage differs')
    identities=collections.Counter()
    for r in rows:
        target=evaluation.ROOT/'videos'/r['label']/Path(r['member']).name
        if Path(r['file'])!=target or r['source']!=p['mappings'][r['label']] or r['split']!='test' or str(r['participant']) in p['excludedSigners'] or Path(r['member']).name in p['knownNames']:raise ValueError('Selection identity/path changed')
        identities[(r['label'],str(r['participant']))]+=1
    if max(identities.values())>p['clipsPerSignerCap']:raise ValueError('Signer cap exceeded')
    def get(r):
        header=evaluation.base.request(r['source'],r['offset']-512,512);info=tarfile.TarInfo.frombuf(header,'utf-8','replace')
        if info.name!=r['member'] or info.size!=r['size'] or not info.isfile():raise ValueError('Source header changed')
        return evaluation.base.download(r)
    with ThreadPoolExecutor(max_workers=2) as pool:downloaded=list(pool.map(get,rows))
    hashes=[r['sha256'] for r in downloaded]
    if len(set(hashes))!=len(hashes) or set(hashes)&set(p['knownHashes']):raise ValueError('Previously used/duplicate content')
    evaluation.verify();write(evaluation.ROOT/'test-manifest.json',downloaded)
    evaluation.main();result=json.loads((evaluation.ROOT/'test-results.json').read_text())
    write(evaluation.REPORT.parent/'release-status.json',dict(word=args.word,stage='recording-check-complete',state='complete',passesFreshSignGate=result['passesRecordedClipGate'],deployed=False,remaining='Ordinary, browser-camera and integration checks determine readiness.'))
if __name__=='__main__':main()
