# Motion vocabulary evaluation, 2026-10-02 (Asia/Manila)

The requested library contains 200 unique entries in 15 categories. PopSign v1.0 archives supplied recordings for 49 requested labels. One label, BED, had fewer than three usable training examples in the first pass; 48 labels were trained in 14 separate research category models. All are withheld from the live website after failing accuracy and automatic-capture checks. Numbers and the remaining requested signs are learning/personal-training entries, not pretrained detections.

973 selected recordings: 585 training, 194 validation, 194 test. Training/validation/test signer sets are disjoint. The first pass obtained 423 usable training sequences and 130 usable validation sequences. Tracking failures are counted in evaluation denominators. Raw recordings remain outside the served website.

The first frozen category models matched **46/190 clips for their 48 trained labels**, with one wrong supported-word label and 143 misses. Counting the four untrained BED clips as misses gives **46/194** over all 49 downloaded requested labels. There were **116 false suggestions across 2,778 out-of-category evaluations**; this is a sum of repeated category/clip comparisons, not 2,778 distinct videos. These are whole-clip results, not real-camera accuracy. See `test-report.json` for per-category results.

## Additional attempts to improve accuracy

A validation-only feature experiment separated local hand shape from wrist movement and optionally normalized palm scale per frame. Five categories improved validation recall without more wrong suggestions. On the already-inspected regression clips, none improved correct recognition without increasing unsupported false suggestions. These refinements were **not promoted**. See `refinement/validation.json` and `refinement/regression.json`.

A separate six-word retraining experiment used up to 144 positive training references and 48 out-of-vocabulary references. It reduced validation unsupported false suggestions from 20/74 to 1/74, but correct supported matches fell from 47/84 to 32/84. This fails the recall requirement and **does not replace the default model**. No reserved test tuning or promotion was performed for it.

Most failed development clips had only 1–7 usable hand frames (196 of 226 failures). A separate dense-frame recovery experiment retries those original recordings at up to 60 sampled frames; see the v8 report for its outcome. It does not lower rejection thresholds or invent training samples from duplicated landmarks.

## Limits

This is an experimental collection of isolated-word recognizers. It is not continuous ASL translation, medical/emergency recognition, identity recognition, or validated emotion recognition. No high-accuracy claim is supported. There is no ordinary non-sign movement benchmark or physical webcam/user-signing evaluation. Existing negative regression clips were reused and are explicitly identified in the protocol.

Practice videos come from training recordings and are not independent evidence of recognition performance. Source attribution and transformations are in `media/signs/README.md` and `media/signs/catalog-sources.json`.


**Final sampling audit:** the initial recovery worker temporally upsampled some short clips. Its recovery counts and v8/v9 results are archived diagnostics, not evidence of improved accuracy. See [sampling issue and correction](../vocabulary-v9/SAMPLING-ISSUE.md). The new category models remain withheld.
