# One-pass online recognition audit — 2026-11-07

**Recognition is not fully repaired. No model or threshold was changed; the rejected candidate remains offline.**

All **76** identity-screened recordings were processed once per pipeline. These are previously unused recordings from **8 known PopSign signers**, not a new-signer benchmark. Publisher labels/variants are retained; identity overlap with ASL Citizen remains unverified. The original publisher TLS limitation remains in the intake report.

The body candidate supports 24 words; this cohort covers **19**, with **69** positive clips and **7** outside-vocabulary clips. Missing: BABY, LOVE, NAME, PAIN, WANT. This is not a retest of all 198 words or a comparison with earlier 198-word totals.

## Native full-clip audit

Uniform 32 unique original source-frame indices, maximum image side 640. Actual Holistic body outputs and separate Tasks VIDEO hand outputs are retained. Both graphs reset between clips. Failures and missing tracking remain in the denominator.

| Classifier | Positive clips | Matched | Incorrect | No match | Outside vocabulary | False accepts |
|---|---:|---:|---:|---:|---:|---:|
| candidate | 69 | 14 | 1 | 54 | 7 | 0 |
| default | 18 | 13 | 0 | 5 | 58 | 30 |
| expanded | 51 | 26 | 14 | 11 | 25 | 21 |
| daily | 6 | 3 | 2 | 1 | 70 | 39 |
| pack | 12 | 9 | 1 | 2 | 64 | 53 |

Native runtime/extraction failures: **0/76**.

## Isolated browser capture audit

Original createLandmarkCapture sampler, countdown exclusion, snapshots, queue, and result filtering. Independent detector inputs are copies of one immutable image; the body output is forwarded without manual-hand substitution. Source playback is unmodified at speed 1 in a 960×720 letterboxed virtual canvas. Original 4/6/8-second duration policy is frozen. Detectors initialize without images before the first take; every take resets both graphs.

| Classifier | Positive clips | Matched | Incorrect | No match | Outside vocabulary | False accepts |
|---|---:|---:|---:|---:|---:|---:|
| candidate | 69 | 1 | 0 | 68 | 7 | 0 |
| default | 18 | 1 | 0 | 17 | 58 | 0 |
| expanded | 51 | 0 | 1 | 50 | 25 | 0 |
| daily | 6 | 0 | 0 | 6 | 70 | 0 |
| pack | 12 | 0 | 0 | 12 | 64 | 1 |

**75/76** capture contracts passed; **381** paired frames. Failed/canceled outcomes: **1**. **0** sources exceeded the unchanged eight-second cap; they were flagged, not sped up, retried or excluded. Physical camera/microphone calls: **0/0**. Fresh headless browser, no user browser attached; the audit server/browser were stopped after completion.

## Interpretation

Each manual mode runs independently on every clip; its positive/negative denominator is its own frozen vocabulary. Default, expanded, daily, and pack outputs are **not combined into an oracle winner**. Expected labels are joined only after prediction. Native and browser sampling/geometry differ; capture contracts do not prove native/browser landmark equality or full production-app routing.

Every error, rejection, and unsupported acceptance is retained in `outcomes.json` and `remaining-errors.json`. Raw landmarks stay in the external audit folder, not this served report. All frozen production weights/runtime/gates remain unchanged. No training, threshold selection, best-of retries or candidate promotion occurred. The candidate's previous NO regression is not erased by this new cohort.

## Next repair boundary

Keep this cohort audit-only. Use its failures to identify tracking/runtime defects, not to choose gates or fit references. Any retraining requires separate development recordings and validation, followed by another untouched audit. Full-198 production-browser regression and genuinely new-signer validation remain outstanding.

External evidence folder: `C:\Users\Squid\Desktop\capstone\hs-eval\online-recognition-audit-20261107\browser-transport-v3`. Frozen protocol and source/cohort/model hashes precede predictions. Local screenshot: `C:\Users\Squid\Desktop\capstone\hs-eval\online-recognition-audit-20261107\browser-transport-v3\browser-proof.png`.

## Setup provenance and throughput findings

See [PROVENANCE.md](PROVENANCE.md) for the two setup-only transport amendments, verified native-evidence copy, and the observed sparse-frame bottleneck. [triage.json](triage.json) separates input preparation failures from classifier rejections. [verification.json](verification.json) records independent metric/hash/order checks and cleanup evidence.
