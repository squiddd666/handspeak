# Capture-throughput repair — 2026-11-08

**The shared Beginner/Capstone body capture now uses a worker on supported browsers. This is a tested capture repair, not proof that recognition is fully fixed.**

## Implemented

- Moved the existing pinned Holistic graph off the camera/UI thread. Source images are copied/transferred with explicit ownership; output images/masks are released after hand recovery.
- Retained the same pose/hand geometry, graph complexity, confidence gates, countdown pose requirement, 4/6/8-second recording windows, 80-image memory cap and queued snapshots.
- Selected CPU execution for software rendering; preserved hardware-GPU preference and legacy iOS CPU behavior. Same-frame IMAGE recovery stays separate from the independent VIDEO hand graph.
- Added guarded fixes for the pinned legacy SDK's worker asset URL and missing GL upload handle. No vendor source or detector weights were edited.
- Guarded close/reset/timeout races and late results; unsupported browsers retain the explicit legacy path. Worker errors fail the take rather than silently restoring blocking UI inference.
- Updated application cache tags so the app and both server vocabularies share the same capture service version.

## Independent development evidence

Three previously used **ASL Citizen train** clips from **one known signer (P11)** were chosen before the probes. None overlaps the 76 online audit clips by SHA-256. Originals remained outside the served repository. No expected labels, classifier references, recognition thresholds or winners were used to choose outputs. Browser probes performed landmark tracking and feature-usability checks, not word recognition.

A matched baseline dual capture collected **8 frames** in four seconds and did not produce a usable manual encoding. Its updated-default counterpart collected **69 frames**, with a usable encoding. All three integrated default captures used the worker, preserved body output and passed immutable-input/epoch/timestamp/dimension contracts.

| Development clip | Window | Sampled/processed pairs | Tracked body frames | Tracked manual frames | Manual encoding usable | Max recording UI lag (ms) |
|---|---:|---:|---:|---:|---|---:|
| dev-1 | 4s | 69 | 9 | 9 | yes | 76.3 |
| dev-2 | 4s | 70 | 13 | 12 | yes | 17.3 |
| dev-3 | 6s | 72 | 12 | 12 | yes | 28.8 |

Blank input still failed pose warm-up without recording; cancellation still produced no accepted capture. The final output-resource cleanup smoke processed **69** pairs with a usable manual encoding and passed contracts.

The same 12 unique source timestamps were also processed serially: median send time was **1250.8 ms** on the baseline and **197.9 ms** on the worker/CPU variant. This compares both execution changes together, not the worker in isolation.

All measurements used a fresh headless Chrome profile with SwiftShader software rendering. They are not user-hardware or live-camera accuracy figures, and capture contracts do not prove full production-app routing or coordinate equality across delegates.

## Verification

- **225 JavaScript tests passed; 2 skipped; 0 failed.**
- **6 targeted Python tests passed.** No full Python-suite pass is claimed.
- **41 frozen application classifier artifacts** remain byte-identical; recognition gates and classifier kernels were not changed. No retraining, recalibration or rejected-candidate promotion occurred.
- All owned browsers/servers exited; loopback ports 8010/9230 have no listeners. Physical camera/microphone access was blocked, with zero calls.
- Earlier uncommitted application edits were preserved. The original 76-clip audit remains baseline evidence only and was not replayed. Its changed runtime files remain verifiable using matching archived snapshots in `C:\Users\Squid\Desktop\capstone\hs-eval\capture-throughput-dev-20261108\audited-baseline-resolution.json`.

## Retained development failures

`development-results.json` retains every probe: the initial worker failed on packed-asset URL resolution; subsequent probes exposed the legacy SDK's missing GL upload handle. The initial serial probe also revealed a non-seekable development server returning repeated time-zero frames, so it is explicitly excluded from motion-throughput comparisons. Media byte-range support and seek validation corrected that fixture defect. These were development iterations, not best-of recognition audits. A single regression assertion required updating the application's intentional cache version; both the failed run and the passing rerun logs are retained.

## Next step

Freeze this runtime and run an **untouched production-browser recognition audit** on separate recordings, including the full-198 routing regression and truly new-signer validation where available. Do not fit references or confidence gates to the previous 76 audit clips. Recognition confusion/rejection and open-set false acceptance still require independent model-development work.

Evidence: `C:\Users\Squid\Desktop\capstone\hs-eval\capture-throughput-dev-20261108`. The JSON verification manifest records current source, unchanged model and evidence hashes. No online audit recordings or local research video were added to this report.
