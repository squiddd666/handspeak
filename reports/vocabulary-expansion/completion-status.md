# 201-word expansion: current status

**Not complete; no new candidate has been deployed.** The current website models
remain in place. Passing software tests does not demonstrate recognition accuracy.

## Expanded training job: all 50 candidate words

The next experiment expands the existing PopSign training set toward 48 clips per
target word, retaining prior clips and limiting additional recordings to two per
signer. Most target words previously had only 9–12 training clips. Source glosses
are taken from the established recordings (for example, PAIN uses `owie`), not
guessed from English labels. Validation remains unchanged; known validation and
test signer identities and recording hashes are excluded from new training data.
Only test identity manifests are read, not test recordings, landmarks, or outcomes.

Downloads and extraction are resumable outside the served website under
`/opt/handspeak-training/vocabulary-expansion-joint50-balanced`. The pass criteria
are unchanged. No passing result or new deployment is claimed for this experiment.
Twenty-five pipeline tests passed before the expanded training run.

All 1,312 additional videos have downloaded. The combined input has 2,515 training
recordings (2,287 target-word recordings), with no duplicate recording hashes.
Landmark extraction and then training/checkpoint verification run as one pipeline;
status is recorded in the private experiment's `job-status.json`. No new accuracy
result is available until that pipeline completes.

The job is managed by `handspeak-joint50-balanced.service`, with a three-core CPU
quota and 5 GiB memory limit. It resumes cached downloads/extractions and runs
training, checkpoint verification, and offline Chromium parity in order. A failed
stage stops the pipeline. It never deploys a model or equates a validation pass
with independent accuracy. Terminal/chat closure does not stop the managed job;
after a server reboot, the transient service must be started again.
Final results are written to `reports/vocabulary-expansion/joint50-balanced/`.
Current status: `/opt/handspeak-training/vocabulary-expansion-joint50-balanced/job-status.json`.

The existing recovered candidate also passed offline Chromium/Python parity on
74 validation examples covering 57 target/rejection labels, including tracking
failures. This verifies classifier implementation consistency, not recognition
accuracy or real-time camera behavior. See
[browser parity](joint50-recovery/browser-parity.json).

## Latest continuation: diagnose misses, motion ordering, and tracking recovery

Reloaded the joint candidate and separated detector failures, raw classification,
and rejected predictions. Before rejection filtering, it selected the right target
word on 851/975 training clips and 127/210 validation clips. There were 109 training
and 22 validation target clips without a usable tracked sequence. Raw top-1 ignores
the quality gate and is diagnostic only; it is not recognized-word accuracy.
See [diagnostic results](joint50/diagnostic.json).

Tested four ordered temporal pooling regions against the original single-region
average, keeping the development data, training search, and acceptance screen
unchanged. The new candidate was worse: **9/210 correct, three wrong-word suggestions,
198 rejected, and five false accepts among 90 other-sign clips**. It remains private.
See the [motion-order experiment](joint50-phases/README.md). Both checkpoints reproduce
their recorded validation after reload. This does not justify lowering rejection
thresholds or deploying the new model.

Retried 117 failed, sparsely sampled development clips using up to 60 actual source
frames and unchanged detector thresholds. This recovered 75 usable sequences:
49 training and 26 validation. Only five training and three validation recoveries
were target words; the other 67 were rejection examples. Original caches and source
videos were preserved. See the [recovery counts](joint50-recovery/recovery-result.json).

Retraining the original architecture on this recovered data produced **52/210
correct, six wrong-word suggestions, 152 rejected, and six false accepts among 90
other-sign clips**. Compared with the baseline, it recognized eight more clips but
increased both wrong-word and other-sign errors. It failed the unchanged release
screen and was not deployed. See the [retrained candidate](joint50-recovery/README.md).
This compares pipelines on previously inspected development recordings, not a new
independent accuracy benchmark. Denser offline sampling is not proof of real-time
camera performance.

| Development pipeline | Correct / 210 | Wrong word | Rejected | Other-sign false accepts / 90 |
| --- | ---: | ---: | ---: | ---: |
| Original joint model | 44 | 4 | 162 | 0 |
| Four ordered temporal regions | 9 | 3 | 198 | 5 |
| Original architecture + denser tracking recovery | 52 | 6 | 152 | 6 |

Twenty-one pipeline tests passed, including architecture freezing, checkpoint
round-trip, motion-order preservation, and isolated tracking-recovery guards.
No independent test clips were opened and no model was deployed.

## Earlier continuation: joint 50-word experiment and additional lexical sources

Trained a joint temporal candidate for all 50 catalog labels represented in the
combined cached PopSign development data. On development validation it recognized
**44/210 target clips correctly, made four wrong-word suggestions, and missed 162**.
It accepted none of the 90 other-sign clips. The candidate failed the frozen
validation screen and remains private; it was not deployed. Reloading its checkpoint
reproduced those results. See the [joint experiment report](joint50/README.md).
Sixteen pipeline tests passed, including duplicate/partition guards and protection
against treating incorrect dictionary naming responses as equivalent signs.

