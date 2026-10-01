# HandSpeak Web

HandSpeak Web is a browser-based capstone prototype that recognizes selected static American Sign Language (ASL) gestures and converts them into readable text.

## Features

- Real-time, on-device hand landmark detection using MediaPipe
- Pretrained weighted k-nearest-neighbor recognition for A, B, I, L, V, W, and Y
- Experimental pretrained moving-sign vocabulary: HELLO, THANK YOU, PLEASE, YES, NO, FINISH
- Optional personal training in AI Studio, including digit 5 after capturing examples
- Stable-sign filtering to reduce accidental input
- Message composition, copy, text-to-speech, and editing controls
- Built-in presentation demo when a camera is unavailable
- Responsive design, keyboard support, high-contrast mode, and reduced-motion support
- No video frames are uploaded or stored

## Run the complete system

Camera access requires a secure context. `localhost` is considered secure, so serve the folder instead of opening `index.html` directly.

```powershell
python server.py
```

Then open <http://localhost:8000> in Chrome or Edge and allow camera access. The first run needs an internet connection to download the MediaPipe runtime and hand-landmark model. The server creates `handspeak.db` automatically.

## Persistent system functions

- Saved translation sessions and detection details
- Gesture library delivered from the database
- Anonymous 5-point research evaluation questionnaire
- Aggregate accuracy, usability, performance, confidence, and latency metrics
- CSV session export for research analysis
- JSON API health check and validated server inputs

## Run automated tests

```powershell
python -m unittest discover -s training -v
```

## Recognition guidance

Use one hand, face your palm toward the camera, keep the hand inside the guide, and use even front lighting. Hold a sign steady for roughly one second. Lower the hand briefly before repeating the same character.

## Scope and limitations

This prototype recognizes selected static hand shapes and a small vocabulary of isolated moving signs, with rejection of uncertain matches. It is not a complete ASL translator: it does not interpret continuous signing, ASL grammar, facial grammar, or body posture. Similar hand shapes and side-on poses may be misclassified. A production version should use a diverse, validated training dataset and evaluation with Deaf/Hard-of-Hearing users and qualified sign-language experts.

## Project files

- `index.html` — semantic page structure
- `styles.css` — responsive visual design and accessibility modes
- `app.js` — camera, MediaPipe integration, recognition, and message tools
- `server.py` — HTTP server, validated JSON API, SQLite persistence, and CSV export
- `training/test_model.py` — pretrained model validation and browser-classifier integration tests

## Pretrained ASL model

The website automatically downloads `models/asl-knn.json` from this server. No personal
training is required to try its seven pretrained letters. AI Studio reports the loaded
reference count. Captured examples stay in browser localStorage and supplement the
reference set; resetting personal samples leaves the pretrained model intact.
Digit 5 is not in the alphabet training set and must be taught before use.
Uncertain predictions stay blank; no hand-shape rule overrides the learned model.

