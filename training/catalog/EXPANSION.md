# Reproducible vocabulary expansion

The 201-entry learning catalog is not a trained 201-class recognizer. Consult
`reports/vocabulary-expansion/all-201-readiness.csv` for source availability and
the experiment reports for measured performance. No script in this workflow
deploys models or marks untested words as supported.

## Expanded first batch

Words: THIRSTY, HOT, SICK, READ, GIVE, CALL, FIND, NOW, TOMORROW, MILK.
CALL uses the established PopSign source gloss `callonphone`.

The second experiment retains the original development validation set, expands
each target to at most 48 training recordings and two examples per signer,
extracts up to 60 unique video frames for new clips, and adds center-frame
upper-body references. Existing clips retain their cached hand sampling.
Missing/invisible body references use the original wrist-centered fallback.
Training and validation signer/hash overlaps stop preparation.

Run from `/opt/handspeak/repository` using the existing training environment:

```sh
/opt/handspeak-training/venv/bin/python training/catalog/expand_batch_data.py --stage download
/opt/handspeak-training/venv/bin/python training/catalog/expand_batch_data.py --stage extract --workers 3
/opt/handspeak-training/venv/bin/python training/catalog/expand_batch_data.py --stage body --workers 2
/opt/handspeak-training/venv/bin/python training/catalog/train_expansion_batch.py --source /opt/handspeak-training/vocabulary-expansion-batch2/body-development-features.json --output /opt/handspeak-training/vocabulary-expansion-batch2 --model temporal
/opt/handspeak-training/venv/bin/python training/catalog/train_expansion_batch.py --source /opt/handspeak-training/vocabulary-expansion-batch2/body-development-features.json --output /opt/handspeak-training/vocabulary-expansion-batch2 --model dtw
/opt/handspeak-training/venv/bin/python training/catalog/report_expansion.py --root /opt/handspeak-training/vocabulary-expansion-batch2 --output reports/vocabulary-expansion/batch2
```

Downloads, per-clip landmarks, and body references are cached outside the served
website. A completed word selection is frozen before clip downloads. Re-running
reuses existing completed caches. A model protocol cannot be silently replaced
with different data: create a new experiment directory for subsequent training.
The downloader stops before consuming the last 5 GB of free disk.

The separate stronger-rejection experiment reuses the same extracted data with
`--output /opt/handspeak-training/vocabulary-expansion-batch2-rejection --negative-weight 10`.
This multiplies the temporal loss weight for the OTHER MOVEMENT class by ten;
the chosen multiplier is frozen in the protocol before training. The DTW baseline
is unchanged and reused only after verifying identical source-data hashes and
labels. See `reports/vocabulary-expansion/completion-status.md` for the measured
tradeoff; the change did not pass the release screen.

## Interpretation and release

The temporal and DTW configurations are selected on validation, including
rejection thresholds. Softmax values are not calibrated confidence percentages.
This reused validation set is development evidence only; additional training,
body features, and changed sampling are confounded in the second experiment.

Passing the development screen is necessary but insufficient for deployment.
Require an untouched signer test, ordinary-movement negatives, comparison with
current word recognition, and timed automatic-capture/browser checks. Do not
weaken rejection thresholds merely to make labels appear. English phrases may
need multiple signs and non-manual features; source gloss text alone is not a
verified semantic mapping.

