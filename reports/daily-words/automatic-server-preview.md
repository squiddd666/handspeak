# Automatic five-word server preview — 3 October 2026

The opt-in NAME/HOME/HAVE/WANT/LOVE preview now uses the same local movement-boundary detector as standard motion words. With Automatic words enabled, a complete captured landmark sequence is sent after the signer pauses. Manual recording remains available. This mode still replaces standard on-device recognition while enabled; it is not a unified 18-word classifier.

One request in flight, at least six seconds between automatic request starts, pause for unreviewed suggestions, and discard responses after cancellation/opt-out. The existing sentence-auto-add setting also applies when explicitly checked. Disabling Automatic words preserves manual operation. Hiding the tab cancels the capture/request. Coordinates remain processed in memory by the existing backend; no videos are uploaded.

Validation: isolated browser module checks for opt-in, automatic segmentation from cached detector frames, request serialization, review, cooldown, cancellation, and manual mode. A cached development NAME sequence with synthetic timing triggered an automatic request to the live server and returned NAME, with no automatic addition. This is not a real-time webcam accuracy measurement, and the frozen model/thresholds were not changed.

Deployment backup: /opt/handspeak/automatic-server-backup-20261003T061513Z.
