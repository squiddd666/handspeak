# Expanded ordinary-action model: not ready for deployment

The frozen model passed development screening but failed known-recording
regression. It recognized 21/44 signs correctly, produced one wrong sign and no
false accepts among 92 other signs. It still produced one false HOME among 12
ordinary-action recordings. Do not deploy this checkpoint.

Training added 78 reviewed clips and separated six ordinary actions into distinct
rejection classes. Validation selected epoch 5 of 20 without using these regression
outcomes. Original ASL training/validation partitions remained unchanged.

See `validation.json`, `regression.json`, and `protocol.json`. Regression recordings
had previously been scored; they are not fresh independent accuracy evidence.
