# Single-word release status — 2026-10-17

Every candidate goes through the same gates: development screens, three known-recording
regression screens, then one fresh recorded-clip test from held-out signers. Nothing is
published unless all of them pass.

## Published (live camera vocabulary)

| Word | Fresh recorded test | Group |
|---|---|---|
| FISH | 3/4 correct, 0/112 false accepts | `single-fish` |
| SICK | 3/4 correct, 0/112 false accepts | `single-sick` |
| PAIN | 4/4 correct, 0/110 false accepts | `single-pain` |
| NIGHT | 4/4 correct, 0/110 false accepts | `single-night` |
| SEE | 3/4 correct, 0/110 false accepts | `single-see` |

PAIN and SEE were re-frozen at a stricter cutoff (0.35 -> 0.75 / 0.85) from the same
checkpoint; NIGHT likewise (0.65 -> 0.75). In each case the development screens were
replayed at the new cutoff before the fresh test, and the original candidate is kept at
`frozen-at<old>/`.

## Not published

| Word | Blocker |
|---|---|
| MORNING | Scores do not separate. The SICK false accept sits at 0.8625 while true MORNING clips sit at 0.836-0.905. Clearing the false accept needs 0.90, which drops fresh recall to 1/4. |
| FIND | Screens conflict. At 0.70 the sign screen is 3/4 but the ordinary screen has 2 false suggestions; at 0.90 the ordinary screens are clean but the sign screen collapses to 1/4. No cutoff satisfies both. |
| CALL | Fresh test was 4/4 correct with 1 false accept in 112. Choosing a cutoff after seeing that result would tune on the holdout itself, so the candidate is left as tested and unpublished. |

## What would actually unblock them

- More development data for the weak labels (MORNING has 66 clips, FIND 36, CALL 52 in the
  current source), which changes the score distributions rather than the cutoffs.
- A different training recipe or seed, evaluated through the same screens.
- Not a lower gate: every blocked word fails for a reason a lower gate would hide.
