# Recorded-video and OBS evaluation scope

The user has existing videos and OBS, without new live-camera testers. Continue
training and evaluate that workflow. Do not describe these results as accuracy on
newly recruited people or as physical-webcam validation.

Before opening fresh evaluation recordings, freeze the checkpoint, feature code,
supported labels, thresholds and acceptance criteria. Reproduce development
validation and check browser parity. Keep evaluation recording hashes and signer
IDs separate from training and validation. Existing test signer populations have
appeared in prior research; disclose this even when recording filenames are new.

For real-time playback tests:

- Use automatic recognition, with actual browser media-frame timing. Cached
  landmarks with synthetic timestamps do not satisfy this check.
- Test the existing 960×720 workflow, correct aspect ratio with letterboxing,
  original and horizontally reversed video, and pause/restart behavior.
- Record every emitted suggestion, missed sign, wrong or unsupported suggestion,
  repeat and end-of-sign-to-result latency. Do not report only the final label.
- Include isolated words and sequences separated by natural pauses, and check the
  existing vocabulary for regressions alongside new words.
- Keep empty/no-hands footage separate from ordinary hand-movement negatives.
  Black padding or frozen frames do not replace annotated ordinary movements.
- Verify FINISH triggers sentence interpretation/speech only under the existing
  user settings and does not introduce duplicate interpretation requests.

Headless fake-camera playback may test the browser capture path and timing, but
does not reproduce OBS itself, its scaling settings, or a physical webcam. Label
each test environment precisely. No candidate is ready merely because software
tests pass or the model returns a plausible sentence.

The accuracy requirements remain unchanged: at least half of supported clips
correct, no wrong-word/other-sign accepts in the frozen screen, and at least one
correct example for every released target. A smaller tested vocabulary must be
reported explicitly; unsupported winners never fall back to another class.
