# HandSpeak Web

HandSpeak Web is a browser-based capstone prototype that recognizes selected static American Sign Language (ASL) gestures and converts them into readable text.

## Features

- Real-time, on-device hand landmark detection using MediaPipe
- Pretrained weighted k-nearest-neighbor recognition for A, B, I, L, V, W, and Y
- Rule-based recognition for 5, plus personal training in AI Studio
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

This prototype recognizes a small set of static hand shapes using a pretrained landmark classifier, personal samples, and fallback landmark heuristics. It is not a complete ASL translator: it does not interpret ASL grammar, movement-based signs, facial expressions, or body posture. Similar hand shapes and side-on poses may be misclassified. A production version should use a diverse, validated training dataset and evaluation with Deaf/Hard-of-Hearing users and qualified sign-language experts.

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
Digit 5 is not in the alphabet training set and retains its existing rule until taught.

Source: [Marxulia/asl_sign_languages_alphabets_v03](https://huggingface.co/datasets/Marxulia/asl_sign_languages_alphabets_v03),
revision `1adf43b2d31eb9d7aea5855edaeac0231d8a2757`.
The source dataset card did not specify a license at download time; redistribution
and commercial permissions have not been established. Raw images are not bundled.

`training/train_asl.py` extracts the same 21 MediaPipe landmarks and wrist/palm/rotation
normalization used in the browser. kNN training stores labeled reference examples;
it does not fit neural-network weights. Exact duplicate decoded images are removed
before an 80/20 stratified split (seed 42). Test examples are excluded from the model.
`models/asl-evaluation.json` records counts, detection failures, confusion matrix,
accuracy including rejected predictions, coverage, and accepted-prediction accuracy.
These are image-holdout results, not signer-independent or live-camera results:
signer identities are unavailable and near-duplicate photos may remain. Evaluation
measures the pretrained classifier alone, without the app's fallback gesture rules.
Neighbor confidence is an agreement score, not a calibrated probability.

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
