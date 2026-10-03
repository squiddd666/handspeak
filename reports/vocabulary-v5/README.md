# Extra ASL words — optional preview, 2 October 2026

Added DRINK, WATER, and BOOK with demonstration videos and optional camera recognition. The original six-word model stays the default. Extra words are only considered after the original/personal vocabulary rejects. The preview is enabled explicitly with its checkbox or the Practice at camera button for a new-word video.

## Data and evaluation

Selected 108 training, 36 validation, and 24 fresh test clips for the new words, plus 16 validation and 16 fresh test clips of APPLE/MILK. Participant splits are disjoint. 86 training clips yielded usable templates: DRINK 31, WATER 30, BOOK 25. Candidate thresholds were selected on validation and frozen before reading the new test outputs. Existing-word test recordings are a previously evaluated regression set. Raw videos and feature caches remain outside the served site.

Validation: 7/36 new-word clips correct; existing-word results stayed 47/84 correct and 1 wrong. Combined real/synthetic negative false suggestions rose 22/40 → 27/40. A strict default-promotion candidate made no new correct suggestions, so the useful candidate is opt-in only.

Fresh new-word test: 9/24 correct, 7 wrong, 8 no match. DRINK 3/8, WATER 5/8, BOOK 1/8. Existing-word regression stayed 20/36 correct with no wrong labels. Combined real/synthetic negative false suggestions rose 23/40 → 27/40. Synthetic-timestamp automatic replay also increased false suggestions (8 → 10), so default promotion failed.

Browser integration: all three selected compressed training videos matched with 30 sought detector frames each. Initial WATER example failed, so a better-tracked training example was selected; this check is not an accuracy benchmark. Real-time 480×640 virtual-camera playback through the actual deployed app, CPU hand inference and face tracking off: WATER matched; DRINK and BOOK had no match. No wrong/repeated suggestions or page errors on these three clips. Physical-webcam generalization remains unverified.

## Website checks

Public page: nine videos, new three play successfully; preview disabled initially; new-word Practice shortcut enables preview and selects Words in motion; disabling preview restores original vocabulary. No JavaScript errors or horizontal overflow at 390px. 21 motion tests passed, including preserving original/personal matches and expansion download failure. git diff --check passed.

Full report: ../../models/asl-extra-words-evaluation.json. Source scripts: ../../training/vocabulary/. Original six-word model unchanged. No claim of high accuracy.
