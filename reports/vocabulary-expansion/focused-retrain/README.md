# Focused 11-word retraining

The first completed seed (17, epoch 80) passed development validation: 40/44
correct, zero wrong, four misses and zero false accepts among 256 other-sign
clips. Every target word had at least one accepted correct example. Threshold
0.65 and margin 0 were selected on development validation using the established
search; release error and coverage requirements were not changed.

That checkpoint was copied and frozen before a new test selection, in
`/opt/handspeak-training/vocabulary-expansion-focused-seed17`. The remaining
research seeds were stopped to free resources for fresh evaluation and the
hands-only experiment. This is not a completed three-seed ensemble. No deployment.

See `../focused-seed17-fresh/job-status.json` for the new evaluation. Its labels
are fixed: CALL, FIND, FISH, HAVE, HOME, HUNGRY, MORNING, NIGHT, PAIN, SEE, SICK.
