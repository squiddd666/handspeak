# Joint 50-word temporal experiment

**withheld; not deployed.** Reloading the checkpoint reproduced validation.

The candidate recognized **52/210 target clips correctly**, made **6 wrong-word suggestions**, and missed **152**. It falsely accepted **6/90** other-sign clips.

Training used 1086 usable clips from 1203 training recordings. Validation included 300 recordings. Training and validation signer IDs and recording hashes were checked for overlap. No reserved test clips were opened.

The frozen screen requires at least 50% correct, no wrong or other-sign suggestions, and at least one correct example for every target word. Passing validation alone would still require independent signer tests and automatic-camera testing.

| Word | Correct | Validation clips |
| --- | ---: | ---: |
| AIRPLANE | 3 | 4 |
| BECAUSE | 1 | 4 |
| BED | 1 | 4 |
| BOOK | 0 | 6 |
| BOY | 0 | 4 |
| BROTHER | 0 | 4 |
| CALL | 2 | 4 |
| CAN | 0 | 4 |
| CAR | 1 | 4 |
| CHAIR | 0 | 4 |
| CHILD | 0 | 4 |
| FIND | 2 | 4 |
| FINE | 0 | 4 |
| FINISH | 1 | 14 |
| FISH | 2 | 4 |
| GIRL | 0 | 4 |
| GIVE | 0 | 4 |
| GRANDFATHER | 1 | 4 |
| GRANDMOTHER | 0 | 4 |
| HAVE | 4 | 4 |
| HEAR | 2 | 4 |
| HOME | 0 | 4 |
| HOT | 1 | 4 |
| HUNGRY | 2 | 4 |
| LATER | 2 | 4 |
| LIKE | 1 | 4 |
| LISTEN | 1 | 4 |
| LOOK | 0 | 4 |
| MAN | 0 | 4 |
| MILK | 1 | 4 |
| MORNING | 1 | 4 |
| NIGHT | 1 | 4 |
| NOW | 1 | 4 |
| PAIN | 1 | 4 |
| PEN | 1 | 4 |
| PENCIL | 1 | 4 |
| READ | 1 | 4 |
| RIDE | 0 | 4 |
| ROOM | 0 | 4 |
| SEE | 2 | 4 |
| SHOES | 0 | 4 |
| SHOWER | 0 | 2 |
| SICK | 4 | 4 |
| SPEAK | 0 | 4 |
| STAY | 1 | 4 |
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
