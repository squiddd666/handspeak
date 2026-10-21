# Similar project and dataset review

Reviewed 2026-10-21 for HandSpeak's isolated webcam recognition, especially
HELLO, DRINK, BOOK, HUNGRY, HOME, and FISH.

## Recommended sources

### 1. ASL Citizen

- Best dataset fit for HandSpeak's webcam use case: 83,399 consented recordings,
  2,731 isolated signs, 52 Deaf or hard-of-hearing signers, and signer-independent
  train/validation/test splits.
- The local metadata contains every priority label. The existing targeted pilot
  already showed that public-dataset accuracy does not automatically transfer to
  the site's camera pipeline, so additional HandSpeak-format calibration examples
  and an untouched signer split are still required.
- Microsoft publishes MIT-licensed I3D and ST-GCN baseline code and checkpoints.
- Dataset use is research-oriented; contact Microsoft before commercial use.
- Use: source training clips and compare an upper-body-plus-hands temporal model.
  Do not concatenate isolated clips and claim continuous ASL translation.

Sources:

- https://www.microsoft.com/en-us/research/project/asl-citizen/
- https://www.microsoft.com/en-us/research/project/asl-citizen/dataset-description/
- https://www.microsoft.com/en-us/research/project/asl-citizen/recommended-use/
- https://github.com/microsoft/ASL-citizen-code

### 2. H29-crypto/CAPSTONE_ASL

- Closest code-level match to HandSpeak. It uses MediaPipe pose and both hands,
  position/velocity/acceleration features, active-motion extraction, and a small
  temporal convolution classifier.
- The repository is MIT licensed and includes model weights plus a record-one-sign
  webcam demo.
- Its published top-100 ASL Citizen result is 68.85% top-1 on 777 test samples.
  The reported phase gain is only 0.90 percentage points and was not statistically
  significant, so phase labels should be treated as an experiment rather than a
  guaranteed accuracy fix.
- Use: adapt the feature and TCN design, then retrain and validate it on HandSpeak's
  own signer-separated manifests. Do not copy its reported accuracy into the UI.

Source: https://github.com/H29-crypto/CAPSTONE_ASL

### 3. khuranaradhika/asl-realtime

- MIT licensed and architecturally useful: MediaPipe hand landmarks, temporal
  CNN/LSTM/Transformer experiments, ONNX export, CPU benchmarking, webcam demo,
  and per-class evaluation.
- Its checked-in vocabulary includes all six priority words.
- Its own documentation reports only about 30% WLASL download yield and very sparse
  class evaluation. Checked-in target metrics include zero-correct examples for
  DRINK and BOOK in some small runs. Its weights are therefore not a safe release
  candidate for HandSpeak without independent testing.
- Use: reuse the ONNX export/latency and per-class report patterns. Do not deploy
  its weights directly.

Source: https://github.com/khuranaradhika/asl-realtime

### 4. OpenHands

- Apache-2.0 code for pose-based isolated recognition, pretrained models, and
  standardized metadata for WLASL and MS-ASL. Its metadata covers all six priority
  labels.
- It is a Python research framework and is no longer actively maintained. It is
  useful for server-side experiments and architecture comparison, not as a direct
  browser module.
- Dataset licenses remain separate from the Apache code license.

Sources:

- https://github.com/AI4Bharat/OpenHands
- https://arxiv.org/abs/2110.05877

## Sources with restrictions or unresolved licensing

### WLASL

- Covers 2,000 signs and includes the six target labels in local metadata.
- Licensed under C-UDA for academic/computational use; the project explicitly says
  no commercial use. Many original video links have expired.
- Use only for capstone research and evaluation under its terms. Do not redistribute
  videos through the website.

Source: https://github.com/krazyjoy/WLASL/blob/main/index.md

### SignBart

- Interesting sub-750K-parameter pose architecture with reported WLASL and ASL
  Citizen results and downloadable checkpoints.
- The checked repository has no license file. Without explicit permission, do not
  copy its code or ship its weights. The paper/design can still guide an independent
  implementation.

Source: https://github.com/TinhNguyen2312/SignBart

## Recommended HandSpeak experiment

1. Keep the current HELLO fallback and production models unchanged during research.
2. Implement an original compact temporal model using the MIT capstone's general
   design: upper-body-relative hand coordinates, velocity, acceleration, automatic
   active-region cropping, and a small TCN.
3. Train only the six weak words first, plus the existing supported vocabulary and
   ordinary-motion/unsupported-sign negatives. Use ASL Citizen training signers and
   retain its signer-independent validation/test divisions.
4. Calibrate rejection using negative movements. Evaluate correct recognition,
   false acceptance, missed signs, and browser latency separately.
5. Export the passing model to ONNX or a small JSON inference format and run parity
   tests against the Python model.
6. Test real Android and desktop camera timing. Publish a word only if it passes the
   existing per-word release gates and does not increase false matches.

This review identifies reusable sources; it does not establish that any external
checkpoint is accurate on HandSpeak's live camera domain.
