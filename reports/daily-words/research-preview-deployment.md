> Superseded by [public preview deployment](public-preview-deployment.md): the user subsequently requested guest access.

# Private research preview deployment

The user explicitly requested applying the trained model after the failed evaluation was reported. The frozen five-word DTW model is therefore integrated as an opt-in **administrator-only private research preview**, not promoted to the default recognizer or described as reliable.

NAME, HOME, HAVE, WANT, LOVE: 44/66 requested-word clips matched; 2/48 unsupported-sign clips were falsely accepted. These are whole-clip research checks, not live-camera accuracy. Both the evaluation failure and restricted mode are displayed beside the control.

The standard browser pipeline stays the default. A checked disclosure enables server processing only for an explicitly started recording. Only the browser-encoded 20-frame hand-landmark sequence is sent, never video, and input coordinates are not persisted. Administrator authorization and explicit consent are required by the endpoint. One request is processed at a time. All suggestions require the separate Add reviewed word button; the research mode does not automatically add or speak words.

The private model stays outside the served website. Dataset recordings, landmarks and models are not exposed as downloadable assets. API responses contain only a possible label or no reliable match. Model hash verification prevents silently substituting another artifact. This restricted integration is for the owner's noncommercial research use; it is not a public dataset/model release.

Validation: 75 application tests; exact serving-output parity on all 100 usable frozen test sequences; malformed-input and concurrency rejection; authenticated browser tests for opt-in, manual capture, explicit acceptance, cancellation, mobile layout and mode reset. Browser capture checks use cached detector frames, not a physical camera. The serving implementation averaged approximately 136 ms per recorded sequence in the parity run; camera capture and network time are additional.

Use: sign in as administrator, select Words in motion, enable Private research, start the camera and choose Record research word. Verify the result before Add reviewed word and Speak message.

Live verification: service active; website and health endpoint respond; research API rejects unauthenticated access; model and Python source paths return 404. Inference was checked under the production service account. Public page has no JavaScript errors and starts in static-letter mode.
