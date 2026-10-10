# Short-window ordinary-movement experiment

Training and whole-clip regression completed. **The 11-word model is not ready.**
It scored 29/44 known signs correctly, zero wrong words and 0/92 other-sign accepts,
but still suggested HOME for one ordinary recording. Testing full clips plus
subwindows produced five HOME suggestions across 49 correlated examples.

The completed jobs were managed by systemd:
`handspeak-windowed-ordinary-training-20261005.service` and
`handspeak-windowed-ordinary-checks-20261005.service`.
See `job-status.json` and `continuation-status.json` for current state.

The previous model compressed long ordinary movements and short signs into the
same 32 feature steps. This experiment adds 3-second ordinary subwindows to the
existing development data. It retains every original example, including the full
ordinary recordings, and preserves all ASL rows and their train/validation split.

There are 313 added windows, including 186 usable training windows and 37
validation windows. Windows share their source recording's identity and partition;
they are correlated examples, not newly collected clips or independent samples.
Frames are selected using real timestamps, never duplicated or invented. Sparse
cached detection and missing hands remain limitations. Sequence-quality checks
are unchanged; unusable validation examples are retained.

Selection is fixed at up to four evenly spaced windows per clip and does not use
model predictions. The same 11 labels, rejection classes, training settings and
acceptance gates are retained. No test recordings enter training or validation.
The script verifies that the original ASL rows are unchanged.

After training, a passing development checkpoint is frozen and checked against
known regression recordings. A regression pass still requires unused recordings,
short-window negatives and browser capture testing before main-site promotion.
Neither service deploys a model automatically.

The adaptive camera pacing experiment reduced queue delay but missed previously
recognized fixtures; it was reverted. Its diagnostic results remain in
`../motion-preview/camera-recordings-adaptive-640.json` and
`../motion-preview/camera-recordings-adaptive-480.json`. They are training-video
camera fixtures, not independent recognition accuracy tests.
