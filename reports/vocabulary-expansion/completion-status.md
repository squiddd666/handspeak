# 201-word expansion: current status

**Not complete; no new candidate has been deployed.** The current website models
remain in place. Passing software tests does not demonstrate recognition accuracy.

## Latest continuation: fresh eight-word test

A vocabulary restricted on development validation passed that screen (23/32
correct, no incorrect suggestions on 162 other-sign clips). The unchanged frozen
candidate was then evaluated on 96 fresh recordings: **35/48 target signs correct,
12 missed, one wrong-word suggestion, and one false accept among 48 other signs**.
It failed the predeclared zero-incorrect-suggestions screen and was not deployed.
See the [fresh test report](fresh-test/README.md). Thirteen software tests passed.

The main `all-201-readiness.csv` now incorporates the additional dataset leads:
9 previously enabled experimental entries, 169 entries with candidate sources,
and 23 without a candidate. BAG gained an additional numbered-variant lead
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
169 other entries now have a source lead, and 23 still have no candidate in the
datasets compared. **A source lead is not a verified sign mapping, accessible
training set, or trained recognizer.** Additional clips must be checked for meaning,
availability, permitted use, duplicates, and signer separation. Multi-sign phrases
also need sequence-level annotation and evaluation.

The 23 unresolved entries are GOOD EVENING, YOU'RE WELCOME, DON'T UNDERSTAND,
CHARGER, FEVER, STOMACHACHE, AMBULANCE, PHARMACY, INJURY, CLASSMATE, ASSIGNMENT,
POLICE STATION, MARKET, TAXI, WORRIED, OKAY, DON'T TOUCH, UNSAFE, CALL POLICE,
CALL AMBULANCE, RICE, HOW MUCH, and DON'T HAVE.

Models must still pass an untouched signer test, ordinary hand-movement negatives,
existing-vocabulary regression, and timed automatic-camera/browser tests. No live
camera accuracy or 201-word coverage is demonstrated here.

## Artifacts

- [Expanded-model results](batch2/README.md)
- [Stronger-rejection results](batch2-rejection/README.md)
- [Additional source candidates](additional-source-candidates.md)
- [Preparation and training commands](../../training/catalog/EXPANSION.md)

Sources: [PopSign](https://signdata.cc.gatech.edu/view/datasets/popsign_v1_0/index.html),
[WLASL](https://github.com/dxli94/WLASL), and
[Microsoft MS-ASL](https://microsoft.github.io/data-for-society/dataset?d=MS-ASL-American-Sign-Language-Dataset).
