"""Merge dense targeted re-extractions without duplicating source attempts.

Only original train/validation splits are fitting inputs. Retains non-targeted
classes and rejects Watch-source, signer, or source leakage. Test files are
never read by this preparation stage.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, sys
from pathlib import Path
import numpy as np

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from sign_features import validate_capture
sys.path.insert(0,str(REPO/'scripts'))
from calibrate_motion_models import canonical


def read_rows(path):
    with Path(path).open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def sources(row):
    return {Path(p).name for p in row.get('componentFiles') or [row['file']]}


def verify_splits(rows, watch):
    source_sets, signer_sets=collections.defaultdict(set),collections.defaultdict(set)
    for row in rows:
        if row.get('split') not in ('train','val'):raise ValueError('Fitting input must be train/val')
        if sources(row)&watch:raise ValueError('Watch source in fitting input')
        participants={p for p in row.get('participants') or [row.get('participant')] if p}
        if not participants:raise ValueError('Missing original participant')
        source_sets[row['split']].update(sources(row));signer_sets[row['split']].update(participants)
    if source_sets['train']&source_sets['val']:raise ValueError('Train/val source leakage')
    if signer_sets['train']&signer_sets['val']:raise ValueError('Train/val signer leakage')


def fitting_rows(rows,watch):
    return [dict(r) for r in rows if r.get('split') in ('train','val') and not sources(r)&watch]


def usable(row):
    try:
        if row.get('error'):return False
        validate_capture(row.get('frames') or [])
        return True
    except (ValueError,TypeError):return False


def duplicates(rows):
    """Diagnostic only: never remove touching/crossing hands by this metric."""
    paired=near=0;files=[]
    for row in rows:
        count=0
        for frame in row.get('frames') or []:
            a,b=frame.get('left'),frame.get('right')
            if a is None or b is None:continue
            a,b=np.asarray(a),np.asarray(b)
            if a.shape!=b.shape or a.shape[0]!=21:continue
            paired+=1
            if float(np.sqrt(((a[:,:2]-b[:,:2])**2).mean()))<.001:
                near+=1;count+=1
        if count:files.append({'file':row['file'],'nearIdenticalFrames':count})
    return {'pairedFrames':paired,'nearIdenticalXYFrames':near,'threshold':.001,'files':files,
            'scope':'Diagnostic coordinate similarity, not proof of erroneous anatomy; no hands removed.'}


def body_row(row,label):
    out={k:v for k,v in row.items() if k not in ('rawFrames','manualLabel','beginnerLabel','capstoneLabel','cached','path')}
    out['label']=label
    # The deployed body capture appends only pose + at least one observed hand.
    # Match that contract without inventing coordinates or filling hand gaps.
    # The unfiltered native archive retains every sampled frame for diagnosis.
    frames=row.get('frames') or []
    keep=[i for i,f in enumerate(frames) if f.get('pose') is not None and (f.get('left') or f.get('right'))]
    out['frames']=[frames[i] for i in keep]
    if len(row.get('bodyTimestamps',[]))==len(frames):out['bodyTimestamps']=[row['bodyTimestamps'][i] for i in keep]
    out['captureContract']='pose plus at least one real hand; missing second hand retained'
    return out


def merge_family(old,native,key,labels):
    merged={r['file']:dict(r,label=r.get('label') or r['gloss']) for r in old}
    added=replaced=0
    for row in native:
        label=row.get(key)
        if label not in labels:continue
        if row['file'] in merged:replaced+=1
        else:added+=1
        merged[row['file']]=body_row(row,label)
    return list(merged.values()),{'newSources':added,'reextractedSources':replaced}


def negatives(known,other,native,labels):
    known_sources=set().union(*(sources(r) for r in known))
    forms={canonical(n) for n in labels};pool={}
    for row in other+[body_row(r,r.get('manualLabel') or r['gloss']) for r in native]:
        label=row.get('label') or row['gloss']
        if row.get('syntheticGreeting') or sources(row)&known_sources or canonical(label) in forms:continue
        pool[row['file']]=dict(row,label=label)
    return list(pool.values())


def write(path,rows):
    if path.exists():raise FileExistsError(path)
    path.write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows),encoding='utf-8')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(args):
    manifest=json.loads(args.manifest.read_text(encoding='utf-8'))
    required={r['file'] for r in manifest if r['split'] in ('train','val')}
    native={r['file']:r for r in read_rows(args.native) if r['split'] in ('train','val')}
    if required-set(native):raise ValueError(f'Incomplete native extraction: {len(required-set(native))} missing sources')
    if any(r.get('error') for r in native.values()):raise ValueError('Extraction errors need explicit repair before fitting')
    native=list(native.values())
    watch={s['originalFile'] for item in json.loads((REPO/'models/recognition-videos.json').read_text(encoding='utf-8'))['items'] for s in item.get('sources',[])}
    beginner_old=fitting_rows(read_rows(args.beginner),watch)
    full_old=fitting_rows(read_rows(args.full),watch)
    beginner_names=json.loads((REPO/'models/beginner-100-label-map.json').read_text(encoding='utf-8'))['trainLabels']
    full_names=sorted({r.get('label') or r['gloss'] for r in full_old})
    beginner,bcounts=merge_family(beginner_old,native,'beginnerLabel',beginner_names)
    full,fcounts=merge_family(full_old,native,'capstoneLabel',full_names)
    bneg=negatives(beginner,full,native,beginner_names);fneg=negatives(full,beginner,native,full_names)
    outputs={'beginner':beginner,'capstone':full,'beginner-negatives':bneg,'capstone-negatives':fneg}
    for rows in outputs.values():verify_splits(rows,watch)
    args.out.mkdir(parents=True,exist_ok=True)
    hashes={name:write(args.out/(name+'.jsonl'),rows) for name,rows in outputs.items()}
    paired=[]
    old_by_file={r['file']:r for r in beginner_old+full_old}
    for row in native:
        old=old_by_file.get(row['file'])
        if old:
            tracked=lambda r:sum(bool(f.get('left') or f.get('right')) for f in r.get('frames') or [])
            paired.append({'file':row['file'],'oldTracked':tracked(old),'newTracked':tracked(row),'oldUsable':usable(old),'newUsable':usable(row)})
    audit={'selectionManifestSha256':hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
           'nativeSha256':hashlib.sha256(args.native.read_bytes()).hexdigest(),'outputs':hashes,
           'nativeAttempts':len(native),'newSourceRecordings':sum(not r['previouslyExtracted'] for r in native),
           'beginner':bcounts,'capstone':fcounts,'testReadForPreparation':False,'watchExcluded':True,
           'signersAndSourcesDisjoint':True,'counts':{name:dict(collections.Counter(r['split'] for r in rows)) for name,rows in outputs.items()},
           'usable':{name:dict(collections.Counter(r['split'] for r in rows if usable(r))) for name,rows in outputs.items()},
           'pairedTracking':paired,'oldDuplicateHandDiagnostic':duplicates(list(old_by_file.values())),
           'nativeDuplicateHandDiagnostic':duplicates(native),
           'scope':'Targeted full-clip train/val extraction. Non-targeted features and explicitly synthetic greetings retained. No deployment or accuracy claim.'}
    (args.out/'preparation-audit.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in audit.items() if k not in ('pairedTracking','oldDuplicateHandDiagnostic','nativeDuplicateHandDiagnostic')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('manifest','native','beginner','full','out'):parser.add_argument('--'+key,type=Path,required=True)
    prepare(parser.parse_args())
