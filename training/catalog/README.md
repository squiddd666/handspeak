# Requested ASL vocabulary expansion

The catalogue contains 200 unique entries and 202 category memberships. SCHOOL and PHARMACY each belong to two categories. English labels and lesson links are not a claim of complete ASL translation.

Source availability was checked on 2026-10-02 (Asia/Manila). PopSign v1.0 provides downloadable recordings for 49 requested labels. Another 31 labels appear on PopSign v2.1 source pages, but their training archives returned HTTP 404 during this run. Those previews are linked, not used as training data. ASLU/Lifeprint lessons are external links; their videos are not rehosted. Related-word lessons are explicitly marked and must not be mistaken for full-phrase demonstrations. CHARGER still needs a verified lesson.

Raw recordings stay outside the served website in `/opt/handspeak-training/vocabulary-v7`. Only compressed, attributed practice examples and derived landmark templates are served. See `media/signs/README.md` for credits.

## Reproduction

Use the existing training virtual environment with MediaPipe, OpenCV, NumPy, SciPy, QuickJS, imageio-ffmpeg and Playwright. `build_catalog.py` initializes the catalogue from the saved PopSign label indexes; rerunning it resets enrichment, so preserve the final catalogue first.

1. `prepare.py` fixes archive-member selection before testing: up to 12 train, 4 validation and 4 test recordings per requested source label, no more than two recordings per signer. Source partitions and signer separation are retained. Previously evaluated source clips are excluded from the new positive test set.
2. `extract_stream.py` extracts completed development downloads with three workers. New videos are resized to 480 pixels wide and sampled to about 30 frames before using the existing hand detector and browser encoder. Older cached recordings retain their original extraction path. Both paths and source checksums are recorded; this preprocessing difference is a limitation.
3. `fit.py` trains independent category template models using development data only. Balanced examples from existing and newly collected training signs outside the selected category supply an internal negative class. A fixed validation objective penalizes wrong labels and negative false accepts four times as heavily as misses. It freezes parameters and SHA-256 hashes before reserved-test extraction.
4. `evaluate.py` checks the frozen models on new positive test clips, every new out-of-category test clip, and an explicitly reused balanced negative regression set. Ordinary non-sign hand movements are not evaluated. Tracking failures count as misses. No thresholds are adjusted from test outcomes.
5. `export_videos.py` exports practice clips from training recordings only. These examples are not independent accuracy evidence.

Category loading was implemented and tested, but all new category models are currently withheld after evaluation; the default six-word model is unchanged. Unsupported movements can still be falsely accepted. Recorded whole-clip evaluation, browser interface tests, and real-time camera behavior are separate measurements. There is no validated continuous-ASL or emergency-use claim.


## Accuracy follow-up

`refine.py` tests four hand-shape/wrist representations on validation only and freezes the selected model before `evaluate_refinement.py` runs a clearly labeled regression check. `refine_core.py` separately retrains the six default words and applies a validation gate. None of these first refinements passed the required improvement gate.

`recover_tracking.py` retries only failed development recordings using up to 60 actual sampled frames from the originals, followed by the same browser feature encoder. Previously usable sequences are retained. `dense_extract.py` preserves the detector thresholds and encoding rules. `HANDSPEAK_EXPERIMENT_DIR=/opt/handspeak-training/vocabulary-v8` directs `fit.py` to the recovered development set. After models are frozen, `evaluate_dense.py` retries failed test tracking and compares complete pipelines on the same previously evaluated recordings. This is regression evidence, not a new independent test set.

`balanced_refine.py` and `balanced_core.py` expand negative-label coverage and select recall improvements under paired validation error limits. Their frozen candidates are checked by `evaluate_balanced.py` and `evaluate_balanced_core.py`. No replacement was selected. The `publish.py` and selection scripts stage research candidates for testing, not automatic production approval; the final public index is intentionally empty after the failed automatic-capture check.
