# Online recognition recording intake — 2026-11-07

**76 previously unused recordings retained for audit. Recognition is not repaired by downloading data.**

* Downloaded 127 publisher-original clips (409.1 MiB); excluded 51 known/duplicate clips. Exclusions and both acquisition selections remain intact.
* 69 recordings cover **19/24 candidate words**; 7 APPLE/CAR/DOG recordings are negatives for this frozen candidate, not necessarily for the full application.
* 8 **previously used** PopSign signer IDs. These are new recordings to the available inventory, not a fresh-new-signer audit. Identity overlap with anonymous ASL Citizen participants is unverified. No identity is inferred from faces.
* 76/76 included clips passed size/hash/full-decode checks; 9106 frames decoded across all acquired files. Decode checks did not choose winners or alter videos.
* All 54 frozen model/runtime files unchanged: **True**. No predictions, training, calibration, candidate installation, or physical-camera calls occurred.
* 15 targeted intake tests passed, including the unchanged stricter user-provided fresh-signer validator. No new full application test pass is claimed.

## Provenance and license

Original **PopSign ASL v1.0**, game category, official test split; Thad Starner et al., Georgia Institute of Technology and Deaf Professional Arts Network.

- [Publisher and public-use consent statement](https://signdata.cc.gatech.edu/view/datasets/popsign_v1_0/index.html)
- [CC BY 4.0 license](https://creativecommons.org/licenses/by/4.0/)
- [Original download documentation](https://signdata.cc.gatech.edu/view/guides/downloading_popsign/index.html)

Original archive URLs, member names, signer IDs, original-byte SHA-256 hashes and absolute local paths are recorded in `frozen-online-intake.json`. Videos remain outside the served repository. Only local cache filenames were changed; video bytes, framing, timing and audio are unchanged. No endorsement is implied.

Publisher v2 pages re-anonymize IDs and move some legacy fitting recordings into their test split. The two checked v2 NO original-archive links returned 404; no v2 preview was used as a substitute. Publisher previews change resolution and duration and are unsuitable here.

**Transport limitation:** the publisher certificate chain was untrusted on this host. The downloader used a public-publisher-host-only unverified TLS context, without credentials. Hash checks establish consistency with available records, not authenticated publisher checksums. Publisher snapshots and this limitation are preserved.

## Identity screening, not performance selection

The first acquisition selected clips using metadata only, then found 51 known-content exclusions despite unfamiliar filenames. Those clips were retained as exclusions, not relabeled as fresh. The second acquisition used a fixed archive metadata offset of 60, frozen before downloading videos, to avoid early members whose older audit hashes lacked filenames. Both phases excluded known recording keys and PopSign fitting signer IDs, then checked content hashes. No recognizer outputs influenced acquisition or deduplication.

Missing candidate labels: **BABY, LOVE, NAME, PAIN, WANT**. Related HURT/WANTTO/PETSNAME labels were not silently substituted. These files do not cover all 198 application words.

| Publisher-aligned label | New recordings |
|---|---:|
| APPLE | 3 |
| BOOK | 3 |
| CAR | 3 |
| DOG | 1 |
| DRINK | 3 |
| FINISH | 3 |
| FISH | 3 |
| FOOD | 6 |
| GO | 6 |
| HAVE | 3 |
| HELLO | 3 |
| HOME | 3 |
| HUNGRY | 6 |
| LIKE | 6 |
| NIGHT | 3 |
| NO | 3 |
| PLEASE | 3 |
| SEE | 3 |
| SICK | 3 |
| THANK YOU | 3 |
| WATER | 3 |
| YES | 3 |

## Next

Freeze the exact production/candidate inference and browser sampling protocol before making predictions. Run every included clip once, keeping tracking failures, rejections and incorrect/unsupported acceptances in the denominator. Do not train or select gates on this cohort. If retraining is justified, obtain separate development recordings; keep this intake audit-only. A genuinely new-signer audit and the full-198 production-browser regression remain outstanding.
