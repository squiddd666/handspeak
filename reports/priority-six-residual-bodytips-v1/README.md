# Priority-six body-and-hands temporal experiment

**Decision: do not deploy.** The joint model passed development validation but
failed the fixed recorded-clip regression rejection gate. The binary follow-up
also failed for five of six words, and FISH lacked a body-enabled positive clip
in the frozen regression pool.

## Joint residual model

Development validation: 37/46 correct, zero wrong supported-word predictions,
nine misses, and zero false accepts among 254 other-sign clips. Per word:
HELLO 11/14, DRINK 12/14, BOOK 3/6, HUNGRY 4/4, HOME 3/4, FISH 4/4.

The frozen regression used 234 usable recordings pooled from three existing,
previously inspected test caches. It produced 25/32 correct target decisions but
15 false accepts among 202 negatives, so it failed the unchanged release gate.

## Independent-word residual model

Six sigmoid outputs and six development-selected thresholds were trained from the
same development source. Every word met the development requirement of at least
50% recall and zero negative accepts. Frozen regression results:

| Word | Correct | Target clips | False accepts | Negative clips | Gate |
| --- | ---: | ---: | ---: | ---: | --- |
| HELLO | 9 | 13 | 0 | 221 | Pass |
| DRINK | 2 | 4 | 1 | 230 | Fail |
| BOOK | 3 | 6 | 34 | 228 | Fail |
| HUNGRY | 1 | 1 | 4 | 233 | Fail |
| HOME | 7 | 8 | 2 | 226 | Fail |
| FISH | 0 | 0 | 0 | 234 | Not testable |

HELLO is not promoted from this experiment. The current browser path does not
produce the per-frame upper-body pose required by this candidate, and deploying
that dependency without camera timing, Android, browser-parity, and negative
movement checks would bypass the release process. The existing hand-only HELLO
fallback remains active.

## Architecture tested

The experiment implements the reusable ideas identified in the external source
review without copying third-party model weights: upper-body-relative fingertip
coordinates, hand/body scale, explicit frame differences, residual dilated
temporal convolutions, mean/max pooling, monotone time-warp augmentation, and
signer-separated development partitions. Raw videos and private checkpoints stay
outside the website.

The regression recordings were inspected by earlier experiments, so these results
are a fixed compatibility screen rather than a new independent accuracy estimate.
No thresholds were changed after regression results were opened.