Source: [Marxulia/asl_sign_languages_alphabets_v03](https://huggingface.co/datasets/Marxulia/asl_sign_languages_alphabets_v03),
revision `1adf43b2d31eb9d7aea5855edaeac0231d8a2757`.
The source dataset card did not specify a license at download time; redistribution
and commercial permissions have not been established. Raw images are not bundled.

`training/train_asl.py` extracts the same 21 MediaPipe landmarks and wrist/palm/rotation
normalization used in the browser. kNN training stores labeled reference examples;
it does not fit neural-network weights. Exact duplicate decoded images are removed.
The original seed-42 20% image test is preserved; a seed-17 split reserves 20% of the
remaining images for validation. Reference training uses 1,463 images, validation
uses 367, and testing uses 456. Threshold selection uses validation only, minimizing
`5 * wrong predictions + rejections`. Neither validation nor test images enter the
reference model. The selected distance weights depth by 0.5, compares both mirrored
orientations, and uses three neighbors with distance, agreement, and class-separation
checks. This improves handling of handedness without duplicating training images.

On the same test images, the previous model gave 441 correct, 8 wrong, and 7 rejected
predictions. The revised model gives 425 correct, 1 wrong, and 30 rejected predictions:
99.77% correct among accepted predictions, 93.42% coverage, and 93.20% correct across
all test images. This is a deliberate reduction in wrong outputs at the cost of more
abstentions, not an improvement in overall recall. See `models/asl-evaluation.json`
for validation metrics, detection failures, and the confusion matrix.

These are image-holdout results, not signer-independent or live-camera results:
signer identities are unavailable and near-duplicate photos may remain. Images
without detected hands are excluded. There is no unsupported-sign test set and
personalized recognition has not been evaluated. Neighbor agreement is not a
calibrated probability. Camera processing skips duplicate video frames, rejects
clipped or very small hands, and pauses text entry during personal capture. Capture
locks the selected label and saves complete batches only; stopping the camera
cancels an incomplete batch.

To reproduce using Python 3.11 with MediaPipe 0.10.21, NumPy 1.26.4, PyArrow and Pillow:

```sh
python training/train_asl.py --cache /path/outside/website/asl-cache
# Additional test dependency: quickjs
python -m unittest discover -s training -v
```

On servers without graphics libraries, use `opencv-contrib-python-headless==4.11.0.86`
in place of `opencv-contrib-python`. Downloaded images and extraction caches should
remain outside the served website directory. The browser needs internet access for
its MediaPipe runtime/model on first use, but classification stays on-device.

## Words in motion (experimental)

The website automatically loads `models/asl-words.json`. No personal training is
required for **HELLO, THANK YOU, PLEASE, YES, NO, and FINISH**.

1. Select **Words in motion** and start the camera.
2. Leave **Automatic words** enabled (the default). Sign one supported word, then pause briefly.
3. A possible match appears over the camera. Review it and select **Add matched word** before adding it to the message.

Automatic capture keeps a short 350 ms lead-in, starts on hand movement, and
finishes after a 600 ms pause with at least 12 samples, or after 4.5 seconds.
It requires a quiet interval and cooldown before the next sign, avoiding repeated
suggestions from ongoing movement. Camera gaps and orientation changes discard
partial movements. This is experimental isolated-sign segmentation, not sentence
translation; it does not improve the classifier's measured accuracy.

**Record a word** remains available for a manual countdown and timed capture.
Disable Automatic words to use only manual recording. Face inference pauses
during active word capture to give hand tracking more processing time. Matches
are suggestions only: automatic capture never appends text or speaks by itself.

This is a nearest-template sequence classifier trained from a small subset of
[PopSign ASL v1.0](https://signdata.cc.gatech.edu/view/guides/downloading_popsign/index.html),
game category, CC BY 4.0. See `models/WORDS-SOURCE.md` for attribution.
It does not train a new neural network: MediaPipe supplies hand landmarks and
training builds labeled motion references. Up to two hands are tracked, leading
and trailing untracked frames are trimmed, and internal gaps of at most two frames
are interpolated. Coordinates are corrected for camera aspect ratio. Hand paths are centered over the full movement and normalized by palm width,
resampled to 20 frames, and compared using banded dynamic time warping. Matching
checks both mirrored orientations. A continuous run containing at least 70% of
usable frames can replace isolated entry/exit fragments; long disconnected runs
are not joined. Validation selects distance, class-separation, and neighbor-vote
cutoffs. Two nearby references must agree, unless the closest competing word is
at least 1.5 times farther away. The maximum-distance check still applies.

The source's train/validation/test partitions are preserved, with no overlapping
participant IDs. Validation selects rejection thresholds; test recordings never
enter the template library. DRINK is reserved as an unsupported-word check.
`models/asl-words-evaluation.json` reports counts, tracking failures, confusion,
and accuracy both with and without rejected predictions. `asl-words-sources.json`
records source archive members and SHA-256 hashes for audit/reproduction.
The revised v3 model contains 116 usable training examples. On 57 tracked test
clips, 38 predictions were correct, 4 wrong, and 15 rejected: 90.48% correct among
accepted matches, 73.68% coverage, and 66.67% correct including rejections. Another
15 of the 72 known-word test videos failed tracking/sequence checks, giving 38/72
correct over the complete selected known-word test set. The prior version gave
31/72 correct and also made 4 wrong predictions; its report is preserved in
`models/asl-words-evaluation-v2.json`. This is a regression comparison on previously
evaluated recordings, not a new independent benchmark. On validation, 26/31
tracked known-word clips were correct, none wrong, and five rejected.
Of 11 tracked unsupported DRINK test clips, 6 were incorrectly accepted and 5
rejected. This remains a significant limitation: rejection of signs outside the
vocabulary is unreliable.
The evaluation uses a small subset of isolated videos; it does not establish
live-camera or continuous-signing accuracy. Unsupported signs can still match a
known word. Distance is not a calibrated confidence probability. Review every
suggestion before adding it. Face/body/grammar/LLM interpretation is not used.

**Optional personalization:** Expand **Optional: add your own word examples**,
enter a label, and record at least three examples for a new word. Personal
recordings store coordinates only in `handspeak-motion-v3` in browser localStorage;
no video/audio is recorded or uploaded. The personal library allows 8 recordings
per word and 96 overall. Removing personal examples preserves pretrained words.
Personal examples supplement the references but have no evaluated accuracy.
Older `handspeak-motion-v1` and `handspeak-motion-v2` recordings are retained in
storage but not loaded because v3 changed movement centering and segmentation. They can be
re-recorded optionally; the pretrained vocabulary works without them.
Stopping the camera, changing modes, or Cancel discards an unfinished recording.
A fresh recording never adds text or speaks until the user confirms the match.
The standard Save button stores the confirmed message through the existing API;
motion similarity is not mixed into static-letter confidence statistics.

To rebuild the bundled vocabulary, use Python 3.11 with MediaPipe 0.10.21,
NumPy 1.26.4, SciPy, QuickJS, and OpenCV (headless is suitable on a server):

```sh
# Downloads selected original clips (~1.4 GB); keep this cache outside the website.
python training/download_words.py --cache /path/outside/website/popsign
python training/train_words.py --cache /path/outside/website/popsign --hand-model /path/outside/website/hand_landmarker.task
python training/fit_words.py --cache /path/outside/website/popsign
python -m unittest discover -s training -p 'test_*motion*.py' -v
python -m unittest discover -s training -p test_words.py -v
```

Extraction uses the same browser sequence encoding and reuses cached landmarks.
Exported models/evaluation files are written to `models/` in this checkout.
`motion-model.js` handles matching, `motion-studio.js` handles recording and
confirmation, and tests cover recording behavior, automatic model loading, source
split integrity, and exact Python/browser reserved-test prediction agreement.

`training/check_word_videos.py --videos /path/to/asl-examples` replays the five
provided MP4 examples through the actual browser MediaPipe hand detector, checks
video seeking, and resets tracking between clips. It requires Playwright/Chromium
and the website running on localhost:8000. Its clips were selected from training
recordings, so this is a functional integration check, not an accuracy benchmark.
Only the summary is bundled in `models/asl-words-browser-check.json`.

## Face tracking

The camera also loads MediaPipe Face Landmarker and draws one face's outline,
eye/lip contours, and sparse landmarks. Use the **Face tracking** checkbox under
the camera to turn it off or on. The visible status reports loading, readiness,
face presence, or unavailability. Face inference is limited to roughly 10 Hz to
leave processing time for hand tracking; GPU initialization falls back to CPU.
A face-model failure is contained and hand recognition continues. Runtime GPU
errors retry face tracking on CPU. If both paths fail, select **Retry face tracking**
or restart the camera. Hand inference errors no longer stop the face drawing loop.
The face outline uses a bright stroke, and detection uses MediaPipe's default 0.5
thresholds. The status gives framing guidance when no face is detected.

The camera also shows visible expression cues: Smiling, Mouth open, Brows raised,
and Brows lowered. These use MediaPipe blendshape coefficients with experimental
thresholds, smoothing, and a 300 ms stability check. They describe facial movements,
not happiness, sadness, anger, or a person's internal emotional state. No expression
accuracy benchmark is claimed. Missing faces, disabled tracking, and model errors
clear the previous cue. This feature does not recognize identity or change sign predictions. Face coordinates are never
saved, included in motion recordings, or sent to the server. The model and runtime
are downloaded on first use; frame processing stays in the browser. The existing
moving-sign recognizer still uses hands only.

Implementation: `face-tracker.js`. Model: Google's
[Face Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/web_js).
`training/test_face.py` covers throttling, toggle/reset behavior, CPU fallback,
and isolated loading/inference failures.

Slow word captures can extend by up to two seconds after the normal 2.5-second recording window to reach the existing 12-frame minimum. A stalled stream still times out; no frames are duplicated to pass the minimum. This does not guarantee word recognition.

The October 2026 accuracy experiment trained an additional temporal candidate. It remains evaluation-only: fresh whole-clip recognition improved, but automatic unsupported-sign suggestions increased. See `reports/accuracy-v4/README.md` in the Git checkout for the recorded results. Local application assets use a release query tag, and the server requests revalidation to avoid stale CDN code.
