# Public five-word preview

At the user’s explicit request, NAME, HOME, HAVE, WANT and LOVE are available to guests and signed-in users as an experimental server recognition preview. No administrator account or personal training is needed. This supersedes the earlier administrator-only deployment.

The model and rejection settings are unchanged. The displayed recorded result remains 44/66 requested-word clips correct and 2/48 unsupported signs falsely accepted. Making the preview public does not demonstrate improved accuracy or validate automatic continuous recognition.

Word cards and the learning catalog open the preview. Users explicitly enable sending hand-landmark coordinates and manually record a sign; video stays on the device. Results are added only after Add reviewed word. The endpoint checks the existing same-origin protections, explicit consent, shape/finite-value validation, a per-IP limit of 12 attempts per minute, and a single concurrent inference limit. Only short-lived hashed client identifiers and counters are kept for throttling; input landmark sequences are not persisted.

The public service returns only a possible word label or no reliable match. Dataset recordings, trained templates, and private model files remain outside the served website. Other administrator endpoints retain their authorization checks. The standard on-device recognizer remains the default.

Validation: 16 application/API tests, four training/rate-limit tests, and staging browser checks for guest access, catalog/card navigation, manual recording, explicit acceptance, cancellation, mode reset, and mobile layout. Browser capture checks use a controlled detector-frame fixture and do not establish physical-webcam accuracy.
