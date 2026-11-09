"""Finish the local targeted train/validation pipeline; never deploy weights.

Waits for the already-running native extraction, verifies all selected fitting
sources exist, then fine-tunes and compares candidates against frozen v3.
No browser control, independent test evaluation, or source uploads occur here.
"""
from __future__ import annotations
import argparse,json,shutil,subprocess,sys,time
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
EVAL=REPO.parent/'hs-eval'


def run(*args):
    command=[sys.executable,*map(str,args)]
    print('RUN',json.dumps(command),flush=True)
    subprocess.run(command,cwd=REPO,check=True)


def main(args):
    selection=EVAL/'motion-repair-v4-20261107/selection.json'
    native=EVAL/'motion-repair-v4-20261107/native-trainval.jsonl'
    required={r['file'] for r in json.loads(selection.read_text(encoding='utf-8')) if r['split'] in ('train','val')}
    start=time.monotonic();last=-1
    while True:
        rows={}
        if native.exists():
            with native.open(encoding='utf-8') as stream:
                for line in stream:
                    try:r=json.loads(line)
                    except json.JSONDecodeError:continue # final write may be in progress
                    rows[r['file']]=bool(r.get('error'))
        if len(rows)!=last and (last<0 or len(rows)-last>=100):
            print('Extraction readiness',len(rows),'/',len(required),flush=True);last=len(rows)
        if required<=set(rows):
            if any(rows[file] for file in required):raise ValueError('Native extraction errors remain; not fitting')
            break
        if time.monotonic()-start>args.wait_seconds:raise TimeoutError('Native extraction not complete; v3 preserved')
        time.sleep(10)
    root=args.out.resolve();root.mkdir(parents=True,exist_ok=True)
    baseline=root/'baseline-v3.json'
    if not baseline.exists():shutil.copyfile(REPO/'models/motion-calibration.json',baseline)
    data=EVAL/'motion-repair-v4-20261107/fitting'
    if not (data/'preparation-audit.json').exists():
        run('scripts/prepare_native_repair_v4.py','--manifest',selection,'--native',native,
            '--beginner',EVAL/'motion-repair-20261107/features-beginner-repaired.jsonl',
            '--full',EVAL/'features-train-merged.jsonl','--out',data)
    candidates=root/'candidates';candidates.mkdir(exist_ok=True)
    for family,base in (('beginner',REPO/'models/beginner-repaired-v2.pt'),
                        ('capstone',REPO/'third_party/microsoft_asl_citizen/capstone100-v4-ensemble.pt')):
        candidate=candidates/(family+'-handshape.pt')
        history=candidate.with_suffix('.history.json')
        complete=history.exists() and len(json.loads(history.read_text(encoding='utf-8'))['history'])==args.epochs
        if not complete:
            if candidate.exists() or history.exists():raise FileExistsError('Interrupted candidate requires a new output name; not overwriting')
            run('scripts/train_handshape_repair.py','--features',data/(family+'.jsonl'),
                '--negative-features',data/(family+'-negatives.jsonl'),'--base',base,
                '--init-auxiliary',REPO/'models'/(family+'-handshape-v3.pt'),
                '--lr','.0003','--epochs',args.epochs,'--threads',args.threads,'--seed','53','--out',candidate)
        output=root/('selection-'+family+'.json')
        if not output.exists():
            run('scripts/select_native_repair_v4.py','--family',family,'--base',base,'--baseline',baseline,
                '--auxiliary',candidate,'--features',data/(family+'.jsonl'),
                '--negative-features',data/(family+'-negatives.jsonl'),'--out',output,'--threads',args.threads)
    summary={family:json.loads((root/('selection-'+family+'.json')).read_text(encoding='utf-8'))['deployable'] for family in ('beginner','capstone')}
    (root/'pipeline-complete.json').write_text(json.dumps({'candidateOnly':True,'deployed':False,'independentTestRead':False,'validationEligible':summary},indent=2)+'\n',encoding='utf-8')
    print('Candidate-only pipeline complete',summary,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=REPO/'reports/motion-repair-v4-20261107')
    parser.add_argument('--epochs',type=int,default=30);parser.add_argument('--threads',type=int,default=3)
    parser.add_argument('--wait-seconds',type=int,default=7200)
    main(parser.parse_args())
