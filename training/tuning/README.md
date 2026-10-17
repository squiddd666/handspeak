# Tuning and re-measurement scripts

Reproducible experiments for the motion-word models. Each writes its outputs beside the
data it reads; nothing here deploys anything.

| Script | Purpose |
|---|---|
| `extract_contiguous.py` | Re-extract the six-word PopSign clips with live-style contiguous frame sampling. Cache: `/opt/handspeak-training/popsign/extracted-contiguous.json`. |
| `evaluate_contiguous.py` | Score the shipped six-word model on the contiguous features. |
| `publish_contiguous.py` | Write the contiguous-basis recorded results into the model and report JSONs. |
| `calibrate_perword.py` | Per-word distance cutoffs for the six-word model, validation only. |
| `calibrate_rules.py` | Search the vote / separation rules on validation only. |
| `parity_check.py` | Run the deployed JavaScript recognizer over the test clips to verify published numbers. |
| `publish_perword.py` | Write the calibrated six-word model and results. |
| `resample_failures.py` | Re-sample clips that fail tracking, to separate harness artifacts from untrackable signing. |
| `diagnose_six.py` | Break the six-word recorded result into tracking failures, rejections and wrong signs. |
| `tune_six_parameters.py` | Global parameter search on validation only. |
| `daily_extract_contiguous.py` | Contiguous re-extraction of the ASL-Citizen daily-word clips. |
| `daily_calibrate_cutoffs.py` | Per-word cutoffs for the five-word research model; verifies its DTW against `research_words.distance` first. |
| `expanded_download_clips.py` | Fetch the PopSign clips for FOOD / GO / HUNGRY / LIKE from the official archive. |
| `expanded_prepare.py` | Assemble the seven expanded-word clips and measure the current recorded numbers. |
| `expanded_extract_contiguous.py` | Contiguous re-extraction of the expanded seven. |

Every cutoff in this directory was chosen on the validation split only; the held-out test
split was scored once, after calibration.
