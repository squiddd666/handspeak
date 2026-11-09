# Fresh worker recognition audit — 2026-11-08

**62 originals tested once. Recognition is not fully repaired.**

This is a previously-unused-recording, **known-signer** regression according to available local provenance, not genuinely new-signer validation, a full-198 audit, full application UI routing, or live-camera accuracy. Anonymous cross-dataset signer identity separation is unverified. No faces were used to infer identity.

## Recognition results

Each mode has its own exact-label positive/negative denominator. Modes are never merged into a best-of result. Unaccepted suggestions are not matches. Zero-positive modes cannot establish recognition accuracy.

| Independent mode | Positives | Matched | Incorrect | No match | False accepts / negatives |
|---|---:|---:|---:|---:|---:|
| default | 18 | 12 | 0 | 6 | 23/44 |
| expanded | 38 | 21 | 5 | 12 | 20/24 |
| daily | 6 | 2 | 3 | 1 | 22/56 |
| pack | 12 | 8 | 1 | 3 | 42/50 |
| beginner | 0 | 0 | 0 | 0 | 16/62 |
| capstone-core | 0 | 0 | 0 | 0 | 8/62 |
| capstone-extended | 0 | 0 | 0 | 0 | 4/62 |
| capstone-full | 3 | 3 | 0 | 0 | 9/59 |
| offline-body-candidate | 56 | 10 | 2 | 44 | 0/6 |

The offline body candidate remains rejected and uninstalled. Different clips and updated execution mean these counts are **not a paired accuracy-improvement comparison** with the old audit or the user's 198-word totals. FOOD→EAT1 and other dataset gloss substitutions were not made.

## Capture and actual production APIs

- 62/62 captures passed immutable-pixel, epoch, timestamp, dimension and unmodified-body-output contracts using the integrated worker path.
- 62 completed; 0 failed; 0 canceled. All outcomes remain in each applicable denominator.
- 55–68 processed pairs per take; 0 takes fell below the manual encoder's **12-total-frame** input minimum. 3 had fewer than its separate five-visible-frame requirement; 53 produced a usable encoding after the unchanged continuity/geometry checks. 60 takes met the production client's five-body-frame minimum.
- 240 real HTTP prediction requests; 0 non-200 responses. All four production modes received the identical unchanged landmark array digest for each usable take, without expected labels or minScore hints. Scalar API receipts preserve accepted/rejected outcomes; no raw images or landmark arrays were saved.
- 0 sources exceeded their frozen 4/6/8-second window; truncations were flagged rather than sped up or replaced.
- 50 application classifier artifacts and every frozen runtime/harness input remain byte-identical. No retraining, recalibration, gate editing or candidate promotion.
- Actual loaded checkpoints: Beginner `beginner-repaired-v2.pt`; Capstone `capstone100-v4-ensemble.pt`. These are the loaded identities, not guesses from preferred candidate filenames; their status and SHA-256 evidence were frozen before acquisition.
- Zero physical camera/microphone calls. Only owned headless Chrome and loopback servers were used; the real user database and MySQL were isolated from the audit.

### Retained capture failures

None.

## Per-word matched coverage

