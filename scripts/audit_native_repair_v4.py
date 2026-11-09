"""Freeze validation candidates, then audit the existing held-out recordings.

No weights/gates are revised from test results. Uses the same v3 denominators
and documents that these are reused held-out regression recordings, not new
physical-camera evidence. Does not install any candidate.
"""
from __future__ import annotations
import argparse,hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path
import torch
from asl_model_tools import REPO,digest,load_checkpoint,load_rows
from calibrate_motion_models import canonical
from evaluate_motion_repair import run_checkpoint,sources

EVAL=REPO.parent/'hs-eval'


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def audit(args):
    torch.set_num_threads(args.threads)
    root=args.root.resolve();baseline=json.loads((root/'baseline-v3.json').read_text(encoding='utf-8'))
    selections={family:json.loads((root/('selection-'+family+'.json')).read_text(encoding='utf-8')) for family in ('beginner','capstone')}
    frozen=root/'frozen-selection.json'
    freeze={'selectedAt':datetime.now(timezone.utc).isoformat(),'baselineSha256':digest(root/'baseline-v3.json'),
            'selectionSha256':{f:digest(root/('selection-'+f+'.json')) for f in selections},
            'auxiliarySha256':{f:selections[f]['auxiliarySha256'] for f in selections},
            'testUsedForSelection':False,'watchClipsUsedForSelection':False,
            'predeclaredDeploymentGate':'Same test attempts: more correct accepts, no extra known-word errors or unsupported accepts in any served mode. No retuning; no installation by this script.'}
    if frozen.exists():
        old=json.loads(frozen.read_text(encoding='utf-8'))
        if any(old[key]!=freeze[key] for key in ('baselineSha256','selectionSha256','auxiliarySha256')):raise ValueError('Frozen candidate changed')
    else:write(frozen,freeze)
    if any(digest(selections[f]['auxiliaryCheckpoint'])!=selections[f]['auxiliarySha256'] for f in selections):raise ValueError('Selected weights changed')
    watch={s['originalFile'] for item in json.loads((REPO/'models/recognition-videos.json').read_text(encoding='utf-8'))['items'] for s in item.get('sources',[])}
    paths={'beginner':EVAL/'motion-repair-20261107/features-beginner-repaired.jsonl','capstone':EVAL/'features-test-merged.jsonl'}
    bases={'beginner':REPO/'models/beginner-repaired-v2.pt','capstone':REPO/'third_party/microsoft_asl_citizen/capstone100-v4-ensemble.pt'}
    gates={}
    for family in selections:
        selection=selections[family];profile=baseline['models'][family]
        if not selection['deployable']:
            gates[family]={'eligible':False,'reason':'No validation-only all-mode improvement'};continue
        output=root/('heldout-'+family+'.json')
        if output.exists():
            gates[family]=json.loads(output.read_text(encoding='utf-8'))['deploymentGate'];continue
        _,labels,_=load_checkpoint(bases[family])
        if digest(bases[family])!=profile['checkpointSha256']:raise ValueError('Baseline checkpoint changed')
        all_known=load_rows(paths[family],'test',labels)
        known=[r for r in all_known if not sources(r)&watch]
        forms={canonical(n) for n in labels};other='capstone' if family=='beginner' else 'beginner'
        all_negative=[r for r in load_rows(paths[other],'test') if canonical(r['label']) not in forms and not r.get('syntheticGreeting')]
        negative=[r for r in all_negative if not sources(r)&watch]
        rows=known+negative
        if len({r['file'] for r in rows})!=len(rows):raise ValueError('Duplicate test attempts')
        if set(labels)-{r['label'] for r in known}:raise ValueError('Missing independent named test recordings')
        fitting=[]
        for split in ('train','val'):
            for kind in (family,family+'-negatives'):
                fitting+=load_rows(EVAL/'motion-repair-v4-20261107/fitting'/(kind+'.jsonl'),split)
        fit_sources=set().union(*(sources(r) for r in fitting));fit_signers={p for r in fitting for p in r.get('participants') or [r.get('participant')] if p}
        if any(sources(r)&fit_sources or fit_signers.intersection(r.get('participants') or [r.get('participant')]) for r in rows):raise ValueError('Test source/signer overlaps fitting')
        old_aux=REPO/profile['auxiliary']['checkpoint']
        old_fusion={'checkpointSha256':profile['checkpointSha256'],'auxiliaryCheckpoint':str(old_aux),'auxiliarySha256':profile['auxiliary']['checkpointSha256'],
                    'auxiliaryFeatureVersion':profile['auxiliary']['featureVersion'],'selected':{mode:{'weight':weight} for mode,weight in profile['auxiliary']['weights'].items()}}
        before=run_checkpoint(bases[family],rows,family,profile['policies'],old_fusion)
        after=run_checkpoint(bases[family],rows,family,selection['policies'],selection)
        checks={mode:{'before':{k:v for k,v in before['modes'][mode]['accepted'].items() if k!='perLabel'},
                      'after':{k:v for k,v in after['modes'][mode]['accepted'].items() if k!='perLabel'}} for mode in before['modes']}
        for mode,pair in checks.items():
            a,b=pair['before'],pair['after']
            pair['passed']=b['correct']>=a['correct'] and b['wrong']<=a['wrong'] and b['negativeFalse']<=a['negativeFalse']
        gate={'eligible':all(c['passed'] for c in checks.values()) and checks['full']['after']['correct']>checks['full']['before']['correct'],'modes':checks}
        gates[family]=gate
        result={'family':family,'split':'test','knownAttempts':len(known),'negativeAttempts':len(negative),
                'watchKnownExcluded':len(all_known)-len(known),'watchNegativeExcluded':len(all_negative)-len(negative),
                'testUsedForSelection':False,'watchClipsExcluded':True,'sourcesAndParticipantsDisjoint':True,
                'selectionSha256':digest(root/('selection-'+family+'.json')),'frozenSelectionSha256':digest(frozen),
                'featuresSha256':digest(paths[family]),'negativeFeaturesSha256':digest(paths[other]),
                'baseline':before,'selected':after,'deploymentGate':gate,'deployed':False,
                'scope':'Frozen candidate vs v3 on identical reused held-out recording regressions. No threshold/checkpoint tuning from test outputs. Not new independent-source or physical-camera accuracy.'}
        write(output,result)
        print(family,json.dumps(gate),flush=True)
    write(root/'heldout-gates.json',gates)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=REPO/'reports/motion-repair-v4-20261107')
    parser.add_argument('--threads',type=int,default=3)
    audit(parser.parse_args())
