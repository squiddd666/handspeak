"""Compare rejection candidate JS/Python on validation only, no gate changes."""
import argparse,json,subprocess
from pathlib import Path
import numpy as np
from scripts.run_online_native_audit import ROOT,sha
from scripts.train_manual_open_set_guard import verify_dev,statistics,apply_gate
from scripts.audit_body_manual_v5 import Baseline,BASELINE_FILES
from scripts.train_native_manual_v4 import dtw_many,mirrored


def main(args):
    folder=args.protocol.resolve().parent;p=json.loads(args.protocol.read_text('utf-8'));verify_dev(p)
    v=json.loads((folder/'validation.json').read_text('utf-8'));model=json.loads((folder/'candidate.json').read_text('utf-8'))
    if sha(folder/'candidate.json')!=v['modelSha256'] or v['testUsedForSelection'] or v['auditOutcomesReadForSelection']:raise ValueError('Candidate identity/provenance mismatch')
    raw=[json.loads(l) for l in Path(p['nativeArchive']).read_text('utf-8').splitlines() if l.strip()];raw={r['file']:r for r in raw if r['split']=='val'}
    exact_input=dict(models={k:json.loads((ROOT/n).read_text('utf-8')) for k,n in BASELINE_FILES.items()},
        cases=[dict(rawFrames=raw[record['file']]['rawFrames'],imageAspect=raw[record['file']]['imageAspect']) for record in v['records']])
    run=subprocess.run(['C:/Program Files/nodejs/node.exe',str(ROOT/'training/ux/run_manual_guard_baseline.mjs')],input=json.dumps(exact_input),text=True,capture_output=True,check=True)
    current=json.loads(run.stdout);cases=[]
    for record,actual_baseline in zip(v['records'],current):
        if record['baseline']!=actual_baseline['baseline']:raise ValueError('Frozen validation baseline differs from actual route kernels')
        seq=actual_baseline['sequence']
        # Only features and already-computed baseline outputs enter JS; no
        # expected label, recording id, signer or lesson reaches the guard.
        cases.append(dict(sequence=seq,baseline=record['baseline']))
    module=(ROOT/'training/experimental/manual_open_set_guard.mjs').as_uri()
    code="import {applyManualOpenSetGuard,manualGuardStatistics} from "+json.dumps(module)+";let s='';for await(const c of process.stdin)s+=c;const x=JSON.parse(s);process.stdout.write(JSON.stringify(x.cases.map(c=>({ ...applyManualOpenSetGuard(x.model,c.sequence,c.baseline),distances:manualGuardStatistics(x.model,c.sequence)}))));"
    run=subprocess.run(['C:/Program Files/nodejs/node.exe','--input-type=module','-e',code],input=json.dumps(dict(model=model,cases=cases)),text=True,capture_output=True,check=True)
    results=json.loads(run.stdout);max_error=0.;refs=np.asarray([r['sequence'] for r in model['samples']])
    for case,actual,expected in zip(cases,results,v['records']):
        if actual['predictions']!=expected['candidate']:raise ValueError('Candidate JS/Python prediction mismatch')
        if any(actual['predictions'][m] is not None and actual['predictions'][m]!=case['baseline'][m] for m in model['modes']):raise ValueError('Rejection-only guarantee violated')
        if case['sequence'] is None:continue
        seq=np.asarray(case['sequence']);d=np.minimum(dtw_many(seq,refs),dtw_many(mirrored(seq),refs))
        for label,actual_d in actual['distances'].items():max_error=max(max_error,abs(actual_d-statistics(d,model['samples'],label)[0]))
    verify_dev(p)
    receipt=dict(cases=len(cases),independentModeOutcomes=len(cases)*4,baselineMatchesActualCurrentJavaScript=True,predictionsIdentical=True,rejectionOnlyGuaranteed=True,
        maximumSameLabelDistanceError=max_error,modelSha256=sha(folder/'candidate.json'),runtimeSha256=sha(ROOT/'training/experimental/manual_open_set_guard.mjs'),
        testRead=False,auditOutcomesRead=False,gateChanges=False,productionFilesUnchanged=True,browserCaptureVerified=False)
    with (folder/'runtime-parity.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2)
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--protocol',type=Path,required=True);main(parser.parse_args())
