# Framing-aware 11-word candidate with development-selected cutoffs

**Development screening passed; ordinary-movement release screening failed. Not deployed.**

The scale-augmented training run completed. Its best global-cutoff checkpoint
(epoch 10) still accepted one unsupported development example as HAVE at 0.5625×
scale. Every word is now checked against the same predetermined stricter cutoff
grid across all three development scales. HAVE requires 0.90; the other ten remain
at 0.80. These are classifier rejection scores, not calibrated confidence values.
No cutoff was lowered and excluded winning classes never fall back to a supported
runner-up. All 11 labels remain in the test; none were dropped to hide a failure.

| Development condition | Correct / 44 | Wrong words | Other-sign/ordinary accepts |
| --- | ---: | ---: | ---: |
| Original landmarks | 36 | 0 | 0 / 268 |
| 0.5625× landmark scale | 36 | 0 | 0 / 268 |
| 1.3× landmark scale | 35 | 0 | 0 / 268 |

These are repeated development clips, conditional on their existing tracking
masks. They are not independent samples or freshly re-detected scaled videos.
Every word has at least one correct example in every development condition.

Frozen checkpoint: `454b5ed628ae03f5fe5ea53b7f64bed624d6ffbafda81809b9602c261ecb4268`.
The complete cutoff mapping, checkpoint and evaluation implementations were frozen
before selecting the new held-out recording set. That set excludes previous
filenames/content hashes and all development signers. It uses the existing held-out
signer pool, not newly recruited people. See `../framing-fresh/job-status.json`.

The actual preview classifier matched Python on 231 development framing cases
covering all 58 output labels. Maximum feature error: 4.65e-7. Browser classification
median/p95: 38.7/41.6 ms on this server, excluding hand detection. Camera capture,
ordinary movements and fresh held-out checks still determine release readiness.

## Completed fresh recording checks

Sign recordings: 28/44 correct, zero wrong words, 16 misses, and 0/92 other-sign
false accepts; every target had at least one correct recording. Ordinary actions:
one false HOME among 12 recordings (eight with usable hand tracking), including
coverage of all four actions. This prevents promotion despite the sign-only pass.
See `../framing-fresh/test-results.json` and
`../framing-ordinary-fresh22/evaluation.json`.

A fixed mirror-agreement rejection check passed development screening but did not
fix the known ordinary failure: 28/44 known signs correct, zero wrong words,
0/92 other-sign accepts, one ordinary false HOME. No thresholds were tuned.
See `mirror-consistency.json` and `mirror-regression.json`. This rule is not deployed.
