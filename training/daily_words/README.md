# Daily-word research training

Target words: NAME, HOME, HAVE, WANT and LOVE. ASL Citizen source glosses WANT1 and WANT2 are retained in provenance and pooled as WANT for this experiment.

Use `/opt/handspeak-training/venv/bin/python`. All source videos, signer metadata, landmark features, distance caches, and model checkpoints stay in `/opt/handspeak-training/daily-words/citizen-research`, outside the website and repository. This pipeline is private, noncommercial research; it does not publish a model or change the live recognizer.

1. `prepare_citizen.py` freezes deterministic source selection and downloads only training/validation clips via HTTP byte ranges. It preserves official signer-separated partitions. At most one recording per source gloss per participant is selected. Twenty-four other source labels are predefined negatives, not ordinary non-sign movements.
2. `extract_citizen.py` reuses the existing 30-frame research extractor: unique source frames, actual timestamps, the browser's hand-quality gate, and a center-frame upper-body reference. Failed hand sequences remain misses in validation and testing; they are excluded from fitting.
3. `train_citizen.py --model dtw` fits a sequence-matching baseline. `train_citizen.py --model temporal` trains two compact six-output convolutional networks (five requested words plus unknown), with mirrored training augmentation and validation-only checkpoint/rejection selection. Scores are uncalibrated. Models and hashes are frozen before test download.
4. Only if the temporal candidate passes the predeclared validation gate, run `prepare_citizen.py --test`, `extract_citizen.py --test`, then `evaluate_citizen.py`. The evaluator asserts disjoint source signers and file hashes and verifies frozen model hashes. It does not tune from test results.
5. `test_training.py` tests unknown/untracked rejection, the promotion gate, and output dimensions. The reused representation also has invariance checks in `training/accuracy/test_experiment.py`.

Whole-clip test results do not establish live-camera or automatic-segmentation accuracy. CPU timing reported by the evaluator measures only network inference, excluding feature extraction and camera processing. A test pass alone is not deployment approval: browser integration, real-time evaluation, non-sign negatives, and permission to redistribute any required research material remain separate requirements.

Source: https://www.microsoft.com/en-us/research/project/asl-citizen/
License inspected: the official archive's `ASL_Citizen/use.txt`. Respect its noncommercial research, confidentiality, redistribution, and research-completion deletion terms. `remote_zip.py` downloads only the archive index and named metadata files; the experiment downloader explicitly selects individual recordings.
