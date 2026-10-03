# First vocabulary expansion experiment — 3 October 2026

Trained both a compact temporal network and a DTW baseline for THIRSTY, HOT,
SICK, READ, GIVE, CALL, FIND, NOW, TOMORROW, and MILK. Neither passed validation;
no candidate was deployed and no new camera words were enabled.

## Results

| Candidate | Correct / 40 target clips | Wrong word | Missed | False accepts / 154 other-sign clips |
| --- | ---: | ---: | ---: | ---: |
| Temporal | 20 | 1 | 19 | 6 |
| DTW | 4 | 0 | 36 | 0 |

These are model-selection validation results, not independent accuracy claims.
The temporal model recognizes more examples but increases incorrect suggestions;
the DTW model rejects too many supported signs. Neither satisfies the frozen
screening gate: at least 50% correct, zero incorrect suggestions, and at least
one correct validation example for every target word.

The temporal false suggestions include SICK → HOT, GIRL/CAR → MILK,
FINE → SICK, CHAIR → READ, and HAVE → THIRSTY. Full counts, selected settings,
model hashes, and error identifiers accompany this report. The selected temporal
checkpoint was reloaded and reproduced its recorded validation metrics exactly.
Its probability threshold is an internal rejection setting, not calibrated
user-facing confidence.

## Data and limits

Used cached PopSign v8 development landmarks: 585 training recordings, 524 with
usable sequences, and 194 validation recordings. Target words account for 120
training recordings (112 usable) and 40 validation recordings. The remaining
39 labels serve as other-sign negatives. Training and validation participant
IDs and recording hashes are disjoint; invalid validation tracking counts as
a miss rather than being dropped. Mirroring augments training only.

Cached data has already been used in earlier research. No test partition was
opened during this experiment. The cache lacks upper-body pose, so temporal
features use the existing wrist-centered fallback. Other signs do not substitute
for ordinary hand-movement negatives. These are whole-clip experiments, not
automatic segmentation or OBS/webcam tests. Successful screening would still
require an untouched signer test, ordinary-movement negatives, regression tests
against existing vocabulary, and real-time browser evaluation before release.

Source attribution: PopSign ASL v1.0, Georgia Tech and DPAN, CC BY 4.0.
Raw data and model checkpoints remain outside the served website at
`/opt/handspeak-training/vocabulary-expansion-batch1`.

## Reproduce

From `/opt/handspeak/repository`:

```sh
/opt/handspeak-training/venv/bin/python training/catalog/train_expansion_batch.py --model temporal
/opt/handspeak-training/venv/bin/python training/catalog/train_expansion_batch.py --model dtw
PYTHONPATH=.:training:training/daily_words:training/catalog /opt/handspeak-training/venv/bin/python -m unittest training.daily_words.test_training training.catalog.test_expansion_batch
```

Six tests passed, covering the existing five-word training behavior, the expanded
output head and rejection behavior, and exclusion of overlapping participants,
duplicate recordings, and test partitions.

## Remaining work

Increase training signer diversity beyond the current 9–12 usable examples per
target word, add upper-body-relative positions to the feature extraction, and
collect ordinary-movement negatives. Freeze a new experiment before evaluating
it. Review source meanings and usage rights for the remaining candidate labels;
the 66 entries without verified local sources remain unresolved. The full 201-word
camera expansion is not complete.
