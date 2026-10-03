# Motion vocabulary and sentence drafts

Four additions: FOOD, HUNGRY, LIKE, GO, with training references and CC BY 4.0 PopSign practice videos. Seven extra labels are opt-in, so the original six-word default model is unchanged. The preview’s new labels compete with prior words; it can produce extra false suggestions.

Sentence UI: opt-in automatic adding to a draft (no automatic speech), typed I/AM/YOU/WANT/TO/A buttons, remove-last-word, punctuation, and existing editing/speaking/saving. Each sign remains a separate movement with a pause; English grammar is not inferred.

## Recognition evidence

96 training clips selected, 59 usable reference sequences. 32 validation clips and 24 reserved new-word clips. Training and validation/test signers separate. Thresholds selected on validation only. See `protocol-note.txt` for the priority revision; no test-prediction-based tuning.

New-word test: FOOD 1/6, HUNGRY 2/6, LIKE 2/6, GO 0/6 (5/24 combined). Existing nine-word regression clips: 29/60 correct, 7 wrong, unchanged from the prior optional preview. Unsupported/synthetic false suggestions rose 24→26 out of 40. The expanded preview is **not promoted to default**.

Real-time virtual camera: first usable training video per new word played at normal speed through the camera pipeline on server CPU, face tracking off. All four automatic captures returned No match. No false words or repeats appeared. This is not a physical-webcam study; concurrent regression load affected timings. Manual recording and typed correction remain necessary fallbacks. See `realtime-cpu.json`.

## Application verification

Sentence spacing, punctuation, limit handling, optional adding, no automatic speech, and single confirmation are covered by regression checks. Browser checks passed sentence edits/save/delete, all four new video playback controls, preview activation, practice mode, and mobile fit, with no JavaScript page errors. The final full-suite result is `/opt/handspeak/live-test-results/sentence-final-tests.log`.

## Deployment result

Published to https://handspeak.cvsu.dev on 2026-10-01 UTC. All 64 final regression checks passed. Live browser tests passed sentence editing/save/delete, four new video playbacks, preview activation, and mobile fit with no JavaScript page errors. Temporary saved test messages were deleted. The release did not modify the database backend or the default six-word model.
