"""Preserve dual-stream diagnostics without promoting them to accuracy claims."""
import csv,hashlib,json,re,shutil
from pathlib import Path
from scripts.report_motion_repair_v6 import verify_retained_runtime
from scripts.summarize_motion_virtual_camera import assert_scalar_telemetry
ROOT=Path(__file__).resolve().parents[1];EVAL=ROOT.parent/'hs-eval'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    out=ROOT/'reports/motion-repair-v7-20261107'
    source=EVAL/'motion-dual-capture-v7-20261107/checkpoint.json'
    report=json.loads(source.read_text(encoding='utf-8'));assert_scalar_telemetry(report)
    fixture=ROOT/'motion-dual-capture-v7-20261107.html'
    cfg=json.loads(re.search(r'window\.DUAL_CAPTURE_FIXTURE = (.*);</script>',fixture.read_text(encoding='utf-8')).group(1))
    if cfg['fixtureSha256']!=report['fixtureSha256'] or report['realCameraCalls'] or report['microphoneCalls']:raise ValueError('Expected frozen virtual-only fixture')
    for name,digest in cfg['filesSha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Diagnostic runtime changed: '+name)
    baseline=json.loads((ROOT/'reports/motion-repair-v6-20261107/baseline-pilot-28.json').read_text(encoding='utf-8'))
    retained=verify_retained_runtime(baseline)
    attempts=report['attempts']
    if len(attempts)!=10 or [a['number'] for a in attempts]!=list(range(1,11)):raise ValueError('Every diagnostic outcome must be retained')
    if any(not a.get('finishedAt') or a['rate']!=1 for a in attempts):raise ValueError('Unfinished or altered-speed diagnostic')
    completed=[a for a in attempts if a['status']=='complete'];canceled=[a for a in attempts if a['status']=='canceled']
    if len(completed)!=9 or len(canceled)!=1:raise ValueError('Expected initial eight, cancellation, and restart outcomes')
    if canceled[0]['id']!='no' or attempts[-1]['id']!='hello':raise ValueError('Cancellation/restart evidence differs')
    for a in completed:
        if not a['contractPassed'] or not all(a[k] for k in ('bodyOutputPreserved','sameEpoch','monotonicTimestamps','sameDimensions','pixelEquality')) or a['pairCount']!=a['processedFrames']:
            raise ValueError('Stream contract failure')
    f=EVAL/'v7-frontend-tests.log';p=EVAL/'v7-recognition-tests.log'
    front=f.read_text(encoding='utf-8-sig');python=p.read_text(encoding='utf-8-sig')
    if not re.search(r'fail 0\b',front) or not python.rstrip().endswith('OK'):raise ValueError('Targeted regression tests failed')
    summary=dict(outcomes=len(attempts),uniqueReferences=len({a['id'] for a in attempts}),
                 completedCaptures=len(completed),captureContractsPassed=sum(a['contractPassed'] for a in completed),
                 canceledOutcomesPreserved=len(canceled),restartAfterCancellationCompleted=True,
                 pairedRecordingFrames=sum(a['pairCount'] for a in completed),productionRuntimeRetained=True,
                 retainedRuntimeSha256=retained,sourceSha256=sha(source),fixtureSha256=sha(fixture),
                 modelChangesInstalled=False,candidatePromoted=False,processingConsentChanged=False,
                 nativeBrowserLandmarkEqualityVerified=False,productionAppRoutingVerified=False,
                 liveCameraAccuracyVerified=False,all198Retested=False,freshNewSignerAuditRun=False,
                 frontend=dict(passed=int(re.search(r'pass (\d+)',front).group(1)),skipped=int(re.search(r'skipped (\d+)',front).group(1)),failed=0),
                 targetedPython=dict(passed=int(re.search(r'Ran (\d+) tests',python).group(1)),failed=0),
                 fullPythonDiscoveryPassed=False,testLogSha256={str(f):sha(f),str(p):sha(p)},
                 scope='Capture-contract verification only: original recording sampler with an experimental immutable dual-reader coordinator. '
                       'Nine completed captures include a separate HELLO restart, not best-of accuracy. One canceled NO take is retained. '
                       'Diagnostic warm-up is frozen for both readers; native whole-clip sampling and full production routing are not verified. '
                       'Candidate recognition failures remain; the known NO regression is not repaired. Fresh audit awaits provider recordings.')
    out.mkdir(parents=True,exist_ok=True);shutil.copy2(source,out/'dual-capture-outcomes.json')
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    rows=[dict(number=a['number'],label=a['label'],status=a['status'],pairedFrames=a['pairCount'],bodyFrames=a['bodyFrames'],
               manualTrackedFrames=a['manualTrackedFrames'],contractPassed=a['contractPassed'],
               bodyCandidate=a.get('experimentalBodyPrediction') or 'NO MATCH',manual=a.get('manualPrediction') or 'NO MATCH') for a in attempts]
    with (out/'word-results.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    lines=['# Separate body/hand capture verification — 2026-11-07','',
           '**Recognition is not fully repaired. No candidate was installed.**','',
           '## Verified capture contracts','',
           '* Original body recording sampler, queue, countdown exclusion, API filtering, and cancellation lifecycle are used.',
           '* Holistic body/recovery and independent Tasks VIDEO hands read copies of one immutable image. Matching pixel checksums, dimensions and source timestamps are verified.',
           '* The original Holistic result is forwarded unchanged. Manual detector hands are never substituted into its output; the two feature streams remain separate.',
           '* A bitmap is retained until both detectors settle, including a failure of either reader. Both graphs reset between takes.',
           f'* **{summary["captureContractsPassed"]}/{summary["completedCaptures"]} completed captures passed** ({summary["pairedRecordingFrames"]} paired recording frames). One canceled NO take and the separate HELLO restart are preserved. Zero physical camera/microphone calls.',
           '* Production application sources, weights and gates are unchanged. The diagnostic server is stopped. Scalar checkpoints contain no images or raw landmark arrays.','',
           '## Actual diagnostic outputs — not recognition accuracy','',
           '| Attempt | Reference | Status | Contract | Body candidate | Manual expanded |','|---:|---|---|---|---|---|']
    lines += [f'| {r["number"]} | {r["label"]} | {r["status"]} | {r["contractPassed"]} | {r["bodyCandidate"]} | {r["manual"]} |' for r in rows]
    lines += ['',summary['scope'],'',
              'The body candidate missed most references and suggested LIKE for PLEASE. Manual expanded recognition also confused HUNGRY, PAIN, APPLE and the separate HELLO restart. These outputs are retained, not used to adjust gates. APPLE and PAIN are unsupported in the selected manual expanded vocabulary; false suggestions are not successes.', '',
              '## Fresh audit waiting for new-signer recordings','',
              'Metadata confirms all 11 official test signers were already audited. The provider said they can supply new-signer recordings; no files or folder path have been supplied yet. No reused cohort is described as fresh.', '',
              'Supply consented local clips with true labels, pseudonymous signer IDs and unique source IDs. The prepared fresh-audit-intake/intake-template.json targets the frozen 24-word candidate, with other signs explicitly marked negative for that candidate. Audit clips remain out of training/calibration. The validator does not infer consent or signer identity from a face.', '',
              f'Tests: {summary["frontend"]["passed"]} frontend passed, {summary["frontend"]["skipped"]} skipped; {summary["targetedPython"]["passed"]} targeted Python passed. Existing full-Python-discovery failures are not hidden and no full-suite pass is claimed.', '',
              'Next: validate the supplied intake, freeze the audit protocol/model/route policies before extracting predictions, then count every miss and unsupported-sign false acceptance. New training/validation data must be separate if retraining is needed. A durable full-198 production-browser regression still remains.']
    (out/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ('outcomes','completedCaptures','captureContractsPassed','pairedRecordingFrames','canceledOutcomesPreserved','candidatePromoted','freshNewSignerAuditRun','frontend','targetedPython')},indent=2))
if __name__=='__main__':main()
