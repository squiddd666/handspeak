# Expanded hands-only model with ordinary-movement rejection

This experiment completed and failed validation; it is not deployed. It starts from the frozen 11-word
candidate's full 58-class checkpoint and changes the supported target set to the
existing 50 development labels. It preserves all eight rejection classes,
including ordinary movements, and maps output-head parameters by label rather
than assuming the old class order.

Training uses the existing signer-separated development partitions only: the
ASL data plus 48 ordinary-action training clips and 12 ordinary validation clips.
Body references remain null. Ordinary recording groups are not verified people.
No recorded test outcomes are used for model or threshold selection.

Forty fine-tuning epochs are scheduled; development checks occur at epochs 10,
20 and 40. Seed 83, learning rate 0.0002, label smoothing 0.05, masked geometric
augmentation, and the parent's training normalization are frozen in the private
experiment protocol. The acceptance gate is unchanged: at least half the target
clips correct, zero wrong-word and negative accepts, and coverage of every target.
Passing development screening alone is insufficient for deployment.

Service: `handspeak-expanded-rejection-20261004.service`.
Private log: `/opt/handspeak-training/vocabulary-expansion-expanded-rejection/train.log`.
`job-status.json` and `validation.json` record progress/results when written.

Selected epoch 40: 115/210 target clips correct, three wrong words, 92 misses,
and 0/102 other-sign/ordinary false suggestions. GRANDFATHER and SHOWER had
no correct validation examples. Checkpoint reload passed. The three wrong
suggestions were MAN → FINE, LOOK → CHAIR and YESTERDAY → NIGHT. These are
development results, not independent accuracy. No acceptance rule was relaxed.
