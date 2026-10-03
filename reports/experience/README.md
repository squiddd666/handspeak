# Recognition-first experience

The home screen explains supported-sign recognition, draft text, user review, and explicit speech. Start Signing scrolls to the recognition workspace and starts the camera, with the existing guard against duplicate camera starts. Navigation remains visible on mobile.

Word capture and acceptance controls are in the recognition workspace and shown in Words in motion mode. Personal gesture training and optional server-side LLM interpretation are in AI Studio. Learning videos and the catalog remain learning tools, separate from supported camera vocabulary.

Vocabulary tiers distinguish seven tested static letters, experimental moving-word models, and personal gestures. Static test results are not signer-independent or live-camera accuracy. No numeric camera confidence is shown: classifier agreement is not calibrated probability. Saved-session agreement remains explicitly labeled as not probability.

Validation: existing 72-test suite; targeted model and motion tests; staging catalog browser regression; desktop/mobile UX browser checks. Camera feedback is tested using controlled classifier states, not an accuracy evaluation with a physical webcam. No recognition model or threshold changed.

Run browser checks with `HANDSPEAK_TEST_URL=http://127.0.0.1:8002 python training/ux/check_browser.py` using the training environment with Playwright installed.
