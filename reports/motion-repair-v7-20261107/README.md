# Separate body/hand capture verification — 2026-11-07

**Recognition is not fully repaired. No candidate was installed.**

## Verified capture contracts

* Original body recording sampler, queue, countdown exclusion, API filtering, and cancellation lifecycle are used.
* Holistic body/recovery and independent Tasks VIDEO hands read copies of one immutable image. Matching pixel checksums, dimensions and source timestamps are verified.
* The original Holistic result is forwarded unchanged. Manual detector hands are never substituted into its output; the two feature streams remain separate.
* A bitmap is retained until both detectors settle, including a failure of either reader. Both graphs reset between takes.
* **9/9 completed captures passed** (304 paired recording frames). One canceled NO take and the separate HELLO restart are preserved. Zero physical camera/microphone calls.
* Production application sources, weights and gates are unchanged. The diagnostic server is stopped. Scalar checkpoints contain no images or raw landmark arrays.

## Actual diagnostic outputs — not recognition accuracy

| Attempt | Reference | Status | Contract | Body candidate | Manual expanded |
|---:|---|---|---|---|---|
| 1 | HELLO | complete | True | NO MATCH | HELLO |
| 2 | NO | complete | True | NO MATCH | NO |
| 3 | HUNGRY | complete | True | NO MATCH | FOOD |
| 4 | FINISH | complete | True | NO MATCH | NO MATCH |
| 5 | PLEASE | complete | True | LIKE | PLEASE |
| 6 | BOOK | complete | True | NO MATCH | BOOK |
| 7 | PAIN | complete | True | NO MATCH | NO |
| 8 | APPLE | complete | True | NO MATCH | FOOD |
| 9 | NO | canceled | False | NO MATCH | NO MATCH |
| 10 | HELLO | complete | True | NO MATCH | DRINK |

Capture-contract verification only: original recording sampler with an experimental immutable dual-reader coordinator. Nine completed captures include a separate HELLO restart, not best-of accuracy. One canceled NO take is retained. Diagnostic warm-up is frozen for both readers; native whole-clip sampling and full production routing are not verified. Candidate recognition failures remain; the known NO regression is not repaired. Fresh audit awaits provider recordings.

The body candidate missed most references and suggested LIKE for PLEASE. Manual expanded recognition also confused HUNGRY, PAIN, APPLE and the separate HELLO restart. These outputs are retained, not used to adjust gates. APPLE and PAIN are unsupported in the selected manual expanded vocabulary; false suggestions are not successes.

## Fresh audit waiting for new-signer recordings

Metadata confirms all 11 official test signers were already audited. The provider said they can supply new-signer recordings; no files or folder path have been supplied yet. No reused cohort is described as fresh.

Supply consented local clips with true labels, pseudonymous signer IDs and unique source IDs. The prepared fresh-audit-intake/intake-template.json targets the frozen 24-word candidate, with other signs explicitly marked negative for that candidate. Audit clips remain out of training/calibration. The validator does not infer consent or signer identity from a face.

Tests: 209 frontend passed, 2 skipped; 94 targeted Python passed. Existing full-Python-discovery failures are not hidden and no full-suite pass is claimed.

Next: validate the supplied intake, freeze the audit protocol/model/route policies before extracting predictions, then count every miss and unsupported-sign false acceptance. New training/validation data must be separate if retraining is needed. A durable full-198 production-browser regression still remains.
