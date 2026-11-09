# Body-manual runtime candidate — offline only

`body_manual_runtime.mjs` ports the existing `body-manual-aspect-v1` Python
representation, mirror, banded DTW distance, and frozen acceptance gates. It is
not imported by the application. It never accesses a camera, network, storage,
lesson label, or expected prediction.

The input is `{imageAspect: height / width, frames: [...]}`. Each real frame has
seven anatomical pose points and two independent 21-point hand slots; absent
hands remain null/empty. Pose indices are `[0, 2, 5, 11, 12, 13, 14]`. Hand depth
is wrist-relative and must not be centered together with pose depth. Inputs are
copied; no hand positions or missing frames are invented.

## Verification completed

The frozen v5 body-manual candidate returned identical JavaScript/Python
predictions on all 228 validation recordings, including rejections. Maximum
feature difference was `2.384185791015625e-7`; maximum selected-distance
difference was `3.702642423220048e-8`. Scalar evidence is saved in
`reports/motion-repair-v6-20261107/body-runtime-validation-parity.json`.
Raw landmarks only crossed the local subprocess pipe; they were not added to
that report. Training, held-out recordings, and Watch clips were not used to
select or adjust gates in this verification.

**This is math parity, not browser capture parity or recognition accuracy.**
The known v5 NO regression is not fixed, and the model is not approved for
installation.

## Before browser integration or promotion

1. Preserve actual Holistic body and Tasks VIDEO manual hand streams separately,
   with their original same-source timestamps. Do not substitute recovered body
   hands into the old manual model's input or vice versa.
2. Verify cancellation, missing frames, anatomical slots, aspect units, and the
   real browser capture contract. Unit tests alone do not establish that parity.
3. Make any new training or routing selections on train/validation only.
4. Audit the newly frozen candidate against a fresh, untouched source/signer
   cohort, counting every miss and unsupported-sign false acceptance. The old
   v5 held-out results cannot be reused as a new independent release audit.
5. Complete a durable 198-reference browser regression without aggregating
   best-of retries. Reference checks are still not live-user accuracy.
