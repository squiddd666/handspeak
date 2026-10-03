# Five-word training experiment — 2 October 2026

Trained private research models for NAME, HOME, HAVE, WANT and LOVE on a targeted ASL Citizen subset. Neither model passed the original release criteria. Following the user’s explicit request to apply it, the DTW model was integrated into an administrator-only, opt-in server research preview. The user subsequently requested public access; it is now an opt-in guest-accessible preview, excluded from default recognition. See [public deployment](public-preview-deployment.md).

## Data and method

- 250 development clips: 179 training and 71 validation. Only 147 training clips had usable hand sequences; tracking failures remained misses in evaluation.
- 114 previously untouched test clips: 66 requested-word clips and 48 other-sign clips; 100 produced usable sequences.
- Official source signer partitions retained. Training/validation/test signers and exact file hashes were checked for overlap. Each source gloss contributes at most one recording per signer. WANT1 and WANT2 are pooled as WANT, with their source identities retained privately.
- DTW baseline uses hand-landmark sequences. Temporal candidate uses local hand shape, movement, and a center-frame upper-body reference, with a compact convolutional network and mirrored training augmentation.
- Thresholds/checkpoints selected using validation only; model hashes were frozen before test video download. The zero-false-suggestion gate and at least 50% supported recall were declared before training.

## Results

| Model | Validation correct | Validation false accepts | Test correct | Test false accepts |
|---|---:|---:|---:|---:|
| Sequence matcher (DTW) | 11/23 | 0/48 | 44/66 | 2/48 |
| Temporal model | 14/23 | 0/48 | 37/66 | 2/48 |

Neither model produced a wrong supported label on the supported test clips; their other failures were misses. Each made two false suggestions on unsupported-sign clips. DTW missed the initial validation recall gate. The temporal model passed validation but failed the untouched-test false-accept gate. The better DTW test result was not used to switch models or retune after seeing test outcomes.

| Word | DTW correct | Temporal correct |
|---|---:|---:|
| NAME | 6/11 | 7/11 |
| HOME | 6/11 | 3/11 |
| HAVE | 8/11 | 8/11 |
| WANT | 15/22 | 17/22 |
| LOVE | 9/11 | 2/11 |

## Limits and deployment

These are small, isolated-clip tests, not live webcam accuracy or continuous-ASL translation. No ordinary non-sign movement recordings or automatic-boundary test was conducted. The network-only CPU latency excludes landmark extraction, camera processing and browser overhead. Probabilities are uncalibrated and must not be shown as confidence percentages.

ASL Citizen is used only for private noncommercial research under the license included with its official archive. No recordings, signer metadata, derived landmark templates, or checkpoints were published. The private experiment directory is restricted to its owner. All existing live model files and the category index were verified unchanged.

Private checkpoints: `/opt/handspeak-training/daily-words/citizen-research/dtw-private.json` and `temporal-private.pt`. Reproduction scripts are in `training/daily_words/`; aggregate results are in `citizen-test-report.json`. Seven training/representation tests passed.

Source: [Microsoft ASL Citizen](https://www.microsoft.com/en-us/research/project/asl-citizen/). Citation: Desai et al., ASL Citizen: A Community-Sourced Dataset for Advancing Isolated Sign Language Recognition (2023).
