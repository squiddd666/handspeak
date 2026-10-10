# Residual motion experiment

**Not deployed.** Development screen: 135/210 correct, 8 wrong supported-word predictions, 67 misses, 3/90 false accepts on other signs.

Passes unchanged validation gate: False. Checkpoint reload reproduced the result.

Uses the balanced development data and seven separate rejection classes. Adds training-only feature normalization, explicit frame differences, residual dilated convolutions, mean/max pooling, and time-warp augmentation. Multiple changes mean this experiment does not isolate the effect of any one change.

This variant also retains explicit fingertip/body coordinates and hand/body scale.

Previously inspected validation, not independent accuracy. Subsequent offline browser parity passed on 75 cached examples; see browser-parity.json. No ordinary movement negatives, automatic-camera timing, or untouched final test was evaluated here. All release requirements still apply. Raw videos and checkpoints stay outside the website.