The metadata audit found ten additional source leads through ASL-LEX's SignBank
translation fields and Rutgers/BU SignBank annotations. This reduces entries
without a candidate from 23 to 13. These are **unverified semantic mappings**:
for example, RICE appears in translations associated with RAT, and HOW MUCH has
several possible variants. No automatic relabeling, video download, or recognition
enablement follows from those matches. ASL-LEX reference videos are excluded from
its metadata license and were not downloaded.

## Earlier continuation: fresh eight-word test

A vocabulary restricted on development validation passed that screen (23/32
correct, no incorrect suggestions on 162 other-sign clips). The unchanged frozen
candidate was then evaluated on 96 fresh recordings: **35/48 target signs correct,
12 missed, one wrong-word suggestion, and one false accept among 48 other signs**.
It failed the predeclared zero-incorrect-suggestions screen and was not deployed.
See the [fresh test report](fresh-test/README.md). Thirteen software tests passed.

The main `all-201-readiness.csv` now incorporates the additional dataset leads:
9 previously enabled experimental entries, 179 entries with candidate sources,
and 13 without a candidate. BAG gained an additional numbered-variant lead
(`BAG1` / `BAG2`) from ASL Citizen; this mapping still needs review.
The original source-only statuses are retained for
audit history. Candidate sources still require verification and training.

## Earlier work completed

- Downloaded 342 additional PopSign training recordings outside the served site.
- Expanded the first ten target words from 120 to 462 training clips, representing
  16–29 training signers per word. The full dataset, including other-sign negatives,
  has 927 training clips (828 usable) and the unchanged 194 validation clips.
- Extracted new hand sequences and center-frame body references. Preserved separate
  training/validation participants and hashes; no test videos were opened.
- Trained an expanded temporal model and DTW baseline, then a separate temporal
  experiment weighting other-sign errors more heavily. Saved protocols, model
  hashes, results, and resumable preparation scripts.
- Ten pipeline tests passed. The expanded temporal checkpoint was reloaded and
  reproduced its recorded validation metrics.
- Audited official WLASL and MS-ASL metadata, finding 42 source leads for entries
  previously lacking a local-source candidate. No WLASL/MS-ASL videos were trained
  or published in this continuation.

## Validation comparison

All rows use the same 40 target-word and 154 other-sign validation clips. These
results influenced model selection and are not an independent accuracy estimate.

| Experiment | Correct / 40 | Wrong supported word | Missed | Other-sign false accepts / 154 |
| --- | ---: | ---: | ---: | ---: |
| First temporal batch | 20 | 1 | 19 | 6 |
| Expanded data + body references | 25 | 0 | 15 | 5 |
| Expanded data + stronger rejection loss | 23 | 0 | 17 | 3 |
| First DTW batch | 4 | 0 | 36 | 0 |
| Expanded DTW | 10 | 0 | 30 | 0 |

None passed the frozen screen: at least 20 correct, zero wrong-word/other-sign
suggestions, and at least one correct example for every target word. The stricter
temporal model reduced false accepts while missing more supported signs; the DTW
model rejected too many supported signs. No acceptance threshold was weakened
for release.

## What prevents completion

Of the 201 catalog entries, 9 were already enabled as experimental recognition,
179 other entries now have a source lead, and 13 still have no candidate in the
datasets compared. **A source lead is not a verified sign mapping, accessible
training set, or trained recognizer.** Additional clips must be checked for meaning,
availability, permitted use, duplicates, and signer separation. Multi-sign phrases
also need sequence-level annotation and evaluation.

The 13 entries without a candidate are GOOD EVENING, FEVER, STOMACHACHE, PHARMACY,
CLASSMATE, POLICE STATION, MARKET, TAXI, DON'T TOUCH, UNSAFE, CALL POLICE,
CALL AMBULANCE, and DON'T HAVE. These require verified recordings or reviewed
multi-sign annotations. Existing source leads also need semantic and licensing
checks before training; they are not all ready-to-use data.

Models must still pass an untouched signer test, ordinary hand-movement negatives,
existing-vocabulary regression, and timed automatic-camera/browser tests. No live
camera accuracy or 201-word coverage is demonstrated here.

## Artifacts

- [Expanded-model results](batch2/README.md)
- [Joint 50-word results](joint50/README.md)
- [Stronger-rejection results](batch2-rejection/README.md)
- [Additional source candidates](additional-source-candidates.md)
- [Preparation and training commands](../../training/catalog/EXPANSION.md)

Sources: [PopSign](https://signdata.cc.gatech.edu/view/datasets/popsign_v1_0/index.html),
[WLASL](https://github.com/dxli94/WLASL), and
[Microsoft MS-ASL](https://microsoft.github.io/data-for-society/dataset?d=MS-ASL-American-Sign-Language-Dataset).
