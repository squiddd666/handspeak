"""Freeze identity-screened online clips without predicting, training, or tuning."""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import re
from pathlib import Path
if __package__:
    from .prepare_targeted_data_v4 import MANUAL
else:
    from prepare_targeted_data_v4 import MANUAL

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def main(args):
    out = args.out.resolve()
    out.mkdir(exist_ok=False)
    evidence, clips, exclusions, seen = {}, [], [], set()
    downloaded = byte_count = decoded = 0
    decode_failures = []
    snapshots = []
    batch_counts = []
    transport_verified = True
    for number, folder in enumerate(args.batch, 1):
        folder = folder.resolve()
        rows = json.loads((folder / 'downloads.json').read_text(encoding='utf-8'))
        protocol = json.loads((folder / 'protocol.json').read_text(encoding='utf-8'))
        integrity = json.loads((folder / 'video-integrity.json').read_text(encoding='utf-8'))
        snapshots.append(protocol['modelAndRuntimeSha256'])
        transport_verified = transport_verified and protocol['transportCertificateVerified']
        batch_counts.append(dict(batch=str(folder), downloaded=sum(r['status'] == 'downloaded' for r in rows),
                                 recordingNew=sum(r['auditEligible'] for r in rows), excluded=sum(not r['auditEligible'] for r in rows)))
        for name in ('downloads.json', 'protocol.json', 'frozen-selection.json', 'summary.json', 'video-integrity.json'):
            evidence[str(folder / name)] = sha(folder / name)
        health = {r['auditId']: r for r in integrity['files']}
        decoded += integrity['summary']['decodedFrames']
        for row in rows:
            identifier = f"batch-{number}-{row['auditId']}"
            downloaded += row['status'] == 'downloaded'
            byte_count += row['byteSize'] if row['status'] == 'downloaded' else 0
            if not row['auditEligible'] or row.get('sha256') in seen:
                exclusions.append(dict(id=identifier, member=row['member'], label=row['label'],
                                       reason=row.get('exclusionReason') or row.get('error') or 'Duplicate across batches'))
                continue
            seen.add(row['sha256'])
            negative = row['negativeForFrozen24WordCandidate']
            if (row['label'] in MANUAL) == negative:
                raise ValueError('Candidate label/negative flag mismatch')
            path = Path(row['path'])
            if sha(path) != row['sha256']:
                raise ValueError('Downloaded bytes changed before intake freeze')
            if not health[row['auditId']]['fullDecodePassed']:
                decode_failures.append(identifier)
            clips.append(dict(file=identifier, path=str(path), sourceId=row['source'] + ' > ' + row['member'],
                              source='PopSign ASL v1.0, game category', publisherLabel=row['publisherLabel'],
                              publisherSplit=row['publisherSplit'], member=row['member'],
                              participant='PopSignV1:' + row['participant'], label=row['label'],
                              manualLabel=None if negative else row['label'], negative=negative,
                              sha256=row['sha256'], split='audit-only',
                              fullDecodePassed=health[row['auditId']]['fullDecodePassed']))
    unchanged = all(snap == snapshots[0] for snap in snapshots)
    unchanged = unchanged and all(sha(ROOT / name) == digest for name, digest in snapshots[0].items())
    test_log = args.batch[-1].resolve() / 'intake-tests.log'
    test_text = test_log.read_text(encoding='utf-8-sig')
    test_count = re.search(r'Ran (\d+) tests', test_text)
    if test_count is None or not re.search(r'^OK\s*$', test_text, re.M):
        raise ValueError('Missing successful targeted intake-test evidence')
    evidence[str(test_log)] = sha(test_log)
    cohort = dict(purpose='audit-only', cohortType='recording-new known-signer regression',
                  publisher='Georgia Institute of Technology / Deaf Professional Arts Network',
                  sourceUrl='https://signdata.cc.gatech.edu/view/datasets/popsign_v1_0/index.html',
                  license='CC BY 4.0', licenseUrl='https://creativecommons.org/licenses/by/4.0/',
                  consentEvidenceType='Publisher public-use consent statement; no user/new-signer declaration fabricated',
                  newSignerDeclarationMade=False, signerIdentityAcrossDatasetsVerified=False,
                  modelAndRuntimeSha256=snapshots[0], sourceEvidenceSha256=evidence,
                  predictionsRun=False, trainingAllowed=False, calibrationAllowed=False,
                  clips=clips)
    save(out / 'frozen-online-intake.json', cohort)
    save(out / 'excluded-recordings.json', exclusions)
    counts = collections.Counter(r['label'] for r in clips)
    positives = {r['label'] for r in clips if not r['negative']}
    previous_signers = set(json.loads((ROOT / 'models/asl-words-evaluation.json').read_text(encoding='utf-8'))['signers']['test'])
    signer_ids = sorted({r['participant'] for r in clips})
    summary = dict(downloadedRecordings=downloaded, downloadedBytes=byte_count,
                   recordingNewRecordings=len(clips), excludedRecordings=len(exclusions),
                   positiveRecordings=sum(not r['negative'] for r in clips),
                   unsupportedCandidateRecordings=sum(r['negative'] for r in clips),
                   counts=dict(sorted(counts.items())), candidateWordCoverage=len(positives), candidateWords=24,
                   missingCandidateWords=sorted(set(MANUAL) - positives),
                   signerIds=signer_ids, signerIdsPreviouslyUsed=all(p.split(':', 1)[1] in previous_signers for p in signer_ids),
                   fullDecodePassed=len(clips) - len(decode_failures), decodeFailuresRetained=decode_failures,
                   allDownloadedFramesDecoded=decoded, modelAndRuntimeUnchanged=unchanged,
                   freshNewSignerAudit=False, independentCrossDatasetSignerSeparation=False,
                   predictionsRun=False, recognitionImprovementClaimed=False, trainingOrCalibrationAllowed=False,
                   intakeSha256=sha(out / 'frozen-online-intake.json'), evidenceSha256=evidence,
                   targetedIntakeTests=int(test_count.group(1)), targetedIntakeTestsPassed=True,
                   batches=batch_counts,
                   provenanceScope='Previously unused according to available source keys and hashes; not proof that every historic private recording is inventoried.',
                   transportCertificateVerified=transport_verified,
                   transportLimitation='Publisher certificate chain was untrusted on this host. Acquisition used an explicitly scoped public-host-only unverified TLS context, without credentials. Local hashes are not publisher authentication.')
    save(out / 'summary.json', summary)
    table = '\n'.join(f'| {label} | {count} |' for label, count in sorted(counts.items()))
    missing = ', '.join(summary['missingCandidateWords'])
    text = f'''# Online recognition recording intake — 2026-11-07

**{len(clips)} previously unused recordings retained for audit. Recognition is not repaired by downloading data.**

* Downloaded {downloaded} publisher-original clips ({byte_count / 1024**2:.1f} MiB); excluded {len(exclusions)} known/duplicate clips. Exclusions and both acquisition selections remain intact.
* {summary['positiveRecordings']} recordings cover **{len(positives)}/24 candidate words**; {summary['unsupportedCandidateRecordings']} APPLE/CAR/DOG recordings are negatives for this frozen candidate, not necessarily for the full application.
* {len(summary['signerIds'])} **previously used** PopSign signer IDs. These are new recordings to the available inventory, not a fresh-new-signer audit. Identity overlap with anonymous ASL Citizen participants is unverified. No identity is inferred from faces.
* {summary['fullDecodePassed']}/{len(clips)} included clips passed size/hash/full-decode checks; {decoded} frames decoded across all acquired files. Decode checks did not choose winners or alter videos.
* All {len(snapshots[0])} frozen model/runtime files unchanged: **{unchanged}**. No predictions, training, calibration, candidate installation, or physical-camera calls occurred.
* {summary['targetedIntakeTests']} targeted intake tests passed, including the unchanged stricter user-provided fresh-signer validator. No new full application test pass is claimed.

## Provenance and license

Original **PopSign ASL v1.0**, game category, official test split; Thad Starner et al., Georgia Institute of Technology and Deaf Professional Arts Network.

- [Publisher and public-use consent statement](https://signdata.cc.gatech.edu/view/datasets/popsign_v1_0/index.html)
- [CC BY 4.0 license](https://creativecommons.org/licenses/by/4.0/)
- [Original download documentation](https://signdata.cc.gatech.edu/view/guides/downloading_popsign/index.html)

Original archive URLs, member names, signer IDs, original-byte SHA-256 hashes and absolute local paths are recorded in `frozen-online-intake.json`. Videos remain outside the served repository. Only local cache filenames were changed; video bytes, framing, timing and audio are unchanged. No endorsement is implied.

Publisher v2 pages re-anonymize IDs and move some legacy fitting recordings into their test split. The two checked v2 NO original-archive links returned 404; no v2 preview was used as a substitute. Publisher previews change resolution and duration and are unsuitable here.

**Transport limitation:** the publisher certificate chain was untrusted on this host. The downloader used a public-publisher-host-only unverified TLS context, without credentials. Hash checks establish consistency with available records, not authenticated publisher checksums. Publisher snapshots and this limitation are preserved.

## Identity screening, not performance selection

The first acquisition selected clips using metadata only, then found {batch_counts[0]['excluded']} known-content exclusions despite unfamiliar filenames. Those clips were retained as exclusions, not relabeled as fresh. The second acquisition used a fixed archive metadata offset of 60, frozen before downloading videos, to avoid early members whose older audit hashes lacked filenames. Both phases excluded known recording keys and PopSign fitting signer IDs, then checked content hashes. No recognizer outputs influenced acquisition or deduplication.

Missing candidate labels: **{missing}**. Related HURT/WANTTO/PETSNAME labels were not silently substituted. These files do not cover all 198 application words.

| Publisher-aligned label | New recordings |
|---|---:|
{table}

## Next

Freeze the exact production/candidate inference and browser sampling protocol before making predictions. Run every included clip once, keeping tracking failures, rejections and incorrect/unsupported acceptances in the denominator. Do not train or select gates on this cohort. If retraining is justified, obtain separate development recordings; keep this intake audit-only. A genuinely new-signer audit and the full-198 production-browser regression remain outstanding.
'''
    with (out / 'README.md').open('x', encoding='utf-8') as stream:
        stream.write(text)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, action='append', required=True)
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args())
