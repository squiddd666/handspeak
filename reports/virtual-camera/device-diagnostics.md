# Device diagnostics — 3 October 2026

The user still reports WATER rejection using OBS, with a visible hand outline. The vocabulary-preservation fix and one successful server-side virtual feed do not establish success on that device.

Added a local camera report with input dimensions, processed frame rate, current raw/usable hand counts, active vocabulary/model state, and last capture's total/tracked frames, duration (automatic capture), encoding validity and result. No coordinates, images, browser identity or account details are copied. The user must explicitly copy and share it.

Automatic rejection messages distinguish incomplete capture from a valid sequence rejected by the classifier. No classifier threshold, model, or training data changed. The prior successful recognition replay is a diagnostic, not an accuracy claim.
