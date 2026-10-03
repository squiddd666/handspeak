# Joint 50-word temporal experiment

**withheld; not deployed.** Reloading the checkpoint reproduced validation.

The candidate recognized **94/210 target clips correctly**, made **8 wrong-word suggestions**, and missed **108**. It falsely accepted **2/90** other-sign clips.

Training used 2214 usable clips from 2515 training recordings. Validation included 300 recordings. Training and validation signer IDs and recording hashes were checked for overlap. No reserved test clips were opened.

The frozen screen requires at least 50% correct, no wrong or other-sign suggestions, and at least one correct example for every target word. Passing validation alone would still require independent signer tests and automatic-camera testing.

| Word | Correct | Validation clips |
| --- | ---: | ---: |
| AIRPLANE | 4 | 4 |
| BECAUSE | 3 | 4 |
| BED | 2 | 4 |
| BOOK | 3 | 6 |
| BOY | 2 | 4 |
| BROTHER | 2 | 4 |
| CALL | 4 | 4 |
| CAN | 4 | 4 |
| CAR | 0 | 4 |
| CHAIR | 1 | 4 |
| CHILD | 1 | 4 |
| FIND | 3 | 4 |
| FINE | 1 | 4 |
| FINISH | 3 | 14 |
| FISH | 2 | 4 |
| GIRL | 0 | 4 |
| GIVE | 0 | 4 |
| GRANDFATHER | 3 | 4 |
| GRANDMOTHER | 0 | 4 |
| HAVE | 4 | 4 |
| HEAR | 0 | 4 |
| HOME | 2 | 4 |
| HOT | 3 | 4 |
| HUNGRY | 4 | 4 |
| LATER | 2 | 4 |
| LIKE | 2 | 4 |
| LISTEN | 1 | 4 |
| LOOK | 0 | 4 |
| MAN | 2 | 4 |
| MILK | 1 | 4 |
| MORNING | 4 | 4 |
| NIGHT | 3 | 4 |
| NOW | 3 | 4 |
| PAIN | 2 | 4 |
| PEN | 1 | 4 |
| PENCIL | 2 | 4 |
| READ | 1 | 4 |
| RIDE | 0 | 4 |
| ROOM | 0 | 4 |
| SEE | 3 | 4 |
| SHOES | 1 | 4 |
| SHOWER | 0 | 2 |
| SICK | 2 | 4 |
| SPEAK | 1 | 4 |
| STAY | 3 | 4 |
| STORE | 1 | 4 |
| TABLE | 2 | 4 |
| THIRSTY | 3 | 4 |
| TOMORROW | 1 | 4 |
| YESTERDAY | 2 | 4 |

## Limits

- Previously inspected development validation; not independent accuracy.
- Whole clips only; no automatic capture or browser timing test.
- No ordinary hand-movement negatives.
- Source caches use different frame sampling; body-reference modes and frame counts are recorded in the companion JSON.
- Existing signs outside this catalog are negatives for this candidate. It cannot replace the current recognizers without separate integration/regression tests.
- Softmax thresholds are model-selection parameters, not calibrated confidence.

Source: PopSign ASL v1.0, Georgia Tech and DPAN, CC BY 4.0. Private recordings and checkpoints remain outside the served website.