Source: [PopSign ASL v1.0](https://signdata.cc.gatech.edu/view/datasets/popsign_v1_0/index.html),
Georgia Tech and DPAN, CC BY 4.0. This dataset is intended for isolated-sign
recognition; it does not establish continuous sign-language translation.

## Checks

```sh
PYTHONPATH=.:training:training/daily_words:training/catalog /opt/handspeak-training/venv/bin/python -m unittest training.catalog.test_expand_batch_data training.catalog.test_expansion_batch training.daily_words.test_training
```

## Joint catalog experiment

The trainer accepts `--labels-file` for a JSON list of target labels. A custom
vocabulary must have usable training clips and validation coverage for every label,
plus other-sign negatives in both partitions. Missing data does not create an
output class that can be advertised as supported.

The current joint experiment combines cached development recordings, deduplicated
by recording hash, and rejects conflicting annotations or cross-partition signers.
It uses all 50 catalog words represented in those caches and seven other signs
as negatives. It does not replace the website's existing vocabulary.

```bash
/opt/handspeak-training/venv/bin/python training/catalog/prepare_joint_experiment.py \
  --output /opt/handspeak-training/vocabulary-expansion-joint50
/opt/handspeak-training/venv/bin/python training/catalog/train_expansion_batch.py \
  --source /opt/handspeak-training/vocabulary-expansion-joint50/development-features.json \
  --labels-file /opt/handspeak-training/vocabulary-expansion-joint50/labels.json \
  --output /opt/handspeak-training/vocabulary-expansion-joint50 --model temporal
/opt/handspeak-training/venv/bin/python training/catalog/report_joint_experiment.py \
  --experiment /opt/handspeak-training/vocabulary-expansion-joint50 \
  --report reports/vocabulary-expansion/joint50
```

The saved checkpoint failed validation. The report command verifies data and
checkpoint hashes and reproduces validation before exporting evidence. It never
exports a deployable model. See `reports/vocabulary-expansion/joint50/README.md`.

## Diagnose misses and test temporal ordering

`diagnose_joint.py` reloads a frozen checkpoint and separates tracking failures,
raw top-1 classification, and accepted predictions on train/validation clips.
Raw top-1 deliberately ignores rejection and must not be exposed as recognized
words. The baseline had 127/210 correct raw validation choices but only 44 accepted
correct predictions, with 22 target clips failing the tracking/sequence gate.

`--temporal-bins 4` tests four ordered pooling regions instead of the original
single average. It leaves the data, seed/width grid, optimizer, and release screen
unchanged. Use a fresh experiment output directory; the architecture is frozen
in its protocol. The existing default remains one bin, including older checkpoint
loading paths. The four-region experiment failed validation (9 correct, 3 wrong,
198 missed, 5/90 other-sign false accepts) and must not be deployed.

```bash
/opt/handspeak-training/venv/bin/python training/catalog/diagnose_joint.py \
  --experiment /opt/handspeak-training/vocabulary-expansion-joint50 \
  --report reports/vocabulary-expansion/joint50
/opt/handspeak-training/venv/bin/python training/catalog/train_expansion_batch.py \
  --source /opt/handspeak-training/vocabulary-expansion-joint50/development-features.json \
  --labels-file /opt/handspeak-training/vocabulary-expansion-joint50/labels.json \
  --output /opt/handspeak-training/vocabulary-expansion-joint50-phases \
  --model temporal --temporal-bins 4
```

`recover_joint_tracking.py` retries only failed development clips containing fewer
than 60 sampled frames, using up to 60 actual frames from the original video. It
does not lower detector confidence or quality thresholds. Isolated hard links and
landmark caches preserve old experiments; center-frame body references are aligned
to the new frame count. Its source hashes, selection, encoder hashes, and detector
hash are recorded before extraction. Test clips are rejected. A successful tracking
retry is not proof of correct classification or live-camera performance.

```bash
/opt/handspeak-training/venv/bin/python training/catalog/recover_joint_tracking.py \
  --source /opt/handspeak-training/vocabulary-expansion-joint50/development-features.json \
  --output /opt/handspeak-training/vocabulary-expansion-joint50-recovery
/opt/handspeak-training/venv/bin/python training/catalog/train_expansion_batch.py \
  --source /opt/handspeak-training/vocabulary-expansion-joint50-recovery/development-features.json \
  --labels-file /opt/handspeak-training/vocabulary-expansion-joint50/labels.json \
  --output /opt/handspeak-training/vocabulary-expansion-joint50-recovery --model temporal
/opt/handspeak-training/venv/bin/python training/catalog/report_joint_experiment.py \
  --experiment /opt/handspeak-training/vocabulary-expansion-joint50-recovery \
  --report reports/vocabulary-expansion/joint50-recovery
```

This pass recovered usable sequences for 75 of 117 attempted development clips
(49 train, 26 validation). That is tracking coverage, not recognition accuracy;
consult the retrained-model report for classification results.

## Expand the joint training set across signers

`expand_joint_data.py` retains the recovered development set and selects additional
official PopSign training recordings toward 48 clips per target label. It reuses
the established source URL for each word, limits new clips to two per signer,
and excludes known held-out signer IDs and recording hashes. Test manifests supply
identities only; no test media, features, predictions, or outcomes are opened.
The validation rows must remain exactly unchanged after merging. Duplicate hashes
with conflicting labels/identities fail the job. Video hashes are rechecked before
feature extraction; a 5 GB free-space floor is retained while downloading.

```bash
/opt/handspeak-training/venv/bin/python training/catalog/expand_joint_data.py \
  --source /opt/handspeak-training/vocabulary-expansion-joint50-recovery/development-features.json \
  --labels-file /opt/handspeak-training/vocabulary-expansion-joint50/labels.json \
  --output /opt/handspeak-training/vocabulary-expansion-joint50-balanced --stage download
/opt/handspeak-training/venv/bin/python training/catalog/expand_joint_data.py \
  --source /opt/handspeak-training/vocabulary-expansion-joint50-recovery/development-features.json \
  --labels-file /opt/handspeak-training/vocabulary-expansion-joint50/labels.json \
  --output /opt/handspeak-training/vocabulary-expansion-joint50-balanced --stage extract
/opt/handspeak-training/venv/bin/python training/catalog/train_expansion_batch.py \
  --source /opt/handspeak-training/vocabulary-expansion-joint50-balanced/development-features.json \
  --labels-file /opt/handspeak-training/vocabulary-expansion-joint50/labels.json \
  --output /opt/handspeak-training/vocabulary-expansion-joint50-balanced --model temporal
```

48 is a sampling target, not a claim that each source has 48 eligible recordings.
Inspect `coverage.json` for actual usable clips and signer counts. Existing source
shortfalls must not be filled with duplicated or held-out recordings. More data
alone is not proof that the model passes the unchanged accuracy screen.

`check_joint_browser.py --experiment <frozen-directory> --report <report-directory>`
checks the one-bin classifier's Python/Chromium feature, logit, and accepted-label
parity. It uses cached validation examples covering each label and tracking-quality
state in an isolated blank Chromium page; it does not send videos or landmarks to
the live site. This is not an end-to-end camera, pose-tracker, latency, or independent
accuracy test. The separate four-bin research architecture is explicitly rejected
by this browser evaluator rather than silently evaluated with the wrong pooling.

### Managed execution

`run_balanced_training.py` runs download, extraction, training, checkpoint reload,
and Chromium parity sequentially. It holds a nonblocking job lock, quarantines
only malformed generated caches left by interruption, and stops on any failed
stage. Logs and `job-status.json` are in the private experiment directory. A
validation pass still requires independent testing; this runner never deploys.

```bash
systemd-run --unit=handspeak-joint50-balanced \
  --property=WorkingDirectory=/opt/handspeak/repository \
  --property=Nice=10 --property=CPUQuota=300% --property=MemoryMax=5G \
  --property=NoNewPrivileges=yes \
  /opt/handspeak-training/venv/bin/python \
  /opt/handspeak/repository/training/catalog/run_balanced_training.py
systemctl status handspeak-joint50-balanced.service
```

Do not start a second extraction/training process in the same experiment directory.
This transient unit survives terminal closure, but not a server reboot; rerun the
command after reboot to resume caches. Existing validation/source hashes remain
checked, and training restarts reproducibly after an interrupted training stage.
