# Joint 50-word temporal experiment

**withheld; not deployed.** Reloading the checkpoint reproduced validation.

The candidate recognized **76/210 target clips correctly**, made **3 wrong-word suggestions**, and missed **131**. It falsely accepted **1/90** other-sign clips.

Training used 2214 usable clips from 2515 training recordings. Validation included 300 recordings. Training and validation signer IDs and recording hashes were checked for overlap. No reserved test clips were opened.

The frozen screen requires at least 50% correct, no wrong or other-sign suggestions, and at least one correct example for every target word. Passing validation alone would still require independent signer tests and automatic-camera testing.

| Word | Correct | Validation clips |
| --- | ---: | ---: |
| AIRPLANE | 4 | 4 |
| BECAUSE | 3 | 4 |
| BED | 1 | 4 |
| BOOK | 1 | 6 |
| BOY | 1 | 4 |
| BROTHER | 1 | 4 |
| CALL | 2 | 4 |
| CAN | 4 | 4 |
| CAR | 0 | 4 |
| CHAIR | 0 | 4 |
| CHILD | 2 | 4 |
| FIND | 3 | 4 |
| FINE | 0 | 4 |
| FINISH | 3 | 14 |
| FISH | 2 | 4 |
| GIRL | 0 | 4 |
| GIVE | 0 | 4 |
| GRANDFATHER | 2 | 4 |
| GRANDMOTHER | 0 | 4 |
| HAVE | 2 | 4 |
| HEAR | 0 | 4 |
| HOME | 3 | 4 |
| HOT | 3 | 4 |
| HUNGRY | 2 | 4 |
| LATER | 2 | 4 |
| LIKE | 0 | 4 |
| LISTEN | 2 | 4 |
| LOOK | 0 | 4 |
| MAN | 0 | 4 |
| MILK | 3 | 4 |
| MORNING | 1 | 4 |
| NIGHT | 2 | 4 |
| NOW | 1 | 4 |
| PAIN | 2 | 4 |
| PEN | 2 | 4 |
| PENCIL | 3 | 4 |
| READ | 1 | 4 |
| RIDE | 0 | 4 |
| ROOM | 0 | 4 |
| SEE | 2 | 4 |
| SHOES | 1 | 4 |
| SHOWER | 0 | 2 |
| SICK | 2 | 4 |
| SPEAK | 0 | 4 |
| STAY | 3 | 4 |
| STORE | 1 | 4 |
| TABLE | 2 | 4 |
| THIRSTY | 3 | 4 |
| TOMORROW | 1 | 4 |
| YESTERDAY | 3 | 4 |

## Limits

- Previously inspected development validation; not independent accuracy.
- Whole clips only; no automatic capture or browser timing test.
- No ordinary hand-movement negatives.
- Source caches use different frame sampling; body-reference modes and frame counts are recorded in the companion JSON.
- Existing signs outside this catalog are negatives for this candidate. It cannot replace the current recognizers without separate integration/regression tests.
- Softmax thresholds are model-selection parameters, not calibrated confidence.

Source: PopSign ASL v1.0, Georgia Tech and DPAN, CC BY 4.0. Private recordings and checkpoints remain outside the served website.

## Comparison with the combined-negative baseline

The same development recordings were used. Keeping seven other-sign labels as separate internal rejection classes reduced false accepts from 8/90 to 1/90 and wrong target-word suggestions from five to three, but correct target recognition fell from 94/210 to 76/210. Per-class loss balancing also changes when rejection labels are separated. The release criteria were unchanged.

Checkpoint reload and [offline Chromium parity](browser-parity.json) passed. [Mirror averaging/agreement](mirror-diagnostic.json) at unchanged thresholds performed worse and was not adopted. None of these results establish independent or live-camera accuracy.
