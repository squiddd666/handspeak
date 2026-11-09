"""Read-only failure attribution; exact and predeclared-alias scores stay distinct."""
import argparse,collections,json
from pathlib import Path
from scripts.run_online_native_audit import ROOT,sha,verify

def acceptable_labels(reference,family):
    # Explicit frozen glossary mapping only, never a suffix/punctuation fuzzy
    # match. A component such as MORNING is NOT the phrase GOOD MORNING.
    labels={reference['label']}
    if family=='capstone':labels.update(reference.get('modelGlosses',[]))
    return labels

def classify(take,reference):
    predicted=take.get('predicted');accepted=predicted in acceptable_labels(reference,take['family'])
    literal=predicted==take['label'];response=take.get('response') or {};camera=take.get('camera') or {}
    capture=camera.get('lastCapture') or {};status=(take.get('status') or '').lower()
    if accepted:return dict(correct=True,literalCorrect=literal,category='matched' if literal else 'predeclared-dataset-label-alias')
    if predicted:return dict(correct=False,literalCorrect=False,category='accepted-wrong-word')
    if not take.get('completeSourcePlayed'):category='source-playback-incomplete'
    elif 'timed out' in status or 'timeout' in take.get('endReason','').lower():category='capture-or-processing-timeout'
    elif response.get('httpStatus') not in (None,200):category='api-error'
    elif response.get('rejectionReason'):category='model-rejection:'+response['rejectionReason']
    elif capture and capture.get('frames',0)<5:category='insufficient-body-tracking'
    elif 'not enough' in status or 'not tracked' in status:category='insufficient-hand-capture-or-encoding'
    else:category='rejected-or-unattributed-no-match'
    return dict(correct=False,literalCorrect=False,category=category)

def main(args):
    folder=args.folder.resolve();p=json.loads((folder/'protocol.json').read_text('utf-8'));verify(p)
    if not (folder/'exact-label-summary.json').exists() or not (folder/'cleanup-receipt.json').exists():raise ValueError('Live/incomplete run; no final report')
    cleanup=json.loads((folder/'cleanup-receipt.json').read_text('utf-8'))
    if any(v!='no response' for v in cleanup.values()):raise ValueError('Owned processes not cleaned up')
    ledger=json.loads((folder/'browser-ledger/checkpoint.json').read_text('utf-8'));rows=ledger['attempts']
    if len(rows)!=198 or [r['id'] for r in rows]!=p['order']:raise ValueError('Wrong full-198 order/coverage')
    manifest_path=ROOT/'models/recognition-videos.json';manifest=json.loads(manifest_path.read_text('utf-8'))
    if p['frozenFilesSha256'].get(str(manifest_path))!=sha(manifest_path):raise ValueError('Unfrozen reference glossary')
    references={r['id']:r for r in manifest['items']};results=[];receipt_count=0
    for take in rows:
        outcome=classify(take,references[take['id']]);endpoint=(take.get('request') or {}).get('endpoint')
        receipt_path=folder/'api-receipts'/(take['id']+'-'+endpoint.rsplit('/',1)[-1]+'.json') if endpoint else None
        if receipt_path and receipt_path.exists():
            receipt=json.loads(receipt_path.read_text('utf-8'));receipt_count+=1
            if receipt['referenceId']!=take['id'] or receipt['endpoint']!=endpoint:raise ValueError('Receipt identity mismatch')
            response=take.get('response')
            if response and (receipt['httpStatus']!=response['httpStatus'] or receipt['accepted']!=take['predicted']):raise ValueError('Browser response differs from production receipt')
            if take['family'] in ('beginner','capstone'):
                status=p['productionStatus'][take['family']]
                if receipt['checkpointSha256'] and receipt['checkpointSha256']!=status['checkpointSha256']:raise ValueError('Loaded checkpoint changed')
        elif endpoint and take.get('response'):raise ValueError('Actual API response has no durable receipt')
        results.append(dict(id=take['id'],label=take['label'],predicted=take['predicted'],family=take['family'],
            completeSourcePlayed=take.get('completeSourcePlayed',False),receipt=str(receipt_path) if receipt_path and receipt_path.exists() else None,
            status=take.get('status'),**outcome))
    total=dict(matched=sum(r['correct'] for r in results),incorrect=sum(bool(r['predicted']) and not r['correct'] for r in results),noMatch=sum(not r['predicted'] for r in results))
    exact=json.loads((folder/'exact-label-summary.json').read_text('utf-8'))
    report=dict(references=198,predeclaredAliasAware=total,literalExact=exact,legacyNormalizedDisplay=dict(matched=sum(r.get('correct',False) for r in rows)),
        failureAttribution=dict(collections.Counter(r['category'] for r in results if not r['correct'])),
        explicitAliases=[r for r in results if r['correct'] and not r['literalCorrect']],productionApiReceipts=receipt_count,
        familyResults={family:dict(attempts=sum(r['family']==family for r in results),matched=sum(r['family']==family and r['correct'] for r in results),
            incorrect=sum(r['family']==family and bool(r['predicted']) and not r['correct'] for r in results),noMatch=sum(r['family']==family and not r['predicted'] for r in results)) for family in sorted({r['family'] for r in results})},
        outcomes=results,inputsSha256={str(folder/n):sha(folder/n) for n in ('protocol.json','browser-ledger/checkpoint.json','exact-label-summary.json','cleanup-receipt.json')},
        reportScriptSha256=sha(Path(__file__)),independentAccuracy=False,newSignerAccuracy=False,fullyFixed=False,
        scope='All 198 old Watch references through actual app controls. Explicit glossary aliases are distinguished from wrong signs, not counted as repairs. No training or calibration from these outcomes.')
    out=args.out.resolve();out.mkdir(exist_ok=False,parents=True)
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    md=['# Full-198 actual-app reference regression','', '**Recognition is not fully fixed.** This is a regression of previously used Watch references, not independent/new-signer accuracy.','',
        f"Explicit-glossary score: **{total['matched']} matched / {total['incorrect']} wrong / {total['noMatch']} no match**.",
        f"Literal strings: {exact['matched']} equal / {exact['incorrect']} unequal accepted labels / {exact['noMatch']} no match. Legitimate predeclared dataset aliases are shown separately, not advertised as recognition improvements.",'',
        f"Verified {receipt_count} production API receipts and owned-process cleanup. All frozen run inputs remain unchanged.",'','## Remaining failures','', '| Word | Prediction | Attribution |','|---|---|---|']
    md += [f"| {r['label']} | {r['predicted'] or 'no match'} | {r['category']} |" for r in results if not r['correct']]
    (out/'README.md').write_text('\n'.join(md)+'\n','utf-8');print(json.dumps(dict(**total,apiReceipts=receipt_count,fullyFixed=False)),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--folder',type=Path,required=True);p.add_argument('--out',type=Path,required=True);main(p.parse_args())
