# Browser capture recovery — 4 October 2026

These are development diagnostics on training recordings, not independent accuracy
or physical-webcam/OBS measurements. Main recognition remains unchanged.

## Fixed test-harness problems

The offline browser test previously drew a stale frame after seeking a file served
by the basic loopback HTTP server. Loading the complete video as a Blob and waiting
for a rendering frame after seeking recovered the actual moving hand. With fresh
browser extraction, CALL yielded 14 usable frames and the correct CALL result.
The original Python extraction had 13 tracked frames. This isolates a harness
loading/seeking problem; it does not prove a defect in actual camera input.

The real-time harness now resizes detector inputs, including portrait sources,
to a maximum dimension of 640 rather than accidentally passing the full
1944×2592 source video. Optional 960×720, 30 fps letterboxed derivatives model the
input dimensions previously reported for OBS. They remain private.

## Worker experiment

A classic worker is required because the pinned MediaPipe WASM loader uses
`importScripts`. A module worker failed initialization and was replaced.
Camera timestamps are retained while detection runs independently of frame capture.

- Main-thread, resized CALL playback: five usable hand frames, no valid capture.
- Worker with 30 ms capture: CALL recognized, but maximum backlog delay 6.78 s.
- Worker with 60 ms capture: CALL recognized, maximum delay 1.26 s.
- HOME and HUNGRY also matched in that isolated worker harness; NIGHT did not.

These timings include this server's software/browser limitations. They are not
promises of speed on another device. Black tails close captures and are not
ordinary-movement negative tests.

## Actual preview camera interface

`check_motion_preview_recording.py` feeds 960×720 recordings through
`canvas.captureStream` and the page's `getUserMedia` interface. This adds browser
stream/render overhead and does not emulate a physical sensor or OBS exactly.
Forcing SwiftShader made this fixture substantially slower; final checks use the
browser's default renderer and the preview selects CPU on detected software GPUs.

The preview worker captures at 80 ms while idle and 60 ms during a sign on CPU,
30 ms on a hardware GPU. The frame queue is bounded to 36 pending images and a
2.5-second age limit. Overload discards the pending capture, reports a pause/retry
message, and invalidates old worker responses. It never fabricates missing frames
or reduces the frozen model's acceptance thresholds.

Latest four-clip check: CALL and HOME each produced one correct suggestion with
no overflow during those clips. HUNGRY overflowed; NIGHT had only seven tracked
frames and was rejected. There were no wrong suggestions. This is debugging
coverage, not a release accuracy result. See the complete events in
`../motion-preview/camera-recordings.json`.
