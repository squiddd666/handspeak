# Guided recognition views — 3 October 2026

Published frontend improvements to https://handspeak.cvsu.dev.

- Hash-based Home, Recognition, Learn, AI Studio, History, Evaluation, and About views preserve existing in-memory application state. Links and browser back/forward reveal the relevant view before scrolling.
- Eighteen-word selector prepares the existing model group. Preparing NAME, HOME, HAVE, WANT, or LOVE does not opt into server landmark processing; the existing checkbox remains explicit.
- Shared lesson player appears beside the camera on wide screens, stacked on smaller screens. Instructions distinguish standard automatic capture, five-word manual capture, and learning-only entries. Videos stop when leaving a view.
- Removed misleading hand emojis; retained written descriptions and linked ASL University alphabet reference. No new hand illustrations were generated or represented as verified.
- Larger supporting text, revised camera layout, five-word per-label result table, unsupported-sign false accepts, missed clips, test limitations, and frozen model identity.
- Existing LLM original/suggestion comparison moved next to draft review and speech. Applying or speaking a suggestion remains explicit.

Validation: 17 model/sentence regression tests passed. Browser checks cover focused views, back navigation, direct links, model-group preparation, explicit server opt-in, lesson handoff, retained draft, and all seven views at 390px. No physical webcam or new model-accuracy evaluation was performed. Model and dataset files are unchanged; higher recognition accuracy is not demonstrated by this interface update.

Deployment backup: /opt/handspeak/guided-ux-backup-20261003T051008Z.
