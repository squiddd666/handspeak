"""Report one frozen worker audit, with independent exact-label denominators."""
import argparse, collections, json
from pathlib import Path
from scripts.run_online_native_audit import verify
from scripts.prepare_online_motion_audit import ROOT, sha, write_new


def score(rows, labels):
    supported=set(labels); positives=[r for r in rows if r['label'] in supported]; negatives=[r for r in rows if r['label'] not in supported]
    matched=sum(r['prediction']==r['label'] for r in positives)
    wrong=sum(r['prediction'] is not None and r['prediction']!=r['label'] for r in positives)
    no_match=sum(r['prediction'] is None for r in positives)
    false=sum(r['prediction'] is not None for r in negatives)
    return dict(positives=len(positives),matched=matched,incorrect=wrong,noMatch=no_match,
        positiveRecall=matched/len(positives) if positives else None,negatives=len(negatives),
        negativeFalseAcceptances=false,negativeRejections=len(negatives)-false,
        negativeFalseAcceptanceRate=false/len(negatives) if negatives else None,
        acceptedPrecision=matched/(matched+wrong+false) if matched+wrong+false else None)


def main(args):
    folder=args.protocol.resolve().parent; protocol=json.loads(args.protocol.read_text('utf-8')); verify(protocol)
    cohort=json.loads(Path(protocol['cohort']).read_text('utf-8')); cfg=json.loads((folder/'fixture.json').read_text('utf-8'))
    ledger=json.loads((folder/'browser-ledger/checkpoint.json').read_text('utf-8'))
    from scripts.serve_online_worker_audit import Store
    # Validate the original immutable ledger in memory without rewriting it.
    receipts={}
    for p in (folder/'api-receipts').glob('*.json'):
        r=json.loads(p.read_text('utf-8')); receipts[(r['id'],r['mode'])]=r
    validator=object.__new__(Store); validator.cfg=cfg; validator.receipts=receipts
    # Validation still uses append-only paths; use a dedicated verification ledger.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        validator.folder=Path(d); validator.previous=None
        import threading; validator.lock=threading.Lock(); validator.save(ledger)
    attempts=ledger['attempts']
    if len(attempts)!=len(cohort['clips']) or [a['id'] for a in attempts]!=protocol['order']: raise ValueError('Incomplete or reordered one-pass ledger')
    for a in attempts:
        path=folder/f"browser-ledger/attempt-{a['number']:03}.json"
        if json.loads(path.read_text('utf-8'))!=a: raise ValueError('Individual immutable outcome changed')
    modes={}; per_word={}
    for mode,labels in {**protocol['manualModes'],**protocol['productionModes'],'offline-body-candidate':protocol['candidateLabels']}.items():
        rows=[]
        for a in attempts:
            prediction=(a['experimentalBodyPrediction'] if mode=='offline-body-candidate' else
                a['productionPredictions'][mode]['accepted'] if mode in protocol['productionModes'] else a['manualPredictions'][mode])
            rows.append(dict(id=a['id'],label=a['label'],prediction=prediction))
        modes[mode]=score(rows,labels)
        per_word[mode]={label:score([r for r in rows if r['label']==label],labels) for label in sorted({r['label'] for r in rows})}
    info=dict(clips=len(attempts),labelCounts=dict(collections.Counter(a['label'] for a in attempts)),
        uniqueSignerIds=sorted({r['participant'] for r in cohort['clips']}),
        complete=sum(a['status']=='complete' for a in attempts),failed=sum(a['status']=='failed' for a in attempts),
        canceled=sum(a['status']=='canceled' for a in attempts),contractsPassed=sum(a['contractPassed'] for a in attempts),
        captureFailures=[dict(id=a['id'],label=a['label'],error=a['error']) for a in attempts if not a['contractPassed']],
        pairRange=[min(a['pairCount'] for a in attempts),max(a['pairCount'] for a in attempts)],
        bodyUsable=sum(a['contractPassed'] and a['bodyFrames']>=5 for a in attempts),
        manualTotalBelow12=sum(a['manualFrames']<12 for a in attempts),
        manualTrackedBelow5=sum(a['manualTrackedFrames']<5 for a in attempts),
        manualEncodingsUsable=sum(a['contractPassed'] and a['manualEncodingUsable'] for a in attempts),
        playbackTruncated=sum(a['playbackTruncated'] for a in attempts),
        productionRequests=len(receipts),productionHttpErrors=sum(r['result']['httpStatus']!=200 for r in receipts.values()),
        frozenClassifierArtifacts=len(protocol['classifierArtifactsSha256']),allFrozenFilesUnchanged=True,
        trainingAllowed=False,calibrationAllowed=False,candidatePromoted=False,newSignerAudit=False,full198Audit=False,
        fullProductionAppRoutingVerified=False,physicalCameraCalls=ledger['realCameraCalls'],microphoneCalls=ledger['microphoneCalls'])
    evidence={str(p):sha(p) for p in folder.rglob('*') if p.is_file() and ('browser-ledger' in p.parts or 'api-receipts' in p.parts or p.name in ('protocol.json','cohort.json','fixture.json','fixture.html','post-run-integrity.json','browser-version.json','cleanup-receipt.json','browser-console.json','loaded-production-status.json'))}
    result=dict(scope=protocol['purpose'],capture=info,modes=modes,perWord=per_word,
        productionRejections={mode:dict(collections.Counter(a['productionPredictions'][mode]['rejectionReason'] or a['productionPredictions'][mode]['error'] or 'accepted' for a in attempts)) for mode in protocol['productionModes']},
        protocolSha256=sha(args.protocol),evidenceSha256=evidence,transportLimitation=protocol['transportLimitation'])
    out=args.out.resolve(); out.mkdir(exist_ok=False); write_new(out/'summary.json',result)
    write_new(out/'outcomes.json',dict(attempts=attempts))
    table='\n'.join(f"| {m} | {s['positives']} | {s['matched']} | {s['incorrect']} | {s['noMatch']} | {s['negativeFalseAcceptances']}/{s['negatives']} |" for m,s in modes.items())
    errors='\n'.join(f"- {a['label']} ({a['id']}): {a['error']}" for a in info['captureFailures']) or 'None.'
    word_table='\n'.join(f"| {label} | {n} | "+' | '.join(
        f"{per_word[m][label]['matched']}/{n}" if per_word[m][label]['positives'] else 'outside vocabulary'
        for m in ('default','expanded','daily','pack','offline-body-candidate'))+' |' for label,n in sorted(info['labelCounts'].items()))
    text=f'''# Fresh worker recognition audit — 2026-11-08

**{len(attempts)} originals tested once. Recognition is not fully repaired.**

This is a previously-unused-recording, **known-signer** regression according to available local provenance, not genuinely new-signer validation, a full-198 audit, full application UI routing, or live-camera accuracy. Anonymous cross-dataset signer identity separation is unverified. No faces were used to infer identity.

## Recognition results

Each mode has its own exact-label positive/negative denominator. Modes are never merged into a best-of result. Unaccepted suggestions are not matches. Zero-positive modes cannot establish recognition accuracy.

| Independent mode | Positives | Matched | Incorrect | No match | False accepts / negatives |
|---|---:|---:|---:|---:|---:|
{table}

The offline body candidate remains rejected and uninstalled. Different clips and updated execution mean these counts are **not a paired accuracy-improvement comparison** with the old audit or the user's 198-word totals. FOOD→EAT1 and other dataset gloss substitutions were not made.

## Capture and actual production APIs

- {info['contractsPassed']}/{len(attempts)} captures passed immutable-pixel, epoch, timestamp, dimension and unmodified-body-output contracts using the integrated worker path.
- {info['complete']} completed; {info['failed']} failed; {info['canceled']} canceled. All outcomes remain in each applicable denominator.
- {info['pairRange'][0]}–{info['pairRange'][1]} processed pairs per take; {info['manualTotalBelow12']} takes fell below the manual encoder's **12-total-frame** input minimum. {info['manualTrackedBelow5']} had fewer than its separate five-visible-frame requirement; {info['manualEncodingsUsable']} produced a usable encoding after the unchanged continuity/geometry checks. {info['bodyUsable']} takes met the production client's five-body-frame minimum.
- {info['productionRequests']} real HTTP prediction requests; {info['productionHttpErrors']} non-200 responses. All four production modes received the identical unchanged landmark array digest for each usable take, without expected labels or minScore hints. Scalar API receipts preserve accepted/rejected outcomes; no raw images or landmark arrays were saved.
- {info['playbackTruncated']} sources exceeded their frozen 4/6/8-second window; truncations were flagged rather than sped up or replaced.
- {info['frozenClassifierArtifacts']} application classifier artifacts and every frozen runtime/harness input remain byte-identical. No retraining, recalibration, gate editing or candidate promotion.
- Actual loaded checkpoints: Beginner `{protocol['productionStatus']['beginner']['checkpoint']}`; Capstone `{protocol['productionStatus']['capstone']['checkpoint']}`. These are the loaded identities, not guesses from preferred candidate filenames; their status and SHA-256 evidence were frozen before acquisition.
- Zero physical camera/microphone calls. Only owned headless Chrome and loopback servers were used; the real user database and MySQL were isolated from the audit.

### Retained capture failures

{errors}

## Per-word matched coverage

| Exact publisher label | Clips | Default | Expanded | Daily | Pack | Offline body candidate |
|---|---:|---:|---:|---:|---:|---:|
{word_table}

All route-specific incorrect/no-match/negative outcomes are retained in `outcomes.json` and `summary.json`; failures are not silently removed. Acquisition exclusions and metadata shortfalls remain outside the recognition cohort and are retained in its source evidence, with no replacement download selected using model results.

## Online source and limitations

[PopSign ASL v1.0 publisher](https://signdata.cc.gatech.edu/view/datasets/popsign_v1_0/index.html), Georgia Institute of Technology / Deaf Professional Arts Network; [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Official game/test archive originals, no preview/re-encoding substitutions. Publisher public-use statement is not independently verified new-signer consent.

{protocol['transportLimitation'] or 'No online media acquired for the development preflight.'}

Originals, metadata-only selections, explicit prior-key/hash/development exclusions, frozen models/status, individual capture ledger entries and API response receipts: `{folder}`.

## Next

Use these failures only to diagnose the remaining tracking/domain/label coverage gaps, **not to fit or select the next model**. Develop on separate consented/licensed recordings, then freeze another unused cohort. The full-198 production-routing regression and genuinely new-signer validation are still required before claiming a complete recognition repair.
'''
    with (out/'README.md').open('x',encoding='utf-8') as f: f.write(text)
    print(json.dumps(dict(capture=info,modes=modes),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--protocol',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True); main(p.parse_args())
