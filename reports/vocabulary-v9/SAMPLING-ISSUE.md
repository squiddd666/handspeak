# Sampling issue found during the final audit

The first recovery worker was started with `fps=60/duration`. That can duplicate source frames when a video contains fewer than 60 frames. The development audit found 91 such short clips among the 226 retries. A source edit made while that worker was running did not change the already loaded function. Consequently, the initial claim of 150 recovered sequences is an archived pipeline count, not a count of independently recovered motion information.

The v8/v9 candidates were already withheld because they failed the improvement gates. This sampling flaw provides a further reason not to use those trials as accuracy-improvement evidence. Their model files, hashes, and reports remain archived rather than being silently overwritten.

The extraction helpers now re-encode with temporal passthrough, preserving original timing and frame count, and choose at most 30 or 60 distinct frame indices. Short-clip retries were repaired in a separate `dense-corrected` cache. Corrected development features are saved separately as `corrected-development-features.json`; they must not be confused with the data used by the archived models. No model trained on the corrected dataset has been promoted.

The initial 30-frame preprocessing is also audited for source clips shorter than 30 frames. Any such cases are recorded in the source-frame audit; the initial category models remain withheld. The original deployed six-word, prior extra-word, and static-letter models were not generated or changed by these new preprocessing experiments.


Correction completed: 91 development retries were rebuilt, and the corrected data contains 702 usable sequences, a gain of **149**, rather than the initially reported 150. The 30-frame audit found one two-frame RIDE training source; it produced no usable sequence and was excluded from model references. No test source had fewer than 30 frames. The corrected dataset has not been used to claim or deploy a high-accuracy model.
