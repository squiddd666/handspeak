# Residual motion experiment

**Not deployed.** Development screen: 145/210 correct, 4 wrong supported-word predictions, 61 misses, 4/90 false accepts on other signs.

Passes unchanged validation gate: False. Checkpoint reload reproduced the result.

Uses the balanced development data and seven separate rejection classes. Adds training-only feature normalization, explicit frame differences, residual dilated convolutions, mean/max pooling, and time-warp augmentation. Multiple changes mean this experiment does not isolate the effect of any one change.

Previously inspected validation, not independent accuracy. No ordinary movement negatives, browser parity, automatic-camera timing, or untouched final test was evaluated here. All release requirements still apply. Raw videos and checkpoints stay outside the website.
