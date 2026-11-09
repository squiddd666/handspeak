"""Exact baseline and candidate parity for class-supported guard, VAL only."""
import argparse,json,subprocess
from pathlib import Path
from scripts.run_online_native_audit import ROOT,sha,verify
from scripts.train_manual_open_set_guard import verify_dev
from scripts.audit_body_manual_v5 import BASELINE_FILES


def main(args):
    folder=args.protocol.resolve().parent;p=json.loads(args.protocol.read_text('utf-8'));verify({'frozenFilesSha256':p['frozenInputsSha256']})
    base=Path(p['base']);bp=json.loads((base/'protocol.json').read_text('utf-8'));verify_dev(bp)
    model=json.loads((folder/'candidate.json').read_text('utf-8'));v=json.loads((folder/'validation.json').read_text('utf-8'))
    if sha(folder/'candidate.json')!=v['modelSha256']:raise ValueError('Candidate changed')
    raw={r['file']:r for r in [json.loads(l) for l in Path(bp['nativeArchive']).read_text('utf-8').splitlines() if l.strip()] if r['split']=='val'}
    inp=dict(models={k:json.loads((ROOT/n).read_text('utf-8')) for k,n in BASELINE_FILES.items()},
        cases=[dict(rawFrames=raw[r['file']]['rawFrames'],imageAspect=raw[r['file']]['imageAspect']) for r in v['records']])
    a=subprocess.run(['C:/Program Files/nodejs/node.exe',str(ROOT/'training/ux/run_manual_guard_baseline.mjs')],input=json.dumps(inp),text=True,capture_output=True,check=True)
    cases=json.loads(a.stdout)
    for r,c in zip(v['records'],cases):
        if c['baseline']!=r['baseline']:raise ValueError('Actual baseline mismatch')
    module=(ROOT/'training/experimental/manual_open_set_guard_v2.mjs').as_uri()
    code='import {applyManualOpenSetGuard} from '+json.dumps(module)+";let t='';for await(const c of process.stdin)t+=c;const i=JSON.parse(t);process.stdout.write(JSON.stringify(i.cases.map(c=>applyManualOpenSetGuard(i.model,c.sequence,c.baseline))));"
    a=subprocess.run(['C:/Program Files/nodejs/node.exe','--input-type=module','-e',code],input=json.dumps(dict(model=model,cases=cases)),text=True,capture_output=True,check=True)
    results=json.loads(a.stdout)
    for r,c,new in zip(v['records'],cases,results):
        if new['predictions']!=r['candidate']:raise ValueError('Refined JS/Python predictions differ')
        if any(new['predictions'][m] not in (None,c['baseline'][m]) for m in model['modes']):raise ValueError('Not rejection-only')
    verify_dev(bp);verify({'frozenFilesSha256':p['frozenInputsSha256']})
    report=dict(cases=len(cases),modeOutcomes=len(cases)*4,baselineIdentical=True,refinedPredictionsIdentical=True,rejectionOnly=True,
        modelSha256=sha(folder/'candidate.json'),runtimeSha256=sha(ROOT/'training/experimental/manual_open_set_guard_v2.mjs'),
        testRead=False,auditOutcomesRead=False,gateChanges=False,productionFilesUnchanged=True,browserVerified=False)
    with (folder/'runtime-parity.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--protocol',type=Path,required=True);main(parser.parse_args())
