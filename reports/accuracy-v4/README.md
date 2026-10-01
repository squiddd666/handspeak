# Six-word accuracy experiment — completed

**Decision: keep the current live model.** The temporal candidate improved whole-clip recognition, but failed the requirement that automatic unsupported-sign suggestions must not increase.

## Fresh test results

The candidate and thresholds were selected on validation and frozen before evaluating these new recordings. Training, validation, and test signer IDs are disjoint. These are new recordings from the existing test-signer population, not a new-population benchmark. All selected recordings count, including tracking failures.

| Measure | Live-model baseline | Expanded DTW | Temporal candidate |
|---|---:|---:|---:|
| Correct supported clips / 36 | 20 | 9 | 32 |
| Wrong supported predictions | 0 | 0 | 0 |
| Missed supported clips | 16 | 27 | 4 |
| Unsupported false accepts / 18 | 3 | 0 | 2 |
| Synthetic nuisance false accepts / 24 | 13 | 3 | 0 |

## Per-word correct results

| Word | Baseline / 6 | Temporal / 6 |
|---|---:|---:|
| HELLO | 2 | 6 |
| THANK YOU | 4 | 5 |
| PLEASE | 5 | 6 |
| YES | 3 | 5 |
| NO | 4 | 6 |
| FINISH | 2 | 4 |

## Automatic boundaries

Source-timestamp replay gave the temporal candidate 31/36 correct clips versus 8/36 for the baseline, with zero wrong supported-word suggestions and zero repeats for both. However, unsupported false suggestions rose from **1 to 2**. This fails the agreed promotion gate. This diagnostic replays landmarks using source timestamps; it is not a wall-clock webcam benchmark.

## Real-time browser checks

Normal-speed, camera-sized video replay recognized **4/6** examples with the temporal candidate and **2/6** with the baseline on identical captured hand segments. The candidate missed HELLO and THANK YOU; it produced 0 wrong suggestions and 0 repeats. These are selected training examples, so this is a functional check, not an accuracy benchmark.

The separate deployed-app camera replay produced 2/6 correct suggestions, 1 wrong, and no repeated suggestions. Its capture timing differs from the comparison harness, so the two baseline counts should not be treated as identical-input comparisons.

Temporal classifier latency: median 9.7 ms, p95 133.4 ms across 20 post-warmup runs. This excludes landmark extraction. Center-frame pose detection plus classification took median 169.1 ms and up to 530.5 ms in the streaming harness. Correct suggestions appeared a median 378.9 ms after video playback ended. Measurements are specific to this CPU/headless-browser host, with face tracking disabled.

Python/JavaScript parity passed: maximum feature error 1.1881266326341233e-07 and logit error 3.2201951256638495e-06.

The original high-resolution video replay was decoder-bound and stretched playback. Camera-sized copies were therefore used for the final timing check; their source and derived checksums are recorded in `accuracy-v4/camera-video-provenance.json`. No physical webcam or real nonsigning user footage was available. Synthetic still hands, camera drift, jitter and no-hands tests are not a substitute for that evidence.

## Data and training

Downloaded 198 additional development clips and 54 fresh test clips from [PopSign ASL v1.0](https://signdata.cc.gatech.edu/view/datasets/popsign_v1_0/), licensed CC BY 4.0. Combined development data: 288 training and 110 validation videos, with 31 training signers (previously 30). Usable supported references increased from 116 to 189; 31 usable DRINK/WATER/BOOK references were added for unknown rejection.

The temporal model uses hand shape, wrist movement, and upper-body-relative position, with two temporal convolutions and an UNKNOWN class. Mirroring and small feature noise are training-only augmentations. Validation selected the model and rejection threshold; there was no tuning on the fresh-test outcomes.

Exact reproduction of this run uses the saved, hashed development feature cache. Body references in some cached clips reuse the earlier video-tracked pose estimate; fresh extraction uses a static center-frame pose. Re-extracting all source videos can therefore change the exact features and results.

## Live-site fix

Browser inspection found Cloudflare returning an older `motion-studio.js` without automatic recognition. Local application/model/style URLs are now versioned, and static responses request revalidation. Verified over public HTTPS that the current module loads and the Automatic words toggle works. The first stale-code replay is preserved outside the website as a diagnostic and excluded from recognition conclusions. **No candidate model was deployed.** Refresh the website to load the corrected assets.

## Saved artifacts

- [Decision](decision.json)
- [Fresh test details](fresh-test-results.json)
- [Frozen candidates and hashes](frozen-candidates.json)
- [Browser timings and parity](browser-classifier-benchmark.json)
- [Real-time candidate replay](realtime-candidate-camera-sized.json)
- [Training scripts](../../training/accuracy/README.md)
- [Trained PyTorch candidate](temporal-candidate.pt)
- [Browser-format candidate weights](temporal-candidate-browser.json)

Raw videos, feature caches, and candidates remain under `/opt/handspeak-training/accuracy-v4`. The next experiment should address automatic false suggestions and live body-reference failures, then reserve another untouched test set.
