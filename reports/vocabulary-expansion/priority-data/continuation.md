# Training-data continuation

The 24-label weighting-only experiment and the 26-label fresh-recording test both
failed their gates. No candidate has been deployed.

The source search selected 220 additional official training recordings (about
1.3 GB), capped at two clips per signer, seeking up to 72 clips for each of the
24 weaker labels. Available counts differ by label. CAR, FISH, GIVE, ROOM,
SHOWER and YESTERDAY yielded no further recordings under those limits.

Raw downloads stay private. The job excludes validation signers and separately
checks the frozen fresh-test identity manifest, without reading test predictions
or features. Existing validation rows are kept unchanged. New hand/body features
use the same 60-frame extractor and window alignment. The full 50-label model
was trained using corrected augmentation and its original class weighting.
This tests additional data, not a weaker release criterion.

The first one-worker extraction was superseded before training by a new frozen
run with three workers. Downloaded videos are reused; feature extraction is
repeated under the new run's provenance. The old snapshots/status remain archived.

Current service: `handspeak-priority-data-v2.service`.

Current private status:
`/opt/handspeak-training/vocabulary-expansion-priority-data-v2/job-status.json`.

The run automatically extracts, trains, verifies checkpoint reload and checks
browser parity. It never deploys. New independent recorded-video evaluation,
ordinary-movement negatives and camera-path regression remain release requirements.
Completed: 108/210 correct, one wrong word, 101 misses and one false accept
among 90 other signs. The gate failed. Checkpoint reload and browser parity
passed; neither demonstrates release accuracy.
