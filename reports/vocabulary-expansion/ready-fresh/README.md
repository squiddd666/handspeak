# Frozen shortlist: fresh-recording evaluation

**Completed; failed; not deployed.** Fresh results: 77/104 correct, five wrong
word suggestions, 22 misses and one false accept among 62 other-sign clips.
PEN had no correct examples. See `test-results.json`.

No labels were removed or thresholds changed after inspecting these results
to manufacture a passing result. These recordings are now consumed research
test data and must not be presented as untouched tests for future candidates.

Development history: The 26-label subset scored 90/104
correct, zero wrong suggestions and zero false accepts on 196 other-word clips
in reused development validation. Those figures were used to select the subset;
they are not independent accuracy.

The checkpoint, original 57 output classes, 26 accepted labels, thresholds and
feature/extraction implementation are frozen before test media access. Excluded
winning labels are rejected without renormalizing or falling back to another
label. Fresh selections exclude prior filenames/content hashes and development
signers. All 31 non-target classes remain in the fresh negative check.

The recorded-video plan requests four clips per accepted label and two per other
label, with at most two recordings per signer. A metadata-only first attempt
requested distinct people for each clip; it was stopped before any video payload
was opened because the SHOWER test archive contains only one signer. V2 records
this sampling correction before accessing media, preserving the same model and
thresholds. No test result was used to change sampling.

The planned total is 166 recordings. The existing held-out population may have
appeared in earlier research; this is fresh-recording evidence, not a claim of
newly recruited signers. Missing tracking counts as a miss. The unchanged
accuracy gate applies. No thresholds will be tuned from these outcomes, and no
post-test label pruning will be reported as an independent pass.

Even a recorded-clip pass still requires ordinary-movement rejection tests and
real-time camera-path integration/regression checks before release. Playback
through a virtual camera is not physical-webcam validation.

Status: `/opt/handspeak-training/vocabulary-expansion-ready-fresh-v2/job-status.json`

Service: `handspeak-ready-fresh-v2.service`. The separate
`handspeak-priority-training.service` finished without passing.
`handspeak-priority-data-v2.service` is gathering more training recordings and
will re-extract features, retrain and verify the new candidate.
Neither service deploys a model.

The extraction output directory had to be created during the run before any
scores were computed. The current runner now creates it explicitly. The exact
runner used for this completed experiment remains in its private source snapshot;
its frozen implementation hash intentionally differs from the corrected runner.
Use a new experiment directory for future tests, not this consumed test set.
