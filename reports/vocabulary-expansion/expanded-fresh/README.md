# Expanded-data subset: fresh evaluation

**Completed and failed; not deployed.** The full 50-word candidate failed development validation:
108/210 correct, one wrong, 101 missed, one false accept among 90 other-sign clips.
Six labels had no correct accepted example.

A smaller 17-label subset was chosen using the same declared development-only
rule as the earlier attempt: at least 75% correct per word and no incoming false
suggestions. It is not a passing 50-word model. Model, thresholds, labels and
implementations were frozen before the new test recordings were selected.

The test evaluated 68 supported clips and 80 other-sign clips (148 total),
excluding prior filenames/content hashes and development signers. At most two
clips per recording signer are selected. The older 26-label fresh test was not
reused or rescored as an independent test.

The parallel ordinary-action check found zero suggestions on 12 whole recordings,
with usable tracking on nine clips and coverage of all four action types. Its
limited screen does not replace automatic-camera-path or integration/regression
checks. No release is permitted solely from these preliminary findings.

Status: `/opt/handspeak-training/vocabulary-expansion-expanded-fresh/job-status.json`

Service: `handspeak-expanded-fresh.service`.

Final result: 35/68 correct, zero wrong, 33 missed and zero false accepts among
80 other signs. RIDE was missed in all four clips, failing the per-word gate.
Results were subsequently used for development selection of the 11-word trial;
they cannot be reused as its independent confirmation.