| Exact publisher label | Clips | Default | Expanded | Daily | Pack | Offline body candidate |
|---|---:|---:|---:|---:|---:|---:|
| APPLE | 3 | outside vocabulary | outside vocabulary | outside vocabulary | outside vocabulary | outside vocabulary |
| BOOK | 3 | outside vocabulary | 1/3 | outside vocabulary | outside vocabulary | 0/3 |
| CAR | 3 | outside vocabulary | outside vocabulary | outside vocabulary | outside vocabulary | outside vocabulary |
| DRINK | 3 | outside vocabulary | 1/3 | outside vocabulary | outside vocabulary | 1/3 |
| FINISH | 3 | 2/3 | 1/3 | outside vocabulary | outside vocabulary | 0/3 |
| FISH | 3 | outside vocabulary | outside vocabulary | outside vocabulary | 2/3 | 0/3 |
| FOOD | 3 | outside vocabulary | 3/3 | outside vocabulary | outside vocabulary | 1/3 |
| GO | 2 | outside vocabulary | 1/2 | outside vocabulary | outside vocabulary | 0/2 |
| HAVE | 3 | outside vocabulary | outside vocabulary | 0/3 | outside vocabulary | 0/3 |
| HELLO | 3 | 0/3 | 0/3 | outside vocabulary | outside vocabulary | 0/3 |
| HOME | 3 | outside vocabulary | outside vocabulary | 2/3 | outside vocabulary | 1/3 |
| HUNGRY | 3 | outside vocabulary | 2/3 | outside vocabulary | outside vocabulary | 0/3 |
| LIKE | 3 | outside vocabulary | 1/3 | outside vocabulary | outside vocabulary | 0/3 |
| NIGHT | 3 | outside vocabulary | outside vocabulary | outside vocabulary | 3/3 | 0/3 |
| NO | 3 | 3/3 | 3/3 | outside vocabulary | outside vocabulary | 0/3 |
| PLEASE | 3 | 3/3 | 3/3 | outside vocabulary | outside vocabulary | 2/3 |
| SEE | 3 | outside vocabulary | outside vocabulary | outside vocabulary | 3/3 | 0/3 |
| SICK | 3 | outside vocabulary | outside vocabulary | outside vocabulary | 0/3 | 0/3 |
| THANK YOU | 3 | 3/3 | 2/3 | outside vocabulary | outside vocabulary | 2/3 |
| WATER | 3 | outside vocabulary | 2/3 | outside vocabulary | outside vocabulary | 3/3 |
| YES | 3 | 1/3 | 1/3 | outside vocabulary | outside vocabulary | 0/3 |

All route-specific incorrect/no-match/negative outcomes are retained in `outcomes.json` and `summary.json`; failures are not silently removed. Acquisition exclusions and metadata shortfalls remain outside the recognition cohort and are retained in its source evidence, with no replacement download selected using model results.

## Online source and limitations

[PopSign ASL v1.0 publisher](https://signdata.cc.gatech.edu/view/datasets/popsign_v1_0/index.html), Georgia Institute of Technology / Deaf Professional Arts Network; [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Official game/test archive originals, no preview/re-encoding substitutions. Publisher public-use statement is not independently verified new-signer consent.

Publisher TLS chain untrusted on this host; public-original-host-only unverified TLS used without credentials. Local hashes are consistency checks, not publisher authentication.

Originals, metadata-only selections, explicit prior-key/hash/development exclusions, frozen models/status, individual capture ledger entries and API response receipts: `C:\Users\Squid\Desktop\capstone\hs-eval\online-worker-recognition-audit-20261108`.

## Next

Use these failures only to diagnose the remaining tracking/domain/label coverage gaps, **not to fit or select the next model**. Develop on separate consented/licensed recordings, then freeze another unused cohort. The full-198 production-routing regression and genuinely new-signer validation are still required before claiming a complete recognition repair.

## Verification and next development priorities

- **25 targeted Python and 39 targeted JavaScript tests passed**, both before and after the fresh audit. No full application-suite pass is claimed.
- All **178 frozen files** remain byte-identical. Owned browser/server processes exited; ports 8011/9231 have no listeners. The final screenshot confirms 62 durably saved outcomes.
- All eight included PopSign signer IDs previously appeared in the local test split. These are unused **recordings**, not new people.
- Acquisition retained its frozen shortfalls: GO has 2/3 eligible originals; DOG has none after the fixed metadata offset. No replacements were selected. All 62 acquired originals decoded into pixels for every frame (5,439 frames).
- Harness development and the initial Python-3.10 SHA-helper compatibility failure were separate from recognition; their logs and byte-identical preflight snapshots are retained in the external evidence folder. No audit clip was retried or used for model selection.

The next development priority is **unsupported-sign rejection**: every mode except the rejected offline candidate showed false accepts on its mode-specific negatives. Confusions also remain (HAVE→HOME, FISH→SEE, and multiple expanded-mode confusions), plus nine unusable manual encodings. Fix and validate these using separate development/validation recordings, never by training on this cohort. Keep the candidate offline and re-audit on another unused cohort before promotion.
