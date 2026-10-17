# Held-out availability audit — 2026-10-17

Read-only audit of the PopSign v1 held-out test archive used by the single-word fresh tests.
No training, no publication, no production change.

## Why

`/opt/handspeak-training/single-word-20261010/pain/fresh/job-status.json` failed with:

```
Insufficient held-out recordings for SHOWER: 1/2
```

`select()` in `training/catalog/evaluate_ready_subset.py` requires `negativeClipsPerWord` (2)
eligible clips for **every** label in `mappings`, and runs before any download or extraction.

## Method

For each of the 57 mapped labels, the label tar was scanned with HTTP range requests
(512-byte tar headers). A clip is eligible when its filename is not in `knownNames`
and its signer is not in `excludedSigners` — the same rule `select()` applies.
Scanning stops as soon as 2 eligible clips are found; labels that never reach 2 are
scanned to the end of the tar.

Machine-readable results: `heldout-audit-20261017.json`.

## Result

- 57 labels audited; **56 still have at least 2 eligible clips**.
- **SHOWER is the only shortfall.**

| Label | Eligible | Clips in tar | Distinct signers | Tar size |
|---|---|---|---|---|
| SHOWER | 1 | 19 | 1 (signer 8037) | 33,146,880 B |

`knownNames` currently holds 5,454 entries and `excludedSigners` 129. Eighteen of the
nineteen SHOWER clips are already in `knownNames`, so exactly one fresh SHOWER clip exists.
The tar ends after 20 headers — deeper scanning cannot produce a second one.

## Impact

`select()` iterates over every mapped label, so this single shortfall fails **every**
fresh single-word test, not just PAIN. FISH and SICK passed earlier only because
`knownNames` was smaller then; re-running their fresh tests today would fail at SHOWER.

## Options

1. **Exclude SHOWER from the negative panel.** 55 negatives remain (110 clips), above the
   gate's `negativeTotal >= 100`. Requires a pipeline version that records the exclusion in
   the protocol; the frozen scripts must stay byte-identical so the FISH/SICK protocols remain
   reproducible. SHOWER is the weakest label in the panel (11 development clips, single-signer
   test tar), so the loss of negative coverage is small — but results are no longer
   strictly comparable with the FISH/SICK runs and this must be documented.
2. **Supply a fresh SHOWER recording** from a signer outside `excludedSigners`. The current
   selector can only draw from the official archive by URL, so this needs a supported local
   override path in the pipeline before it can be used.
3. **Leave the pipeline untouched** and treat single-word expansion as blocked.

No option was applied in this audit.
