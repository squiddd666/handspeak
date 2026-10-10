"""Train one supported output against all other signs/actions; no automatic release."""
import argparse
import json
from pathlib import Path
import shutil
import train_split_ordinary_rejection as trainer
import freeze_split_candidate as freeze
from calibrate_word_thresholds import sha,write
REPO=Path(__file__).resolve().parents[2]
BASE=Path('/opt/handspeak-training')
WORDS=['CALL','FIND','FISH','SEE','SICK','PAIN','NIGHT','MORNING']

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--word',choices=WORDS,required=True);args=parser.parse_args()
    root=BASE/'single-word-20261010'/args.word.lower();report=REPO/'reports/vocabulary-expansion/single-word'/args.word.lower()
    if (root/'plan.json').exists():raise ValueError('Experiment already exists; never overwrite frozen training')
    parent=BASE/'vocabulary-expansion-framing-calibrated';p=json.loads((parent/'protocol.json').read_text())
    if sha(parent/'frozen.pt')!=p['checkpointSha256']:raise ValueError('Parent checkpoint changed')
    source=BASE/'vocabulary-expansion-windowed-ordinary-source'
    sp=json.loads((source/'protocol.json').read_text())
    files=[Path(__file__),Path(trainer.__file__),Path(freeze.__file__),REPO/'training/catalog/remap_rejection_head.py',REPO/'training/catalog/body_tip_features.py',REPO/'training/catalog/train_motion_residual.py',REPO/'training/catalog/train_expansion_batch.py',REPO/'training/catalog/camera_framing.py']
    plan=dict(word=args.word,sourceSha256=sp['sourceSha256'],parentCheckpointSha256=p['checkpointSha256'],
              recipe='One supported label; all other ASL signs and six ordinary actions remain competing rejection classes. Same fixed 20-epoch recipe, seed109, 5/10/20 development checkpoints and acceptance gates.',
              testPolicy='No test data used in training or checkpoint selection. Fresh release checks required.',implementations={str(f):sha(f) for f in files},deployed=False)
    write(root/'plan.json',plan);write(report/'plan.json',plan)
    for f in files:
        dst=root/'source-snapshot'/f.relative_to(REPO);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dst)
    p['labels']=[args.word];p['thresholdByLabel']={args.word:p['thresholdByLabel'][args.word]}
    write(root/'parent/protocol.json',p);shutil.copyfile(parent/'frozen.pt',root/'parent/frozen.pt')
    trainer.BASE=root/'parent';trainer.SOURCE=source;trainer.ROOT=root/'training';trainer.REPORT=report
    trainer.main()
    if any(sha(f)!=h for f,h in plan['implementations'].items()):raise ValueError('Training implementation changed')
    result=json.loads((root/'training/validation.json').read_text())
    if result['passesValidation']:
        freeze.SOURCE=root/'training';freeze.ROOT=root/'frozen';freeze.REPORT=report/'frozen';freeze.main()
    write(report/'completion.json',dict(word=args.word,trainingComplete=True,passesDevelopmentScreen=result['passesValidation'],requiresFreshTests=True,deployed=False))
if __name__=='__main__':main()
