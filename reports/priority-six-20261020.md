# Priority six motion-word experiment

Target words: HELLO, DRINK, BOOK, HUNGRY, HOME, and FISH.

The experiment trained a joint compact temporal model and six isolated temporal
models from signer-separated development data. Models use four ordered temporal
bins and include other signs and ordinary movements as rejection examples.

## Development results

| Word | Correct | Supported total | Negative false accepts | Negative total | Gate |
| --- | ---: | ---: | ---: | ---: | --- |
| HELLO | 9 | 14 | 1 | 124 | Failed |
| DRINK | 8 | 14 | 0 | 124 | Passed |
| BOOK | 1 | 6 | 1 | 124 | Failed |
| HUNGRY | 1 | 4 | 0 | 124 | Failed |
| HOME | 3 | 4 | 0 | 124 | Passed |
| FISH | 4 | 4 | 0 | 124 | Passed |

The joint model failed with 8/46 correct and 2/309 negative false accepts.

## Frozen recorded-clip check

The three development-pass candidates were checked without retuning on 136
previously reserved recordings from the existing held-out signer pool.

| Word | Correct | Supported total | Negative false accepts | Negative total | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| DRINK | 1 | 2 | 15 | 134 | Reject |
| HOME | 2 | 4 | 0 | 132 | Reject: no measured improvement |
| FISH | 0 | 4 | 0 | 132 | Reject |

No candidate was deployed. These clips are recorded-sign regression checks, not
new-person or real-time webcam accuracy. The next useful data collection should
add more signer-separated validation examples for BOOK, HUNGRY, HOME, and FISH,
plus visually similar negative movements for HELLO and DRINK.

## Follow-up model search

Isolated DTW candidates were trained for all six words. Only HOME and FISH
passed development validation. Both scored 3/4 correct with zero false accepts
on the frozen clips. This ties the recorded result already published for FISH.
The current HOME server recognizer also scored 3/4 on the same HOME clips, so
neither candidate demonstrates an accuracy improvement.

Confusion-aware temporal candidates were then trained for BOOK/THANK YOU and
HUNGRY/LIKE, with each negative sign retained as a separate rejection class.
They passed development validation but failed the frozen check:

| Candidate | Development | Frozen supported | Frozen negative false accepts |
| --- | --- | --- | ---: |
| BOOK / THANK YOU | 15/20, 0 false accepts | 0/4 | 6/132 |
| HUNGRY / LIKE | 5/8, 0 false accepts | 0/6 | 2/130 |

HELLO with separate rejection classes and DRINK/WATER also failed development
validation. These results show a train-to-frozen distribution gap. Further
threshold tuning on the frozen clips would contaminate the release test, so it
was not performed. None of these follow-up candidates was deployed.

## Additional signer-source pass

Direct WLASL training-split sources were downloaded outside the website. Legacy
SWF and YouTube entries were skipped. Seventeen videos downloaded and 12 produced
usable landmark sequences: BOOK 4, DRINK 2, FISH 2, HELLO 1, HOME 1, and HUNGRY
2. Existing validation and frozen test recordings were unchanged.

Adding these recordings did not produce a release candidate. HUNGRY DTW improved
to 3/4 on development with zero development false accepts, but recognized 0/4
on the frozen clips and falsely accepted 1/132 negatives. BOOK, HELLO, and DRINK
still failed development validation. The additional data therefore remains a
research artifact outside the served website.

## ASL Citizen additional-signer pass

The official ASL Citizen archive was accessed with HTTP byte ranges, avoiding a
43 GiB full download. Ninety-nine train-partition clips were downloaded, at most
one clip per source gloss and participant. Ninety-four produced usable landmark
sequences: BOOK 15, DRINK1 14, DRINK2 12, FISH 14, HELLO 14, HOME 11, and
HUNGRY 14. Videos and derived features remain outside the served website.

A full-data temporal experiment passed development screening for HELLO (7/14),
DRINK (10/14), HUNGRY (4/4), HOME (2/4), and FISH (4/4), all with zero
development false accepts. Regression on 225 usable previously frozen clips
rejected every candidate: HELLO 0/5; DRINK 4/4 with 17/221 false accepts;
HUNGRY 0/4; and FISH 1/4 with 4/221 false accepts. HOME did not improve the
existing development result.

A second experiment limited the new source to six examples per word, with three
examples from each DRINK variant. DRINK, BOOK, HUNGRY, HOME, and FISH passed the
development screen, but all failed the same fixed regression check:

| Word | Regression correct | Supported total | Negative false accepts | Negative total |
| --- | ---: | ---: | ---: | ---: |
| DRINK | 3 | 4 | 6 | 221 |
| BOOK | 4 | 7 | 2 | 218 |
| HUNGRY | 0 | 4 | 2 | 221 |
| HOME | 1 | 4 | 10 | 221 |
| FISH | 0 | 4 | 2 | 221 |

The result confirms a source/camera distribution gap rather than a shortage of
raw clip count alone. None of these checkpoints was deployed, and no thresholds
were changed after regression outcomes were observed.

## Binary camera-domain follow-up

Compact per-word binary temporal classifiers were trained to decide one word
versus rejection directly. Mixed ASL Citizen/PopSign candidates still failed the
frozen regression check. A second run used only the original PopSign development
source to remove cross-dataset shift.

HELLO passed both fixed gates: 9/14 correct with zero false accepts among 341
development negatives, followed by 3/5 correct with zero false accepts among 220
previously frozen regression negatives. With upper-body pose removed to match
the production hand-only camera path, the regression result remained 3/5 and
zero false accepts.

The exported JavaScript classifier reproduced all 225 Python regression
decisions in headless Chromium. Maximum score difference was 0.000000254 and
mean classifier time was 8.45 ms per captured word, excluding hand detection.
All 92 application tests passed. HELLO was deployed on 21 October 2026 as a
fallback after the existing recognizer returns no match. The existing recognizer
retains priority.

DRINK and BOOK failed development screening. HUNGRY, HOME, and FISH passed
development but failed regression, so their replacements were not deployed.
