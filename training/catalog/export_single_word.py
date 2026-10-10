"""Export a one-word browser bundle to private staging, never directly to production."""
import argparse
import json
from pathlib import Path
import shutil
import torch
from calibrate_word_thresholds import sha,write
REPO=Path(__file__).resolve().parents[2]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--word',required=True);args=parser.parse_args()
    if args.word not in ['CALL','FIND','FISH','SEE','SICK','PAIN','NIGHT','MORNING']:raise ValueError('Unsupported word')
    root=Path('/opt/handspeak-training/single-word-20261010')/args.word.lower()/'frozen';p=json.loads((root/'protocol.json').read_text());screen=json.loads((root/'validation.json').read_text())
    if not screen['passesDevelopmentScreen'] or p['labels']!=[args.word] or sha(root/'frozen.pt')!=p['checkpointSha256']:raise ValueError('Candidate invalid')
    saved=torch.load(root/'frozen.pt',weights_only=True)
    if saved['outputLabels']!=p['outputLabels']:raise ValueError('Output order changed')
    model={k:p[k] for k in ['labels','outputLabels','threshold','margin','thresholdByLabel','featureMode','checkpointSha256']};model.update(version=1,encoding='hands-only-body-tips-residual-v1',featureEncoding='body-tips-v1',weights=[{k:v.tolist() for k,v in state.items()} for state in saved['states']])
    stage=Path('/opt/handspeak-staging/single-word-20261010')/args.word.lower();preview=stage/'motion-preview';preview.mkdir(parents=True,exist_ok=True)
    for name in ['index.html','style.css','app.js','boot.js','recognizer-worker.js','classifier.js','runtime.js','temporal-features.js','temporal-window.js','capture.js','motion-model.js','gesture-model.js']:shutil.copyfile(REPO/'motion-preview'/name,preview/name)
    serialized=json.dumps(model,separators=(',',':'))+'\n';(preview/'model.json').write_text(serialized)
    write(preview/'integrity.json',dict(checkpointSha256=p['checkpointSha256'],modelSha256=sha(preview/'model.json')))
    models=stage/'models/motion-categories';models.mkdir(parents=True,exist_ok=True);(models/f'single-{args.word.lower()}.json').write_text(serialized)
    report=REPO/'reports/vocabulary-expansion/single-word'/args.word.lower();write(report/'staging.json',dict(checkpointSha256=p['checkpointSha256'],modelSha256=sha(preview/'model.json'),path=str(stage),deployed=False))
    print('Private staging bundle:',stage,flush=True)
if __name__=='__main__':main()
