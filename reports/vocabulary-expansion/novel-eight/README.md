# Eight new-word candidate: ordinary-action release screen failed

Candidate labels: CALL, FIND, FISH, MORNING, NIGHT, PAIN, SEE, SICK.

The 11-word window-trained model failed known ordinary-movement regression with
HOME suggestions. This candidate excludes HOME, HAVE and HUNGRY, which are already
available in the main site's experimental vocabulary, and tests the eight new
labels only. **This selection occurred after viewing prior failures.** Those
recordings cannot establish independent release accuracy for this candidate.

All 63 original output classes continue to compete. A winning excluded class is
rejected without fallback or renormalization. Weights and cutoffs are unchanged.
The model and target list were frozen before selecting the new evaluation media.

Development results: 25/32, 26/32 and 25/32 correct across the three framing scales,
zero wrong words and 0/323 negative accepts in each condition; every label covered.
These are repeated development examples, not independent accuracy.

Sign-test acquisition was stopped after the ordinary-action failure, before any
new sign video was downloaded or scored. Those clips remain unused. The frozen
sign evaluation plan excludes all
development signer IDs. It uses an existing held-out signer pool, not newly
recruited people. `job-status.json` records the stop; there is no sign-test accuracy result.

The ordinary screen uses 24 newly selected recordings: four existing actions in
group 25 (clips 1–3) and lipstick/head-massage groups 19–24 (clip 1). All 24 were
reviewed at two positions before scoring. It checks both full clips and fixed
three-second windows, with zero suggestions and usable coverage per action
required. Recording groups are not verified unique people. Results are in
`ordinary-results.json`: one false MORNING on a head-massage subwindow among
94 correlated full-clip/window examples from 24 recordings. Every action had
usable window coverage. This fails the unchanged zero-false-suggestion gate.
Source selection and review stay private.

Services: `handspeak-novel-eight-evaluation-20261005.service` and
`handspeak-novel-eight-ordinary-20261005.service`. Both jobs have stopped. No deployment.
Even a recording pass requires browser parity, camera timing and integration tests.
