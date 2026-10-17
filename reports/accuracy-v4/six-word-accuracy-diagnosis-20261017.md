# Six-word default model — accuracy diagnosis (2026-10-17)

Measured on the held-out PopSign test split (signer-disjoint from training), using the
shipped prototypes and shipped rejection parameters. Reproduction script: `tuning/diagnose_six.py`.

## Where the accuracy actually goes

Recorded screen for the default six-word model (`models/motion-word-accuracy.json`, 12 clips
per word, 72 total):

| Word | Correct | Notes |
|---|---|---|
| PLEASE | 11/12 | perfect on trackable clips |
| THANK YOU | 8/12 | 3 tracked clips rejected |
| HELLO | 6/12 | 3 tracking failures, 3 rejections |
| YES | 8/12 | 3 rejections, 1 wrongly read as NO |
| NO | 3/12 | **6 tracking failures**, 2 wrongly read as YES |
| FINISH | 2/12 | **4 tracking failures**, 5 rejections, 1 read as HELLO |

Decomposed over the 72 clips:

- **15 clips (21%) never produce a usable sequence** — hand tracking fails before the
  classifier runs. Concentrated in the fastest signs: NO 6/12, FINISH 4/12, HELLO 3/12.
- **15 clips (21%) are rejected** by the classifier (score below cutoff or insufficient vote).
- **4 clips (5%) are read as the wrong sign** — NO↔YES twice, FINISH→HELLO once.

Accuracy on trackable clips only: 38/57 correct (67%), with 90.5% accuracy among accepted.

## What was tried, and why it did not improve

**Rejection parameters.** Full grid search on the validation split only
(`maxDistance` × `minRatio` × `minVotes` × `strongRatio`), requiring zero wrong and zero
false accepts on the validation DRINK negatives. The only operating point that satisfies
both is stricter than shipped (`maxDistance` 0.5), and it is worse on the held-out test
split:

| Parameters | test correct | test wrong | test rejected | DRINK false accepts | accuracy |
|---|---|---|---|---|---|
| shipped (0.65) | 38 | 4 | 15 | 6/11 | 66.8% |
| validation-optimal (0.5) | 33 | 2 | 22 | 2/11 | 57.9% |

The shipped parameters are already the best trade-off in this family. Lowering the cutoff
would recover rejections but trade them for false accepts.

**Prototype count.** The model ships all 116 prototypes that the training split can produce
(one per usable training clip: PLEASE 23, YES 23, NO 20, FINISH 20, HELLO 16, THANK YOU 14).
There is no unused training data to add.

## What would actually raise accuracy

1. **Hand tracking for fast signs** — 21% of failures are tracking failures, and NO and
   FINISH account for 10 of the 15. The current pipeline samples 30 frames uniformly and
   needs at least 12 frames with a detected hand, filling gaps of at most 2 frames. More
   samples, larger gap tolerance, or a different hand-detector setting would recover clips
   no classifier change can reach.
2. **More signer-diverse training data** — the classifier itself is at its data limit.
3. **The neural temporal candidate** (seed 29, width 32, epoch 80) was held back because
   automatic replay increased unsupported-action false suggestions from 1 to 2
   (`reports/accuracy-v4/decision.json`). It is the only architecture already on disk that
   beat the baseline on fresh whole clips, so fixing its false-accept behaviour is the
   highest-value direction.

No model file was changed by this diagnosis.
