# Isolated browser camera diagnostic

**Failed to produce a usable capture; not deployed.** This is development debugging
using training clips, not an independent accuracy test or a physical camera test.

The candidate needs synchronized hand and body landmarks. The current live app
has no upper-body pose extractor. This isolated harness uses Tasks Vision CPU
hands and CPU full-body pose on the same 640x480 letterboxed canvas. Video plays
at wall-clock speed, followed by a blank tail for automatic capture completion.
Model decisions keep all 57 output classes and reject excluded winners.

CALL produced one tracked frame in the measured playback. HOME produced two.
Neither produced an encodable automatic capture. HOME's source-frame processing
median was about 496 ms while training competed for CPU. The approximately
160 ms overall median includes the easier blank tail and is not a camera FPS
estimate. Results include the warm-up and first playback separately.

These measurements describe this server's CPU browser, not the user's GPU or OBS
machine. The earlier legacy-Pose prototype also failed its timing check. Tasks
Pose and legacy Pose have matching large weight buffers, but complete landmark
output parity has not been established.

The optional 30 ms capture interval retains short visible gestures that the
80 ms default can undersample. Movement assessment keeps its original cadence.
The live application still uses the unchanged default; the prototype opts in.
27 capture tests passed. The browser temporal-window implementation also matched
Python on 102 generated/boundary fixtures, including disconnected runs and gaps.
These software checks do not demonstrate recognition accuracy.

Next steps: compare a hands-only model to avoid requiring a second live detector;
then test real-time capture, mirrored input, wrong suggestions, repeats, latency
and regressions before any deployment. Raw recordings remain outside the webroot.
