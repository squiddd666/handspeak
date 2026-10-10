# Framing robustness experiment

Training completed; the global-cutoff screen failed. No deployment. Parent: the frozen 11-word hands-only candidate,
checkpoint `0890de66b466bf97d915bed825d1b83354d870ba3f29ac3e8a574bd78e488d98`.

The parent passed native development screening (37/44 correct, no wrong words,
0/268 other-sign/ordinary accepts). A synthetic 0.5625× landmark-scale diagnostic
reduced this to 27/44 with four negative accepts; 1.3× gave 36/44 with one negative
accept. These are the same development clips under feature perturbation, not
additional independent samples or freshly detected images.

Fine-tuning uses original, 0.5625× and 1.3× training landmark geometry, mirrored
variants, and the existing ordinary-movement examples. It preserves missing hands
and existing quality decisions. This is geometric augmentation conditional on the
original tracking mask; it does not simulate detector misses, cropped-hand quality
rejection, or live frame timing. Those require separate media/camera tests.

Twenty epochs, seed 97; checkpoints at 5/10/20. One common threshold/margin pair
must pass the unchanged screen separately for each development framing scale.
The native result is reported separately from the repeated-clip stress conditions.
Neither held-out recording outcomes nor test clips are used for selection.

Service: `handspeak-framing-rejection-20261004.service`.
Private log: `/opt/handspeak-training/vocabulary-expansion-framing-rejection/train.log`.

Selected epoch 10: 36/44 original, 36/44 smaller and 35/44 larger signs correct.
No wrong supported words, but one smaller-scale negative was accepted as HAVE.
The next experiment calibrates stricter word-specific cutoffs using development
examples only; see `../framing-calibrated/README.md`.
