"""One-pass native extraction and label-blind frozen classifier audit.

Offline full-clip sampling, not the production browser or a new-signer claim.
Never trains, selects thresholds, retries a take, or drops failed recordings.
"""
from __future__ import annotations
import argparse,concurrent.futures,hashlib,json,math,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT))


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def verify(protocol):
    for name,digest in protocol['frozenFilesSha256'].items():
        if sha(Path(name))!=digest:raise ValueError('Frozen audit input changed: '+name)


def extract_phase(protocol,folder):
    from extract_native_motion_v4 import initialize,extract
    native=folder/'native.jsonl'
    if native.exists():raise FileExistsError('One-pass extraction already attempted')
    cohort=json.loads(Path(protocol['cohort']).read_text(encoding='utf-8'))['clips']
    # Decoder inputs contain no evaluation labels, including for negatives.
    inputs=[{k:r[k] for k in ('file','path','participant','sha256','sourceId','split')} for r in cohort]
    with concurrent.futures.ProcessPoolExecutor(max_workers=2,initializer=initialize,
            initargs=(protocol['nativeHandModel'],32)) as pool,native.open('x',encoding='utf-8') as sink:
        for index,row in enumerate(pool.map(extract,inputs),1):
            sink.write(json.dumps(row,separators=(',',':'))+'\n');sink.flush()
            print('native extraction',index,'/',len(inputs),'body',row.get('trackedFrames'),'hands',row.get('manualTrackedFrames'),'error',row.get('error'),flush=True)


class FrozenManual:
    def __init__(self):
        # Existing vectorized DTW has an explicit-cost and JS-kernel parity test.
        from audit_body_manual_v5 import Baseline
        self.base=Baseline()
        import re
        code=(ROOT/'training/experimental/online_manual_runtime.mjs').read_text(encoding='utf-8')
        self.base.js.eval(re.sub(r'^import .*?;\s*','',code,flags=re.M).replace('export ',''))

    def predict(self,raw,aspect):
        import numpy as np
        from train_native_manual_v4 import dtw_many,mirrored
        base=self.base
        base.js.eval('var currentAudit=prepareAudit('+json.dumps(raw)+','+str(aspect)+'); currentAudit.aspect='+str(aspect)+';')
        sequence=json.loads(base.js.eval('JSON.stringify(currentAudit.sequence)'))
        if sequence is None:direct=mirror=np.full(len(base.refs),1e100)
        else:
            a=np.asarray(sequence);direct,mirror=dtw_many(a,base.refs),dtw_many(mirrored(a),base.refs)
        base.js.eval('auditDirect='+json.dumps(direct.tolist())+';auditMirror='+json.dumps(mirror.tolist())+';')
        return json.loads(base.js.eval('JSON.stringify(predictManualRoutes(auditModels,currentAudit.frames,currentAudit.aspect))'))


class FrozenCandidate:
    def __init__(self,path):
        import numpy as np
        self.model=json.loads(Path(path).read_text(encoding='utf-8'))
        self.refs=np.asarray([r['sequence'] for r in self.model['samples']])

    def predict(self,frames,aspect):
        import numpy as np
        from body_manual_features import tensorize,mirrored,dtw_many
        from train_body_manual_v5 import gate_statistics,gate_mask
        filtered=[f for f in frames if f.get('pose') and (f.get('left') or f.get('right'))]
        sequence=tensorize({'frames':filtered,'imageAspect':aspect})
        if sequence is None:return dict(prediction=None,tracked=False,distance=None,separation=None,votes=0)
        p=self.model['featureParameters']
        distance=np.minimum(dtw_many(sequence,self.refs,**p),dtw_many(mirrored(sequence),self.refs,**p))[None,:]
        stats=gate_statistics(distance,self.model['samples'],self.model['labels'])
        accepted=bool(gate_mask(stats,self.model['parameters'])[0])
        finite=lambda x:float(x) if math.isfinite(float(x)) else None
        return dict(prediction=str(stats[0][0]) if accepted else None,tracked=True,
                    distance=finite(stats[2][0]),separation=finite(stats[3][0]),votes=int(stats[4][0]))


def predict_phase(protocol,folder):
    target=folder/'native-predictions.jsonl'
    if target.exists():raise FileExistsError('Native predictions already attempted; no best-of reruns')
    cohort=json.loads(Path(protocol['cohort']).read_text(encoding='utf-8'))['clips']
    native=[json.loads(line) for line in (folder/'native.jsonl').read_text(encoding='utf-8').splitlines() if line]
    if [r['file'] for r in cohort]!=[r['file'] for r in native]:raise ValueError('Incomplete or reordered one-pass extraction')
    manual=FrozenManual();candidate=FrozenCandidate(protocol['candidate'])
    with target.open('x',encoding='utf-8') as sink:
        for index,row in enumerate(native,1):
            result=dict(file=row['file'],status='failed' if row.get('error') else 'complete',error=row.get('error'),
                        selectedFrames=row.get('selectedFrames',0),bodyTrackedFrames=row.get('trackedFrames',0),
                        manualTrackedFrames=row.get('manualTrackedFrames',0),sourceDimensions=row.get('sourceDimensions'),
                        duration=row.get('duration'),sourceSha256=row['sha256'],candidate=None,
                        candidateTracked=False,manual={mode:None for mode in protocol['manualModes']})
            try:
                if not row.get('error'):
                    result['manual']=manual.predict(row['rawFrames'],row['imageAspect'])
                    c=candidate.predict(row['frames'],row['imageAspect'])
                    result.update(candidate=c['prediction'],candidateTracked=c['tracked'],candidateDistance=c['distance'],
                                  candidateSeparation=c['separation'],candidateVotes=c['votes'])
            except Exception as error:
                result.update(status='failed',error=str(error),candidate=None,manual={mode:None for mode in protocol['manualModes']})
            # Annotations are only joined by the report AFTER all prediction calls.
            sink.write(json.dumps(result,allow_nan=False,separators=(',',':'))+'\n');sink.flush()
            print('native prediction',index,'/',len(native),result['file'],'body',result['candidate'],'manual',result['manual'],'status',result['status'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--protocol',type=Path,required=True)
    parser.add_argument('--phase',choices=['extract','predict'],required=True);args=parser.parse_args()
    protocol=json.loads(args.protocol.read_text(encoding='utf-8'));verify(protocol)
    folder=args.protocol.resolve().parent;started=time.monotonic()
    (extract_phase if args.phase=='extract' else predict_phase)(protocol,folder)
    verify(protocol);print(args.phase,'completed in',round(time.monotonic()-started,2),'seconds',flush=True)
