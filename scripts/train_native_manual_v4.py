"""Build a local 24-word hand-only template candidate on train/val only.

Uses the exact on-device usable-hand filter and motion encoding via QuickJS.
An explicit OTHER MOVEMENT competitor and independent validation negatives
are retained. This experimental model is not substituted into existing routes.
"""
from __future__ import annotations
import argparse,collections,hashlib,itertools,json,sys
from pathlib import Path
import numpy as np
import quickjs
from prepare_native_repair_v4 import REPO,read_rows,verify_splits
from prepare_targeted_data_v4 import MANUAL


def mirrored(a):
    a=np.concatenate([a[:,64:],a[:,:64]],axis=1).copy()
    a[:,1:64:3]*=-1;a[:,65:128:3]*=-1
    return a


def dtw_many(a,refs):
    """Exact motionDistance band/cost, vectorized over training references."""
    a=np.asarray(a,float);refs=np.asarray(refs,float);n=len(refs)
    cost=np.zeros((n,20,20));weights=np.tile([1,1,.5],21)
    for off in (0,64):
        x=a[:,off+1:off+64]*weights;y=refs[:,:,off+1:off+64]*weights
        squared=np.sum(x*x,1)[None,:,None]+np.sum(y*y,2)[:,None,:]-2*np.einsum('ic,njc->nij',x,y)
        both=a[None,:,off,None]*refs[:,None,:,off]
        mismatch=a[None,:,off,None]!=refs[:,None,:,off]
        cost+=np.sqrt(np.maximum(0,squared)/63)*both+2*mismatch
    previous=np.full((n,21),np.inf);previous[:,0]=0
    for i in range(1,21):
        current=np.full((n,21),np.inf)
        for j in range(max(1,i-5),min(20,i+5)+1):
            current[:,j]=cost[:,i-1,j-1]+np.minimum(np.minimum(previous[:,j],current[:,j-1]),previous[:,j-1])
        previous=current
    return previous[:,-1]/20


def matrix(rows,refs):
    sequences=np.asarray([r['sequence'] for r in refs]);out=[]
    for row in rows:
        if row['sequence'] is None:out.append(np.full(len(refs),np.inf));continue
        a=np.asarray(row['sequence']);out.append(np.minimum(dtw_many(a,sequences),dtw_many(mirrored(a),sequences)))
    return np.asarray(out)


def prototypes(rows,count):
    if len(rows)<=count:return rows
    d=matrix(rows,rows);selected=[int(np.argmin(np.median(d,axis=1)))]
    while len(selected)<count:
        distance=d[:,selected].min(1);distance[selected]=-1
        selected.append(int(np.argmax(distance)))
    return [rows[i] for i in selected]


def predictions(d,refs,p,labels):
    ref_labels=np.asarray([r['label'] for r in refs]);result=[]
    for distance in d:
        ranking=np.argsort(distance,kind='stable');label=ref_labels[ranking[0]];best=distance[ranking[0]]
        other=next(distance[i] for i in ranking if ref_labels[i]!=label)
        ratio=other/(best+1e-6) if np.isfinite(best) else 0
        votes=int((ref_labels[ranking[:3]]==label).sum())
        result.append(str(label) if label in labels and best<=p['maxDistance'] and ratio>=p['minRatio'] and (votes>=p['minVotes'] or ratio>=p['strongRatio']) else None)
    return result


def metrics(rows,out,labels):
    known=np.asarray([r['label'] in labels for r in rows]);accepted=np.asarray([p is not None for p in out]);correct=np.asarray([r['label']==p for r,p in zip(rows,out)])
    hit=int((known&accepted&correct).sum());wrong=int((known&accepted&~correct).sum());negative=int((~known&accepted).sum())
    return dict(attempts=int(known.sum()),correct=hit,wrong=wrong,noMatch=int((known&~accepted).sum()),negativeAttempts=int((~known).sum()),negativeFalse=negative,
                precision=hit/max(1,hit+wrong),negativeFalseRate=negative/max(1,int((~known).sum())))


