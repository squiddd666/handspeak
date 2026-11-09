"""Score frozen predictions AFTER inference; never choose a route or threshold."""
import argparse,collections,hashlib,json
from pathlib import Path
from scripts.run_online_native_audit import verify
ROOT=Path(__file__).resolve().parents[1]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def metrics(rows,predictions,labels):
    if len(rows)!=len(predictions):raise ValueError('Missing outcomes')
    result=dict(positiveAttempts=0,matched=0,incorrect=0,noMatch=0,negativeAttempts=0,falseAccepts=0,correctRejections=0)
    for r,p in zip(rows,predictions):
        if r['label'] in labels:
            result['positiveAttempts']+=1
            result['matched' if p==r['label'] else 'noMatch' if p is None else 'incorrect']+=1
        else:
            result['negativeAttempts']+=1;result['falseAccepts' if p is not None else 'correctRejections']+=1
    return result

def main(args):
    folder=args.protocol.resolve().parent;protocol=json.loads(args.protocol.read_text(encoding='utf-8'));verify(protocol)
    clips=json.loads(Path(protocol['cohort']).read_text(encoding='utf-8'))['clips']
    native=[json.loads(line) for line in (folder/'native-predictions.jsonl').read_text(encoding='utf-8').splitlines() if line]
    checkpoint=json.loads((folder/'browser-ledger/checkpoint.json').read_text(encoding='utf-8'));browser=checkpoint['attempts']
    if [r['file'] for r in native]!=protocol['order'] or [r['id'] for r in browser]!=protocol['order']:
        raise ValueError('All 76 frozen outcomes are required, in the original order')
    labels={'candidate':protocol['candidateLabels'],**protocol['manualModes']}
    summary={};outcomes=[]
    for pipeline,records in [('native',native),('browser',browser)]:
        outputs={mode:[] for mode in labels}
        for clip,r in zip(clips,records):
            predicted={'candidate':r.get('candidate') if pipeline=='native' else r.get('experimentalBodyPrediction'),
                       **(r['manual'] if pipeline=='native' else r['manualPredictions'])}
            for mode,p in predicted.items():outputs[mode].append(p)
            outcomes.append(dict(pipeline=pipeline,file=clip['file'],expected=clip['label'],sourceSha256=clip['sha256'],
                                 status=r['status'],error=r.get('error'),predictions=predicted,
                                 contractPassed=r.get('contractPassed') if pipeline=='browser' else None,
                                 bodyFrames=r.get('bodyTrackedFrames') if pipeline=='native' else r.get('bodyFrames'),
                                 manualFrames=r.get('manualTrackedFrames'),candidateTracked=r.get('candidateTracked'),
                                 playbackTruncated=r.get('playbackTruncated') if pipeline=='browser' else False))
        measured={mode:metrics(clips,values,labels[mode]) for mode,values in outputs.items()}
        summary[pipeline]=dict(outcomes=len(records),failed=sum(r['status']!='complete' for r in records),metrics=measured,
                               perLabel={label:{mode:metrics([r for r in clips if r['label']==label],[p for r,p in zip(clips,values) if r['label']==label],labels[mode])
                                                for mode,values in outputs.items()} for label in sorted({r['label'] for r in clips})})
    summary['browser'].update(captureContractsPassed=sum(r['contractPassed'] for r in browser),
                              pairedFrames=sum(r['pairCount'] for r in browser),
                              truncatedPlaybacks=sum(r['playbackTruncated'] for r in browser),
                              realCameraCalls=checkpoint['realCameraCalls'],microphoneCalls=checkpoint['microphoneCalls'])
    summary.update(cohortRecordings=76,positiveCandidateRecordings=69,negativeCandidateRecordings=7,
                   candidateWordCoverage=19,missingCandidateWords=sorted(set(protocol['candidateLabels'])-{r['label'] for r in clips}),
                   knownSigners=8,freshNewSignerAudit=False,all198Tested=False,fullProductionAppRoutingVerified=False,
                   modelAndRuntimeUnchanged=True,trained=False,thresholdsChanged=False,candidatePromoted=False,
                   selectionAfterPredictions=False,liveCameraAccuracyVerified=False,
                   sourceEvidenceSha256={str(p):sha(p) for p in [args.protocol,folder/'native.jsonl',folder/'native-predictions.jsonl',folder/'browser-ledger/checkpoint.json',folder/'fixture.json',folder/'fixture.html',folder/'browser-version.json']})
    target=args.out.resolve();target.mkdir(exist_ok=False)
    (target/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    (target/'outcomes.json').write_text(json.dumps(outcomes,indent=2)+'\n',encoding='utf-8')
    errors=[r for r in outcomes if any((r['expected'] in labels[mode] and p!=r['expected']) or (r['expected'] not in labels[mode] and p is not None) for mode,p in r['predictions'].items())]
    (target/'remaining-errors.json').write_text(json.dumps(errors,indent=2)+'\n',encoding='utf-8')
    table=lambda p:'\n'.join(f"| {mode} | {r['positiveAttempts']} | {r['matched']} | {r['incorrect']} | {r['noMatch']} | {r['negativeAttempts']} | {r['falseAccepts']} |" for mode,r in summary[p]['metrics'].items())
    header='| Classifier | Positive clips | Matched | Incorrect | No match | Outside vocabulary | False accepts |\n|---|---:|---:|---:|---:|---:|---:|'
    text=f'''# One-pass online recognition audit — 2026-11-07

**Recognition is not fully repaired. No model or threshold was changed; the rejected candidate remains offline.**

All **76** identity-screened recordings were processed once per pipeline. These are previously unused recordings from **8 known PopSign signers**, not a new-signer benchmark. Publisher labels/variants are retained; identity overlap with ASL Citizen remains unverified. The original publisher TLS limitation remains in the intake report.

The body candidate supports 24 words; this cohort covers **19**, with **69** positive clips and **7** outside-vocabulary clips. Missing: {', '.join(summary['missingCandidateWords'])}. This is not a retest of all 198 words or a comparison with earlier 198-word totals.

## Native full-clip audit

Uniform 32 unique original source-frame indices, maximum image side 640. Actual Holistic body outputs and separate Tasks VIDEO hand outputs are retained. Both graphs reset between clips. Failures and missing tracking remain in the denominator.

{header}
{table('native')}

Native runtime/extraction failures: **{summary['native']['failed']}/76**.

## Isolated browser capture audit

Original createLandmarkCapture sampler, countdown exclusion, snapshots, queue, and result filtering. Independent detector inputs are copies of one immutable image; the body output is forwarded without manual-hand substitution. Source playback is unmodified at speed 1 in a 960×720 letterboxed virtual canvas. Original 4/6/8-second duration policy is frozen. Detectors initialize without images before the first take; every take resets both graphs.

{header}
{table('browser')}

**{summary['browser']['captureContractsPassed']}/76** capture contracts passed; **{summary['browser']['pairedFrames']}** paired frames. Failed/canceled outcomes: **{summary['browser']['failed']}**. **{summary['browser']['truncatedPlaybacks']}** sources exceeded the unchanged eight-second cap; they were flagged, not sped up, retried or excluded. Physical camera/microphone calls: **0/0**. Fresh headless browser, no user browser attached; the audit server/browser were stopped after completion.

## Interpretation

Each manual mode runs independently on every clip; its positive/negative denominator is its own frozen vocabulary. Default, expanded, daily, and pack outputs are **not combined into an oracle winner**. Expected labels are joined only after prediction. Native and browser sampling/geometry differ; capture contracts do not prove native/browser landmark equality or full production-app routing.

Every error, rejection, and unsupported acceptance is retained in `outcomes.json` and `remaining-errors.json`. Raw landmarks stay in the external audit folder, not this served report. All frozen production weights/runtime/gates remain unchanged. No training, threshold selection, best-of retries or candidate promotion occurred. The candidate's previous NO regression is not erased by this new cohort.

## Next repair boundary

Keep this cohort audit-only. Use its failures to identify tracking/runtime defects, not to choose gates or fit references. Any retraining requires separate development recordings and validation, followed by another untouched audit. Full-198 production-browser regression and genuinely new-signer validation remain outstanding.

External evidence folder: `{folder}`. Frozen protocol and source/cohort/model hashes precede predictions. Local screenshot: `{folder/'browser-proof.png'}`.
'''
    (target/'README.md').write_text(text,encoding='utf-8');print(json.dumps({p:summary[p]['metrics'] for p in ['native','browser']},indent=2));print('Report:',target/'README.md')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--protocol',type=Path,required=True);p.add_argument('--out',type=Path,required=True);main(p.parse_args())
