# Joint 50-word temporal experiment

**withheld; not deployed.** Reloading the checkpoint reproduced validation.

The candidate recognized **94/210 target clips correctly**, made **5 wrong-word suggestions**, and missed **111**. It falsely accepted **8/90** other-sign clips.

Training used 2214 usable clips from 2515 training recordings. Validation included 300 recordings. Training and validation signer IDs and recording hashes were checked for overlap. No reserved test clips were opened.

The frozen screen requires at least 50% correct, no wrong or other-sign suggestions, and at least one correct example for every target word. Passing validation alone would still require independent signer tests and automatic-camera testing.

| Word | Correct | Validation clips |
| --- | ---: | ---: |
| AIRPLANE | 4 | 4 |
| BECAUSE | 3 | 4 |
| BED | 0 | 4 |
| BOOK | 2 | 6 |
| BOY | 3 | 4 |
| BROTHER | 2 | 4 |
| CALL | 4 | 4 |
| CAN | 3 | 4 |
| CAR | 0 | 4 |
| CHAIR | 1 | 4 |
| CHILD | 2 | 4 |
| FIND | 2 | 4 |
| FINE | 0 | 4 |
| FINISH | 0 | 14 |
| FISH | 2 | 4 |
| GIRL | 3 | 4 |
| GIVE | 1 | 4 |
| GRANDFATHER | 0 | 4 |
| GRANDMOTHER | 0 | 4 |
| HAVE | 3 | 4 |
| HEAR | 1 | 4 |
| HOME | 3 | 4 |
| HOT | 0 | 4 |
| HUNGRY | 4 | 4 |
| LATER | 2 | 4 |
| LIKE | 1 | 4 |
| LISTEN | 2 | 4 |
| LOOK | 1 | 4 |
| MAN | 0 | 4 |
| MILK | 3 | 4 |
| MORNING | 3 | 4 |
| NIGHT | 3 | 4 |
| NOW | 0 | 4 |
| PAIN | 3 | 4 |
| PEN | 3 | 4 |
| PENCIL | 4 | 4 |
| READ | 2 | 4 |
| RIDE | 0 | 4 |
| ROOM | 0 | 4 |
| SEE | 3 | 4 |
| SHOES | 2 | 4 |
| SHOWER | 0 | 2 |
| SICK | 3 | 4 |
| SPEAK | 0 | 4 |
| STAY | 3 | 4 |
| STORE | 1 | 4 |
| TABLE | 3 | 4 |
| THIRSTY | 4 | 4 |
| TOMORROW | 2 | 4 |
| YESTERDAY | 3 | 4 |

## Limits

- Previously inspected development validation; not independent accuracy.
- Whole clips only; no automatic capture or browser timing test.
- No ordinary hand-movement negatives.
- Source caches use different frame sampling; body-reference modes and frame counts are recorded in the companion JSON.
- Existing signs outside this catalog are negatives for this candidate. It cannot replace the current recognizers without separate integration/regression tests.
- Softmax thresholds are model-selection parameters, not calibrated confidence.

Source: PopSign ASL v1.0, Georgia Tech and DPAN, CC BY 4.0. Private recordings and checkpoints remain outside the served website.
