# Conservative manual recognition recovery — 2026-11-08

**Recognition is not fully repaired. No candidate has been deployed.**

## Native development validation only

Official ASL Citizen TRAIN references and signer-disjoint VAL recordings were used. The old Watch/test/online-audit cohorts were excluded from fitting. These are selection-set results, not independent or live-camera accuracy.

| Mode | Correct: baseline → candidate | Wrong: baseline → candidate | No match: baseline → candidate | Unsupported accepts: baseline → candidate |
|---|---:|---:|---:|---:|
| default | 18 → 21 | 2 → 0 | 9 → 8 | 58 → 7 |
| expanded | 35 → 42 | 6 → 0 | 19 → 18 | 60 → 10 |
| daily | 16 → 16 | 2 → 0 | 6 → 8 | 80 → 15 |
| pack | 22 → 22 | 1 → 0 | 0 → 1 | 176 → 61 |

The rejection guard preserves every correctly accepted native validation recording. A separate fallback recovers FINISH and DRINK only after that guard rejects. Supported fallback classes require at least three correct validation recordings, two validation signers and zero additional wrong/unsupported validation accepts. Sparse classes and daily/pack fallback remain disabled. FINISH recordings appear in both default and expanded modes; mode improvements are not independent additional recordings.

Exact Python/JavaScript parity: 228 validation recordings / 912 mode outcomes. Maximum distance/separation error: 6.66e-15.

Frozen candidate SHA-256: `7703f7ef94d5eef1106152884f8c10893de7da196b66b3dc25275f413f3ef034`

The ASL Citizen originals and derived template bank stay outside the served repository under local noncommercial research terms. This report contains aggregate metrics only.

## Ongoing verification

- The 34-clip train/validation browser check is development evidence, not an independent audit. Earlier bootstrap and retired-tracker failures are preserved separately; no best-of results replace them.
- An unused-recording PopSign cohort is being acquired after freezing the candidate. Known signer IDs are not new signers; cross-dataset signer separation remains unverified. Public publisher TLS validation is unavailable on this host; the scoped acquisition has no credentials and reports this limitation.
- The actual app full-198 Watch → Practice → Record regression is frozen using the actually loaded production checkpoint identity. It uses old references, including synthetic greetings, not fresh natural-phrase evidence.
- No prototype, threshold, route policy or production weight was changed from these browser or online audit outcomes.

Tests this phase: 244 JavaScript passed, 2 skipped; 68 targeted Python passed. No full-Python-suite pass is claimed.

## Completed 34-clip browser development check

33/34 captures passed paired-stream contracts (2,248 paired frames). The NO take timed out and remains a counted failure. 32 body-usable captures produced 128 actual production API receipts. Both scalar ledgers are intact; all 225 frozen inputs stayed unchanged; zero physical camera/microphone calls; owned processes were cleaned up.

| Validation mode | Correct: baseline → guard | Wrong: baseline → guard | Unsupported: baseline → guard |
|---|---:|---:|---:|
| default | 3 → 3 | 1 → 0 | 7 → 1 |
| expanded | 7 → 6 | 2 → 0 | 4 → 0 |
| daily | 4 → 4 | 0 → 0 | 12 → 3 |
| pack | 5 → 4 | 0 → 0 | 21 → 7 |

**Do not deploy this candidate.** The browser guard lost correct HUNGRY and NIGHT validation predictions, plus the separate HAVE training infrastructure prediction. Native validation parity is not sufficient evidence of browser reliability. No gates were adjusted from these results. The recovery fallback itself has not yet been evaluated in a browser.

The full-198 actual-app regression has now started with durable checkpoints and real production API receipts. Final counts are pending. Newly acquired online originals remain audit-only and have not been recognized or used to fit any candidate.

A separate browser-domain development plan is frozen: 162 TRAIN / 132 VAL sources; all 34 earlier browser-check recordings excluded. Only 18/24 manual classes have the minimum metadata support. Sparse classes are explicitly retained as unsupported for gate fitting. No new features or predictions have been captured from this cohort yet.

Additional domain-selection tests: 3 passed (71 targeted Python in this phase in total).

Online acquisition completed: 54 originals, 54/54 full decodes, 4265 decoded frames, no predictions. The actual acquisition has no coverage for BABY, FISH, GO, LOVE, NAME, PAIN, WANT; CAR and DOG negative clips were also unavailable at the frozen selection offset. No absent classes are reported as passing.

Exact BABY/LOVE publisher v2 metadata is available (53/44 test entries respectively), but no v2 recordings have been acquired or evaluated; anonymized source IDs need provenance screening first. Additional metadata tests: 2 passed (73 targeted Python in this phase).
