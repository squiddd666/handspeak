# Individual word training

Each candidate is trained with one supported output and 62 competing outputs
(other signs and ordinary actions). The classifier must choose that word over
every competing output; hiding other labels cannot turn a rejected sign into a
match. Development data select the checkpoint and cutoff before new recordings
are evaluated. Cutoffs are not calibrated confidence percentages.

## Status

| Word | Training | New recorded-sign screen | Publication |
| --- | --- | --- | --- |
| CALL | Complete; development passed | 4/4 CALL correct, 1/112 other signs falsely accepted | Withheld |
| FIND | Complete; development passed | Known ordinary-action regression failed; fresh sign test not started | Withheld |
| FISH | Running | Pending | Not published |
| SEE, SICK, PAIN, NIGHT, MORNING | Pending | Pending | Not published |

CALL also rejected all 90 full-clip/subwindow examples from 24 new ordinary-action
recordings. These windows are correlated, and neither this result nor its four
positive clips establishes general accuracy or accuracy on new people. Its
other-sign false acceptance fails the unchanged release screen.

FIND recognized 3/4 known sign clips and rejected all 132 other-sign clips, but
accepted one of 12 ordinary recordings (three accepts among 49 correlated
full-clip/window examples). That fails regression; fresh recordings were not
consumed for this candidate.

No new single-word model has been added to the live website. The existing live
vocabulary remains unchanged. Private main-app integration is under test;
camera-worker lifecycle tests pass, but end-to-end camera recognition has not
passed. Earlier camera timing runs overlapped CPU-heavy jobs and are inconclusive.

Per-word `job-status.json`, `completion.json`, `release-status.json` and
`fresh/test-results.json` record progress and outcomes. A completed training job
is not a passed release check. Publication requires passed development, sign and ordinary-action regression
screens plus the new recorded-sign test. On 2026-10-10 the owner explicitly
waived camera and application integration checks for experimental publication.
The queue no longer waits for camera, browser parity or integration checks.

## Storage

Raw recordings remain outside the served website. Seven unused older derived
feature caches were losslessly compressed to preserve the download disk reserve.
`/opt/handspeak-training/archived-feature-caches-20261010.json` records their
original paths, SHA-256 digests and compressed paths. Restore a cache before
rerunning an older experiment that references its original path. The active
single-word training source was not compressed.

## Running queue

`handspeak-single-word-queue-20261010.service` adopts the existing FIND job,
then processes FISH, SEE, SICK, PAIN, NIGHT and MORNING in that fixed order.
Only one training/evaluation workload runs at a time. Development or sign-screen
failures advance to the next word. Operational failures stop with an error.
A passed sign screen triggers experimental publication after the publisher
rechecks all recorded accuracy gates against the exact frozen checkpoint.
Camera/integration results are explicitly marked unverified. The original running
queue is allowed to finish its current evaluation;
`handspeak-single-word-publication-20261010.service` adopts it at that boundary
without restarting training or downloads. Subsequent passing words publish
automatically, then the queue continues. Public assets are backed up and
rolled back if model delivery verification fails.
`queue-status.json` is the machine-readable status.

Software controls verified before the waiver: 14 existing application model tests, the added
cancelled-camera-start regression, eight camera-worker/delegate checks and four
queue continuation/failure checks. These are software tests, not accuracy claims.
