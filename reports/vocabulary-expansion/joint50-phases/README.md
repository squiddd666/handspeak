# Joint 50-word temporal experiment

**withheld; not deployed.** Reloading the checkpoint reproduced validation.

The candidate recognized **9/210 target clips correctly**, made **3 wrong-word suggestions**, and missed **198**. It falsely accepted **5/90** other-sign clips.

Training used 1037 usable clips from 1203 training recordings. Validation included 300 recordings. Training and validation signer IDs and recording hashes were checked for overlap. No reserved test clips were opened.

The frozen screen requires at least 50% correct, no wrong or other-sign suggestions, and at least one correct example for every target word. Passing validation alone would still require independent signer tests and automatic-camera testing.

| Word | Correct | Validation clips |
| --- | ---: | ---: |
| AIRPLANE | 0 | 4 |
| BECAUSE | 0 | 4 |
| BED | 0 | 4 |
| BOOK | 0 | 6 |
| BOY | 0 | 4 |
| BROTHER | 0 | 4 |
| CALL | 1 | 4 |
| CAN | 1 | 4 |
| CAR | 0 | 4 |
| CHAIR | 0 | 4 |
| CHILD | 0 | 4 |
| FIND | 0 | 4 |
| FINE | 0 | 4 |
| FINISH | 0 | 14 |
| FISH | 0 | 4 |
| GIRL | 1 | 4 |
| GIVE | 0 | 4 |
| GRANDFATHER | 0 | 4 |
| GRANDMOTHER | 0 | 4 |
| HAVE | 0 | 4 |
| HEAR | 0 | 4 |
| HOME | 1 | 4 |
| HOT | 0 | 4 |
| HUNGRY | 0 | 4 |
| LATER | 0 | 4 |
| LIKE | 0 | 4 |
| LISTEN | 0 | 4 |
| LOOK | 0 | 4 |
| MAN | 0 | 4 |
| MILK | 0 | 4 |
| MORNING | 0 | 4 |
| NIGHT | 0 | 4 |
| NOW | 0 | 4 |
| PAIN | 0 | 4 |
| PEN | 0 | 4 |
| PENCIL | 0 | 4 |
| READ | 1 | 4 |
| RIDE | 0 | 4 |
| ROOM | 0 | 4 |
| SEE | 0 | 4 |
| SHOES | 0 | 4 |
| SHOWER | 0 | 2 |
| SICK | 0 | 4 |
| SPEAK | 0 | 4 |
| STAY | 0 | 4 |
| STORE | 0 | 4 |
| TABLE | 3 | 4 |
| THIRSTY | 1 | 4 |
| TOMORROW | 0 | 4 |
| YESTERDAY | 0 | 4 |

## Limits

- Previously inspected development validation; not independent accuracy.
- Whole clips only; no automatic capture or browser timing test.
- No ordinary hand-movement negatives.
- Source caches use different frame sampling; body-reference modes and frame counts are recorded in the companion JSON.
- Existing signs outside this catalog are negatives for this candidate. It cannot replace the current recognizers without separate integration/regression tests.
- Softmax thresholds are model-selection parameters, not calibrated confidence.

Source: PopSign ASL v1.0, Georgia Tech and DPAN, CC BY 4.0. Private recordings and checkpoints remain outside the served website.
