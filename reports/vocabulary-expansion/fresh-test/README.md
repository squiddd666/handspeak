# Fresh-recording test of the eight-word candidate

**Failed the frozen release screen. No new word was enabled.**

The development-selected vocabulary is THIRSTY, HOT, SICK, READ, CALL, FIND, NOW,
and TOMORROW. GIVE and MILK were excluded using development results before fresh
test access. Predictions for excluded classes are rejected, without choosing the
next-best word or renormalizing probabilities. The original eleven-output network
and its checkpoint, threshold, and margin were frozen before new clips were selected.

| Evaluation | Correct target signs | Wrong target word | Missed | False accepts on other signs |
| --- | ---: | ---: | ---: | ---: |
| Development validation | 23/32 | 0 | 9 | 0/162 |
| Fresh recordings | 35/48 | 1 | 12 | 1/48 |

The two incorrect suggestions were THIRSTY → CALL and FINISH → HOT. The model
was not retuned on these results. It failed the predeclared requirement of zero
incorrect suggestions, despite recognizing more than half the supported clips.
Do not remove those classes after seeing this test and describe the remaining
results as another independent test.

Per-word correct results: THIRSTY 4/6, HOT 4/6, SICK 4/6, READ 3/6, CALL 5/6,
FIND 6/6, NOW 5/6, TOMORROW 4/6. Six clips per word are too few to establish
reliable per-word accuracy. A 6/6 result is not evidence of perfect recognition.

## Test integrity and limits

Downloaded 96 fresh PopSign recordings: six per target word and six each for
MILK, GIVE, CAR, LIKE, HELLO, WATER, PLEASE, and FINISH. Selection used at most
two clips per signer per word. Previously used/reserved recording filenames were
excluded, then hashes were checked against prior manifests and development data.
Training/validation/test participants are separate for this experiment.

These are fresh recordings from the official test signer pool. That pool has
appeared in earlier research; it is not a never-inspected population. Model
selection used development validation only. Failed tracking remains in the
denominator. Extraction uses up to 60 sampled source frames and a center-frame
body reference, so this is an offline isolated-sign test, not a live webcam test.

Ordinary hand movements, automatic-capture timing, runtime feature parity, and
combined recognition with the existing website vocabulary remain unevaluated.
Passing this clip screen alone would not have authorized deployment.

The raw recordings, landmarks, and checkpoint remain outside the served website
at `/opt/handspeak-training/vocabulary-expansion-fresh-test`. Public artifacts here
contain only protocol, hashes, counts, and evaluation results.

## Reproduce

From the repository, using the existing frozen experiment and caches:

```sh
/opt/handspeak-training/venv/bin/python training/catalog/test_frozen_expansion.py freeze
/opt/handspeak-training/venv/bin/python training/catalog/test_frozen_expansion.py download
/opt/handspeak-training/venv/bin/python training/catalog/test_frozen_expansion.py extract
/opt/handspeak-training/venv/bin/python training/catalog/test_frozen_expansion.py evaluate
PYTHONPATH=.:training:training/daily_words:training/catalog /opt/handspeak-training/venv/bin/python -m unittest training.catalog.test_fresh_protocol training.catalog.test_expansion_batch training.catalog.test_expand_batch_data training.daily_words.test_training
```

Thirteen software tests passed, including rejection of masked winners, counting
excluded vocabulary as negatives, protocol-tampering detection, and existing
five-word model behavior. A shared-label-state defect found during testing was
fixed before benchmark inference; model weights and decision settings were unchanged.

Source: [PopSign ASL v1.0](https://signdata.cc.gatech.edu/view/datasets/popsign_v1_0/index.html),
Georgia Tech and DPAN, CC BY 4.0.
