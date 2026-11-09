# Recognition diagnostics v6 — 2026-11-07

The padding candidates are **not installed**. The production capture code, model weights and calibration were restored to the retained pre-padding state. The v5 body-manual candidate also remains offline.

## Separate 28-reference trials

| Trial | Matched | Incorrect | No match |
|---|---:|---:|---:|
| baseline | 12 | 4 | 12 |
| padding | 6 | 3 | 19 |
| paddingParity | 10 | 2 | 16 |

Separate diagnostic reference trials, not independent accuracy or a clean causal benchmark. The first padding candidate changed unpadded warm-up resolution; the second restores that input. Sampling rates differed between trials. Every wrong/no-match output is retained. No best-of aggregation.

## Installed diagnostic repair

The opt-in fixture now saves scalar checkpoints after every completed attempt using scripts/serve_motion_audit.py. The audit server binds only to 127.0.0.1, uses a separate test database, validates frozen fixture/clip identities, rejects raw coordinate arrays and changed past outcomes, and preserves misses. Production server.py has no checkpoint endpoint. These are test outcomes, not user video/landmarks or personal samples.

## Offline body-runtime math parity

The experimental JavaScript representation, anatomical mirror, banded distance, and frozen prediction gates are checked against Python without a camera. The candidate is not imported by production. Body and manual hand streams must remain separate; this check does not fix the known NO regression or verify browser capture parity.

## Remaining work

All 198 words were not retested in v6. The previous v5 all-word report was lost before download after the browser session ended; no totals have been reconstructed from incomplete logs. The last saved full-198 v4 result remains separate (135 matched, 6 incorrect, 57 no match) and is not a v6 result.

Padding alone does not resolve the native/browser sampling gap, sign variants, or model confusion. Do not lower gates or promote the v5 model using the reused held-out results. The next model iteration needs separate body + hand capture streams, validation-only training/route selection, a newly untouched signer/source-separated audit, and a full browser regression with durable reports.

All frontend tests passed for each candidate; relevant recognition/checkpoint Python tests passed. Full Python discovery did not pass: missing platform dependencies (MediaPipe in the PyTorch environment, Linux-only ffprobe path), Windows text encoding, and legacy motion/word fixture failures remain recorded in the external v6 test logs. No blanket all-tests-passed claim is made.

Frozen JS/Python validation prediction agreement: 228/228. Maximum feature absolute difference: 2.38e-07; distance difference: 3.7e-08. All validation outcomes, including rejected inputs, are preserved in body-runtime-validation-parity.json. This is implementation agreement, not recognition accuracy.
