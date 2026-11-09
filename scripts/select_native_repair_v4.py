"""Compare a new auxiliary against deployed v3 on identical validation clips.

No reference or test outputs are inputs. Dense re-extraction changes some
validation features, so recompute both baselines on the exact same attempts.
Promotion requires more correct accepts with no extra wrong/unsupported
accepts; every served vocabulary must be no worse before a family is eligible.
"""
from __future__ import annotations
import argparse, json, sys
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import torch
from asl_model_tools import REPO,digest,load_checkpoint,load_rows,predict,tensorize
from calibrate_motion_models import CORE,EXTRA
from select_handshape_repair import metrics,fit_budget
sys.path.insert(0,str(REPO))
from handshape_features import tensorize as shape_tensorize
from handshape_model import load as load_shape,predict as shape_predict
from handshape_inference import combine


def eligible(before,after):
    return after['correct']>=before['correct'] and after['wrong']<=before['wrong'] and after['negativeFalse']<=before['negativeFalse']


def select(args):
    if args.out.exists():raise FileExistsError(args.out)
    torch.set_num_threads(args.threads)
    config=json.loads(args.baseline.read_text(encoding='utf-8'))
    if config['testUsedForCalibration'] or config['watchClipsUsedForCalibration']:raise ValueError('Contaminated baseline')
    profile=config['models'][args.family]
    models,names,base_blob=load_checkpoint(args.base)
    if digest(args.base)!=profile['checkpointSha256']:raise ValueError('Different deployed baseline')
    _,labels,blob=load_shape(args.auxiliary)
    audit=blob['trainingAudit']
    if audit['testUsedForSelection'] or audit['selectionSplit']!='val' or audit['watchClipsUsedForTrainingOrCalibration']:raise ValueError('Invalid candidate provenance')
    if audit['featuresSha256']!=digest(args.features) or audit['negativeFeaturesSha256']!=digest(args.negative_features):raise ValueError('Fitting data changed')
    if audit['baseCheckpointSha256']!=digest(args.base) or labels!=names+['__UNKNOWN__']:raise ValueError('Candidate baseline/vocabulary differs')
    archive=np.load(args.auxiliary.with_suffix('.val.npz'),allow_pickle=False)
    if list(archive['labels'])!=labels:raise ValueError('Validation label order differs')
    rows_by_file={r['file']:r for r in load_rows(args.features,'val',names)+load_rows(args.negative_features,'val')}
    files=list(map(str,archive['files']))
    if len(set(files))!=len(files) or set(files)!=set(rows_by_file):raise ValueError('Validation denominator differs')
    rows=[rows_by_file[f] for f in files]
    expected=np.asarray([r['label'] if r['label'] in names else '__UNKNOWN__' for r in rows])
    if not np.array_equal(expected,archive['expected']):raise ValueError('Validation expected labels differ')
    watch={s['originalFile'] for item in json.loads((REPO/'models/recognition-videos.json').read_text(encoding='utf-8'))['items'] for s in item.get('sources',[])}
    if any({Path(p).name for p in r.get('componentFiles') or [r['file']]}&watch for r in rows):raise ValueError('Watch source in validation')
    version=base_blob.get('preprocessorVersion','legacy-v1')
    xs=[tensorize(r,version) for r in rows];positions=[i for i,x in enumerate(xs) if x is not None]
    base_p=np.full((len(rows),len(names)),np.nan,np.float32)
    base_p[positions]=predict(models,[xs[i] for i in positions],mirror=bool(base_blob.get('mirrorTta',len(models)>1)),anatomical=base_blob.get('mirrorVersion')=='anatomical-v2')
    old_path=REPO/profile['auxiliary']['checkpoint']
    if digest(old_path)!=profile['auxiliary']['checkpointSha256']:raise ValueError('Active auxiliary identity differs')
    old_model,old_labels,_=load_shape(old_path)
    xs=[shape_tensorize(r) for r in rows];positions=[i for i,x in enumerate(xs) if x is not None]
    old_p=np.full((len(rows),len(old_labels)),np.nan,np.float32)
    old_p[positions]=shape_predict(old_model,[xs[i] for i in positions])
    candidate_p=archive['probabilities']
    np.savez_compressed(args.out.with_suffix('.validation.npz'),files=np.asarray(files),expected=expected,labels=np.asarray(labels),base=base_p,old_auxiliary=old_p,new_auxiliary=candidate_p)
    modes={'full':names} if args.family=='beginner' else {'full':names,'core':CORE,'extended':CORE+EXTRA}
    policies={};selected={};candidates={}
    for mode,allowed in modes.items():
        before_p=combine(base_p,old_p,names,old_labels,profile['auxiliary']['weights'][mode])
        before=metrics(before_p,expected,labels,allowed,profile['policies'][mode])
        candidates[mode]=[];winner=None
        for weight in (0,.25,.5,.75,1):
            p=combine(base_p,candidate_p,names,labels,weight)
            policy=fit_budget(p,expected,labels,allowed,before)
            if not policy:continue
            after=metrics(p,expected,labels,allowed,policy)
            row={'weight':weight,'metrics':after,'policy':policy};candidates[mode].append(row)
            key=(after['correct'],-after['wrong'],-after['negativeFalse'])
            if eligible(before,after) and (winner is None or key>winner[0]):winner=(key,row)
        if winner:
            row=winner[1];policies[mode]=row['policy']
            selected[mode]={'weight':row['weight'],'before':before,'after':row['metrics'],'eligible':True,'improved':row['metrics']['correct']>before['correct']}
        else:
            policies[mode]=profile['policies'][mode]
            selected[mode]={'weight':None,'before':before,'after':None,'eligible':False,'improved':False}
        print(mode,json.dumps(selected[mode]),flush=True)
    result={'family':args.family,'checkpoint':args.base.name,'checkpointSha256':digest(args.base),
            'auxiliaryCheckpoint':str(args.auxiliary.resolve()),'auxiliarySha256':digest(args.auxiliary),
            'auxiliaryFeatureVersion':blob['featureVersion'],'auxiliaryValidationSha256':digest(args.auxiliary.with_suffix('.val.npz')),
            'baselineConfigurationSha256':digest(args.baseline),'baselineAuxiliarySha256':digest(old_path),
            'validationArchiveSha256':digest(args.out.with_suffix('.validation.npz')),'selectedAt':datetime.now(timezone.utc).isoformat(),
            'selectionSplit':'val','testUsedForSelection':False,'watchClipsUsedForSelection':False,
            'selected':selected,'policies':policies,'candidates':candidates,
            'deployable':selected['full']['improved'] and all(s['eligible'] for s in selected.values()),
            'scope':'Candidate only, not deployed. Active v3 and candidate evaluated on identical train/val-source-deduplicated validation attempts.'}
    args.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--family',choices=('beginner','capstone'),required=True)
    for key in ('base','baseline','auxiliary','features','negative-features','out'):parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--threads',type=int,default=2)
    select(parser.parse_args())
