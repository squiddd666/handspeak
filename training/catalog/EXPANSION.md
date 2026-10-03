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
