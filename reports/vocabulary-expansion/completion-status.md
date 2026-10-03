# 201-word expansion: current status

**Not complete; no new candidate has been deployed.** The current website models
remain in place. Passing software tests does not demonstrate recognition accuracy.

## Motion-feature continuation

Completed development comparisons (210 target clips, 90 other-sign clips):

| Candidate | Correct | Wrong word | Other-sign false accepts | Release |
| --- | ---: | ---: | ---: | --- |
| Separate-rejection baseline | 76 | 3 | 1 | Failed |
| Residual motion ensemble | 145 | 4 | 4 | Failed |
| Aligned windows, existing classifier | 94 | 8 | 2 | Failed |
| Stable single-hand slots, existing classifier | 96 | 9 | 1 | Failed |
| Residual model with aligned windows | 132 | 3 | 3 | Failed |
| Aligned residual model with rejection guard | 132 | 3 | 2 | Failed |
| Explicit fingertip/body geometry | 129 | 3 | 2 | Failed |

The residual model uses explicit frame differences, training-only feature
normalization, residual temporal convolutions, mean/max pooling, and signing-speed
augmentation. Three seeds and their final ensemble use the unchanged acceptance
screen. Its browser parity passed on 74 cached examples; offline classifier
inference took about 301 ms median and 316 ms p95 on this server. These timings
exclude camera and landmark detection and were measured while another training
job competed for CPU. The residual candidate still has no correct FINE examples
at its selected thresholds and has more false accepts than the baseline.

The aligned residual model recognized at least one clip for all 50 targets, but
still failed the error requirements. A separately trained rejection guard removed
one other-sign false accept without removing the remaining errors. Explicit
fingertip/body geometry also failed the accuracy screen. Its Python/Chromium
predictions matched on 74 examples; single-model inference measured about 51 ms
median and 64 ms p95, excluding camera and landmark extraction.

The private pretrained ASL Citizen pilot completed: 3/50 target clips recognized,
zero wrong suggestions and 0/7 other-sign false accepts. Eleven target names had
no exact output-label match. This was one development clip per source label, not
a full validation set. The input encoding matched the author's implementation at
six lengths. Four of five exact labels matched in a separate training-source
sanity check; WANT produced the specific output WANT1. No guessed synonym or
numbered-variant mappings were used in the PopSign pilot. This model was not
adopted. See [pilot and sources](pretrained-citizen/README.md).

### Active follow-up: dynamic body references

`handspeak-dynamic-pose.service` is extracting all 2,815 development recordings
again, using 60 actual sampled frames and measuring the body in each frame.
Earlier training repeated a single body reference across the entire clip, so it
could not use actual head/upper-body movement. Existing hand detection thresholds
and the JavaScript sequence-quality rules remain unchanged. Training and
validation signers remain separate; no reserved test recording is opened.

The managed job resumes completed extraction caches, then automatically trains,
reloads the selected checkpoint, and checks browser parity. Models failing the
accuracy screen remain withheld. Even a validation pass is not deployment-ready
without independent evaluation, ordinary-movement negatives and live-camera tests.
The job continues after terminal/chat closure; the transient systemd unit does
not survive a server reboot. It is expected to take hours on this CPU-only server.

- [Live job status](/opt/handspeak-training/vocabulary-expansion-dynamic-pose/job-status.json)
- [Pipeline and commands](dynamic-pose/README.md)

Twenty-seven relevant tests passed before this run. A real-video extractor smoke
check produced 60 synchronized hand/body samples with actual increasing timestamps.

A metadata-only check fully scanned held-out AIRPLANE, CAN, FINE and SHOWER
archives. There are 147, 141, 128 and 17 previously unselected recording filenames,
respectively, but no signer IDs outside prior manifest selections. This is a
conservative exclusion: selected recordings may not all have been evaluated.
Fresh recording tests remain possible after freezing a candidate, with content
hash checks and explicit population limitations. Generalization to a genuinely
new signer population and real-camera ordinary movements still needs new evidence.
No test video payloads or landmarks were opened by this audit. See
[header-only holdout audit](holdout-readiness.json).

The user confirmed that only existing videos/OBS are available for testing. Use
the [recorded-video/OBS evaluation scope](obs-validation-plan.md), keep accuracy
requirements unchanged, and make no claim of testing newly recruited people or
physical webcams. This does not pause the training job.

The window audit found 2,636 of 2,815 development recordings had removable empty
boundaries or a dominant visible run. Feature frames decreased from 138,973 to
55,469; all original sequence-quality decisions remain unchanged. Five window
tests passed, including comparisons against the JavaScript encoder. Three new
model tests cover checkpoint reload, batch-independent inference, finite gradients,
and rejection without a runner-up fallback. Three slot-stability tests cover
coordinate preservation, missing/two-hand boundaries, and mirroring. Slot changes
are a research hypothesis, not verified hand-identity corrections; they changed
552 frame slots across 379 development clips without changing quality decisions.

These runs do not deploy automatically. A development-screen pass still requires
untouched evaluation, ordinary-movement negatives, and browser/camera integration
checks before a new word is enabled on the live website.

## Expanded training job: all 50 candidate words

**Completed:** the balanced-data model reached 94/210 correct, five wrong-word
suggestions, 111 misses, and eight false accepts among 90 other-sign clips.
Checkpoint reload and offline Chromium parity passed, but the unchanged accuracy
screen failed. Nothing was deployed. See [balanced results](joint50-balanced/README.md).

**Follow-up completed:** trained the seven other-sign labels as separate internal
rejection classes instead of collapsing them into one class. The 50 supported
targets, development recordings, and acceptance screen stay unchanged. All seven
rejection outputs remain unsupported for this candidate; a rejected winner never
falls back to another label. This also balances each rejection label separately
in the training loss. The result was **76/210 correct, three wrong-word suggestions,
131 misses, and one false accept among 90 other-sign clips**. Rejection improved,
but recall decreased and the unchanged accuracy screen still failed. It was not
deployed. [Separate-rejection results](joint50-separated/README.md).

Checkpoint reload reproduced validation. Offline Chromium/Python parity passed on
74 examples with the expanded 57-class head. Nineteen relevant regression tests
passed, including rejection without runner-up fallback and frozen class ordering.
Mirror averaging/agreement at unchanged thresholds yielded 72 correct, three wrong,
135 misses, and two other-sign false accepts; this strategy was not adopted.
These are reused development comparisons, not independent accuracy results.

The balanced experiment expanded the existing PopSign training set toward 48 clips per
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
result was available until that pipeline completed; its outcome is recorded above.

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
