# Official ASL Citizen ST-GCN 100-word release

Released as an opt-in server-landmark preview on 2026-10-21.

| Partition | Preprocessing | Clips | Top-1 | Top-5 | Macro F1 |
|---|---|---:|---:|---:|---:|
| Validation | MediaPipe Holistic, official | 367 | 92.37% | 97.00% | 92.03% |
| Untouched test subset | MediaPipe Holistic, official | 516 | 86.43% | 95.35% | 85.69% |
| Validation compatibility check | MediaPipe Tasks | 367 | 55.59% | 79.02% | 57.16% |

The untouched subset covered all 100 labels with 2–12 clips per label. It was frozen by completed extraction order before any test predictions were computed. The remaining official test clips were not used. MediaPipe Tasks failed compatibility, so the live opt-in interface loads MediaPipe Holistic in the browser. Video stays on the device; extracted coordinates are processed in server memory and are not stored.

Warm server inference measured about 240 ms. Live-camera accuracy remains unverified, predictions require user review, and the model remains labeled experimental.
