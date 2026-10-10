# Hands-only candidate with ordinary-movement rejection

**Recorded checks passed; main recognizer not replaced.** Checkpoint:
`0890de66b466bf97d915bed825d1b83354d870ba3f29ac3e8a574bd78e488d98`.

Training added 48 ordinary-action training clips (35 usable), with 12 separate
validation clips (eight usable). The source ASL development rows remained unchanged.
All body references were removed for this model so it can use the existing hand
detector. Fine-tuning retained other-sign classes and added an ordinary-movement
rejection class; excluded winning classes never fall back to a supported word.

Development selection: 37/44 correct, zero wrong and 0/268 other-sign/ordinary
false suggestions. The serialized checkpoint reproduced that result.

Reserved recorded-sign comparison: 34/44 correct, zero wrong, ten misses,
0/92 other-sign false suggestions. CALL 3/4, FIND 3/4, FISH 2/4, HAVE 2/4,
HOME 3/4, HUNGRY 4/4, MORNING 4/4, NIGHT 3/4, PAIN 3/4, SEE 4/4, SICK 3/4.
These clips were shared with the previously frozen body and hands-only candidates.
Their outcomes were not read until the ordinary-rejection candidate was selected
using development validation and frozen. This is not a new unused test set for
every candidate. All recorded comparisons now count as consumed evaluation data.

A further ordinary-action test selected groups 19–21 after model freeze,
excluding development groups 4–18 and earlier evaluation groups 1–3. It produced
0/12 false suggestions with eight usable tracked clips and coverage of all four
actions. All 12 clips were reviewed at three timestamps before inference.
These are recording groups, not verified distinct people; the small test cannot
establish general everyday-movement rejection.

Python/Chromium classifier parity passed on 77 examples with median/p95 inference
52.4/59.5 ms. These measurements exclude camera detection. Software-rendered
server camera tests failed to capture short signs reliably. Physical-camera and
OBS checks on the user's normal browser are still required before main rollout.

A standalone [camera-test page](https://handspeak.cvsu.dev/motion-preview-20261004/index.html)
is live; source files are under `motion-preview/`. It performs
recognition locally, labels every output as a possible match, and does not add
words to sentences or trigger speech. Its test log records no video or landmarks.
The expected-word selector affects the test log only, not classification.
