# Recorded tracking failures are a harness artifact (2026-10-17)

Experiment: `training/tuning/resample_failures.py`, run on `15` recorded clips that the
shipped six-word model cannot score because no usable sequence is produced.

## Result

| Sampling | Clips recovered |
|---|---|
| `uniform30` (shipped harness: 30 frames spread across the whole video) | 0 / 15 |
| `contiguous30` (30 consecutive frames around the signing window, as the live app captures) | **11 / 15** |
| `contiguous45` | 11 / 15 |

The four clips that stay unrecoverable show 0-8 frames with any hand at all (THANK YOU,
PLEASE, FINISH, one NO), so they are genuinely untrackable rather than a sampling problem.

Why: MediaPipe's hand landmarker runs in `VIDEO` mode and relies on temporal continuity,
so consecutive frames track far better than frames spread across a clip. The recorded
harness samples uniformly, which lands on motion-blurred and transitional frames and drops
below the pipeline's 70% visibility requirement.

The live app captures contiguous frames, so the recorded evaluation was *pessimistic*
relative to deployment. Clips that a live user would sign through successfully were being
counted as failures.

## Effect on the recorded six-word screen

Default six, 12 clips per word, 72 total. Current recorded result: 38 correct (53%).

| Word | Now | Clips recovered by contiguous sampling | Ceiling if every recovered clip classifies correctly |
|---|---|---|---|
| HELLO | 6/12 (50%) | 3 | 9/12 (75%) |
| THANK YOU | 8/12 (66.7%) | 0 | 8/12 |
| PLEASE | 11/12 (91.7%) | 0 | 11/12 |
| YES | 8/12 (66.7%) | 0 | 8/12 |
| NO | 3/12 (25%) | 4 | 7/12 (58%) |
| FINISH | 2/12 (16.7%) | 3 | 5/12 (42%) |

Ceiling: 48/72 (67%). Whether the recovered clips then classify correctly still has to be
measured — recovery is necessary, not sufficient.

## What a rebuild requires

1. Re-extract train/val/test clips with contiguous sampling (same MediaPipe options).
2. Rebuild the prototype set from the re-extracted training rows; today the model already
   ships every usable training prototype, so the change is in the sequences themselves.
3. Re-tune the rejection parameters on validation only, then evaluate the test split once.
4. Refresh the shipped model and the recorded-accuracy reports, and re-run the browser
   check. The change to the evaluation protocol must be documented, because it makes
   results non-comparable with the previously published numbers.

This is a genuine accuracy improvement for real users as well: the same tracking continuity
is what the live camera pipeline already relies on.
