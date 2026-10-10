# Hands-only training experiment

**First seed completed; remaining seeds superseded by evaluation.** Uses the same expanded development clips, hand
landmarks, quality decisions, labels and train/validation splits, replacing
all body-reference frames with null. The feature encoders then use their existing
hand-only fallback. No test clips were added to training.

This tests whether the 11-word candidate can work with the website's existing
hand detector, without the extra cost of live body detection. It retains all
other output classes for rejection and uses target loss weight 2. No accuracy
or camera-speed improvement is established yet.

Private source: `/opt/handspeak-training/vocabulary-expansion-hands-only-source`.
Source SHA-256: `d370e3c0f1748218f60598e45d700aba982858423558a01bd4b1bdb1dd1a7ad3`.
The source protocol records the original development dataset hash.

Service: `handspeak-hands-only-retrain.service`.
Private run: `/opt/handspeak-training/vocabulary-expansion-hands-only-retrain`.

The selected epoch-20 checkpoint passed development at 37/44 and recorded signs
at 29/44 with no wrong or other-sign false suggestions. It failed ordinary-action
regression: one makeup clip was suggested as MORNING. This led to the separately
trained ordinary-rejection candidate; this earlier checkpoint is not promoted.
