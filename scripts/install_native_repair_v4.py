"""Install only independently audited v4 candidates; preserve v3 rollback.

Failed candidates remain reports only. Published accuracy evidence follows the
actually installed family, including when its older v3 model is retained.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,shutil
from datetime import datetime,timezone
from pathlib import Path
from asl_model_tools import REPO,digest


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def install(root):
    if (root/'installation.json').exists():raise FileExistsError('Release already installed')
    baseline=read(root/'baseline-v3.json');frozen=read(root/'frozen-selection.json');gates=read(root/'heldout-gates.json')
    if digest(REPO/'models/motion-calibration.json')!=frozen['baselineSha256']:raise ValueError('Active baseline changed')
    config=copy.deepcopy(baseline);evidence=root/'installed-evidence';changed=[]
    for family in ('beginner','capstone'):
        selection=read(root/('selection-'+family+'.json'))
        if digest(root/('selection-'+family+'.json'))!=frozen['selectionSha256'][family]:raise ValueError('Selection changed after test freeze')
        profile=config['models'][family]
        candidate_report=root/('heldout-'+family+'.json')
        report=read(candidate_report) if candidate_report.exists() else read(REPO/'reports/motion-repair-v3-20261107'/('heldout-'+family+'.json'))
        promote=bool(selection['deployable'] and gates[family]['eligible'])
        if promote:
            if report['selectionSha256']!=frozen['selectionSha256'][family] or not report['deploymentGate']['eligible']:raise ValueError('Audit selection differs')
            candidate=Path(selection['auxiliaryCheckpoint']);target=REPO/'models'/(family+'-handshape-v4.pt')
            if digest(candidate)!=selection['auxiliarySha256'] or target.exists():raise ValueError('Candidate identity/target differs')
            shutil.copyfile(candidate,target)
            profile['auxiliary']={'checkpoint':target.relative_to(REPO).as_posix(),'checkpointSha256':selection['auxiliarySha256'],
                                  'featureVersion':selection['auxiliaryFeatureVersion'],'weights':{mode:s['weight'] for mode,s in selection['selected'].items()}}
            profile['policies']=selection['policies'];chosen=report['selected'];changed.append(family)
        else:
            chosen=report.get('baseline',report['selected']) if candidate_report.exists() else report['selected']
        name=family+'-handshape-v4.json';profile['calibrationReport']=name
        calibration={k:v for k,v in profile.items() if k!='auxiliary'}
        calibration.update(auxiliarySha256=profile['auxiliary']['checkpointSha256'],auxiliaryFeatureVersion=profile['auxiliary']['featureVersion'],
                           fusionWeights=profile['auxiliary']['weights'],testUsedForCalibration=False,watchClipsUsedForCalibration=False,
                           selectionSplit='val',scope='Validation-frozen gates; reused held-out regression audit, no test/Watch fitting.')
        path=evidence/'calibration'/name;write(path,calibration)
        published=copy.deepcopy(report);published['selected']=chosen;published['calibrationSha256']=digest(path)
        published['deployed']=True;published['retainedV3Model']=not promote
        write(evidence/('heldout-'+family+'.json'),published)
    backup=root/'pre-v4';backup.mkdir(exist_ok=True)
    for name in ('motion-calibration.json','motion-word-accuracy.json'):
        target=backup/name
        if target.exists():raise FileExistsError(target)
        shutil.copyfile(REPO/'models'/name,target)
    config['calibrationId']='motion-repair-v4-20261107-val-'+hashlib.sha256(json.dumps(config['models'],sort_keys=True).encode()).hexdigest()[:12]
    config['selectedAt']=datetime.now(timezone.utc).isoformat()
    config['selectionScope']='Targeted dense re-extraction/fine-tuning, validation-only fusion/gates. Failed held-out candidates retain v3; no test/Watch fitting.'
    write(root/'release-draft.json',config);write(REPO/'models/motion-calibration.json',config)
    write(root/'installation.json',{'installedAt':config['selectedAt'],'calibrationId':config['calibrationId'],'upgradedFamilies':changed,
                                   'retainedFamilies':[f for f in ('beginner','capstone') if f not in changed],'manualCandidateInstalled':False,
                                   'configurationSha256':digest(REPO/'models/motion-calibration.json'),'rollback':str(backup)})
    print('Installed',config['calibrationId'],'upgraded',changed,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=REPO/'reports/motion-repair-v4-20261107')
    install(parser.parse_args().root.resolve())