def train(args):
    if args.out.exists():raise FileExistsError(args.out)
    rows=[r for r in read_rows(args.native) if r['split'] in ('train','val')]
    watch={s['originalFile'] for item in json.loads((REPO/'models/recognition-videos.json').read_text(encoding='utf-8'))['items'] for s in item.get('sources',[])}
    verify_splits(rows,watch)
    if len({r['file'] for r in rows})!=len(rows):raise ValueError('Duplicate native source')
    js=quickjs.Context()
    for name in ('gesture-model.js','motion-model.js'):js.eval((REPO/name).read_text(encoding='utf-8').replace('export ',''))
    js.eval('function prepareNative(raw,aspect){const frames=raw.map(f=>f.map(h=>isUsableHand(h)?h:null));return {frames,sequence:encodeMotion(frames,aspect)};}')
    data=[]
    for r in rows:
        encoded=json.loads(js.eval('JSON.stringify(prepareNative('+json.dumps(r['rawFrames'])+','+str(r['imageAspect'])+'))'))
        sequence=encoded['sequence']
        if sequence is not None and not js.eval('validMotion('+json.dumps(sequence)+')'):sequence=None
        data.append({k:r[k] for k in ('file','split','participant','gloss','previouslyExtracted')}|{'label':r.get('manualLabel') or r['gloss'],'sequence':sequence})
    labels=list(MANUAL);train=[r for r in data if r['split']=='train' and r['sequence'] is not None]
    val=[r for r in data if r['split']=='val'];refs=[];counts=collections.Counter(r['label'] for r in train)
    if any(counts[label]<3 for label in labels):raise ValueError('Insufficient native manual references: '+str({l:counts[l] for l in labels if counts[l]<3}))
    for label in labels:refs.extend(prototypes([r for r in train if r['label']==label],4))
    other=[r for r in train if r['label'] not in labels];groups=collections.defaultdict(list)
    for r in other:groups[r['gloss']].append(r)
    negative=[]
    for group in sorted(groups):negative.extend(prototypes(groups[group],2))
    negative=sorted(negative,key=lambda r:hashlib.sha256(r['file'].encode()).hexdigest())[:48]
    refs.extend(dict(r,label='OTHER MOVEMENT') for r in negative)
    distances=matrix(val,refs);best=None
    for limit,ratio,votes,strong in itertools.product((.2,.3,.4,.5,.65,.8,1.,1.2,1.5,2.),(1.,1.1,1.3,1.5,2.),(1,2,3),(1.5,2.,3.,5.)):
        if strong<ratio:continue
        p=dict(maxDistance=limit,minRatio=ratio,minVotes=votes,mirror=True,strongRatio=strong)
        out=predictions(distances,refs,p,labels);m=metrics(val,out,labels)
        if m['precision']<.9 or m['negativeFalseRate']>.05:continue
        key=(m['correct'],-m['wrong'],-m['negativeFalse'],-limit,-ratio)
        if best is None or key>best[0]:best=(key,p,m,out)
    if best is None:raise ValueError('No reliable nonempty validation operating point')
    _,parameters,validation,out=best
    model={'version':1,'encoding':'two-hand-motion-v3','labels':labels,'parameters':parameters,
           'samples':[{'label':r['label'],'sequence':r['sequence']} for r in refs],
           'status':'local-research-candidate-not-deployed','source':'ASL Citizen; noncommercial local research, no source redistribution'}
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(model,separators=(',',':')),encoding='utf-8')
    report={'modelSha256':hashlib.sha256(args.out.read_bytes()).hexdigest(),'nativeSha256':hashlib.sha256(args.native.read_bytes()).hexdigest(),
            'selectionSplit':'val','testUsedForSelection':False,'watchClipsUsedForSelection':False,'sourcesAndParticipantsDisjoint':True,
            'trainCounts':{l:counts[l] for l in labels},'negativeReferences':len(negative),'parameters':parameters,'validation':validation,
            'perLabel':{label:metrics([r for r in val if r['label']==label],[o for r,o in zip(val,out) if r['label']==label],labels) for label in labels},
            'records':[dict(file=r['file'],expected=r['label'],prediction=o,tracked=r['sequence'] is not None) for r,o in zip(val,out)],
            'deployed':False,'scope':'Unified hand-only template experiment. Not compared to the current multi-route ensemble, not independently tested, not body-location-aware, not a claim that manual confusions are fixed.'}
    args.out.with_suffix('.validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(validation),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    train(parser.parse_args())
