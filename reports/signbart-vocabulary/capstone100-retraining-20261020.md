# CAPSTONE_ASL 100-word retraining

Date: 2026-10-20

## Outcome

The replacement checkpoint remains offline. It improved substantially against
the vendored checkpoint under the new extraction protocol, but 69.95% top-1
validation accuracy is not strong enough to present as reliable 100-word
recognition.

| Model / crop | Top-1 | Top-5 | Macro F1 | Validation clips |
| --- | ---: | ---: | ---: | ---: |
| Vendored checkpoint, active region | 32.51% | 60.66% | 31.06% | 366 |
| Fine-tuned checkpoint, active region | **68.85%** | **89.62%** | **67.91%** | 366 |
| Fine-tuned checkpoint, full clip | **69.95%** | **89.07%** | **70.23%** | 366 |
| Regularized full clip, seed 17 | **69.95%** | **87.70%** | **69.47%** | 366 |
| Vendored checkpoint, stroke only | 13.39% | 33.61% | 12.27% | 366 |
| Fine-tuned checkpoint, stroke only | 42.08% | 69.95% | 40.74% | 366 |

The active/full results show that the live pipeline's stroke-only crop removes
useful preparation and retraction motion. Any later integration should retain
the full motion and must be tested against negative motions before release.

## Promotion gate

The candidate is eligible for live integration only after all of these pass:

- at least 75% top-1 and 70% macro F1 on participant-separated validation;
- evaluation on the still-untouched official test partition;
- an out-of-vocabulary and ordinary-motion false-match audit;
- browser and Android camera integration checks.

## Protocol

- Vocabulary: the 100 labels in the vendored CAPSTONE_ASL label map.
- Source: ASL Citizen official train and validation partitions.
- Optimizer input: 1,798 tracked training clips.
- Checkpoint selection: 366 separately partitioned validation clips.
- Tracking exclusions: two training clips and one validation clip, using a
  predeclared minimum of eight body and hand frames.
- Extraction: MediaPipe video tracking on 15 uniformly sampled frames,
  linearly resampled to a 60-frame sequence.
- Architecture: the vendored 448-input TCN with attention, initialized from the
  vendored checkpoint.
- Fine-tuning: AdamW, learning rate 0.0001, up to 25 epochs, class weighting.
- Best active-region epoch: 21.
- The official test partition was not downloaded or opened.
- Raw videos, landmarks, feature caches, and checkpoints remain under
  `/opt/handspeak-training/capstone100-retrain` and are not served or committed.

## Reproducibility

- Candidate checkpoint SHA-256:
  `b53154832447dd88932c18d8aca2e3435df6285f96bb8d1418613de2f75d72cd`
- Best full-clip checkpoint SHA-256:
  `215ba7e1c7cd3e7f28eb58991ffd85f12577eba7fcca13655c8ebad04f03b4c3`
- Extraction protocol SHA-256:
  `1884e2ed344d303212d29cbec98f0b8797b6c0315a5ad1ff4de5ddc3933abed4`
- Development manifest SHA-256:
  `d92023790fb94269f17ff55d90edc6270e90dc3423d2e71041243b8934b73266`

Commands:

```bash
python training/catalog/download_citizen_capstone100.py
python training/catalog/extract_citizen_capstone100.py --workers 4
python training/catalog/train_citizen_capstone100.py --crop active
```

ASL Citizen data is restricted to noncommercial research use. Dataset-derived
artifacts should not be published or deployed without confirming that the
dataset terms permit that use.

## Second training run — 2026-10-21

The second run added temporal-boundary jitter, light normalized-feature noise,
6% label smoothing, 40% dropout, stronger weight decay, and cosine learning-rate
decay. It matched the first run's 69.95% top-1 score but reduced macro F1 from
70.23% to 69.47%. It therefore failed the promotion gate and was not deployed.

Checkpoint SHA-256:
`4171d16f64fdf601a16690daecfac7f1f543d0c1cd6896de7ec542d62d8c486d`
