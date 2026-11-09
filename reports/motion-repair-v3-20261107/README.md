# Full-handshape retraining and third frozen recognition release

## Implemented

* Trained separate lightweight temporal auxiliary classifiers for Beginner-79 and full-100, each for 55 epochs. Saved the best train/validation-only objective checkpoint.
* Preserved the existing ST-GCN checkpoints and added 21-point wrist-relative XYZ handshape, body-relative wrists, seven body landmarks, and explicit missing-hand masks. Pose depth is never mixed with hand depth.
* Included training-only aspect/crop/sparse-sampling/noise/hand-loss augmentation, anatomical mirror averaging, and an explicit unsupported-sign class. Unknown probability mass is retained for rejection and never emitted as a word.
* Selected fusion weights and gates only on validation. Both known-word errors and unsupported accepts must stay within v2 validation budgets; class relaxations require at least three correct validation examples.
* Source/signers are disjoint across train/validation/test. Primary Watch videos are excluded from fitting and independent audits. Synthetic joined GOOD greetings remain explicitly synthetic.
* Auxiliary digests, label maps, preprocessing, and gates are tied together; mismatches fail closed. Preserved v2 weights/configuration/benchmarks. Published honest current recorded counts.
* Small default/pack/daily template recognizers were not retrained: their available data are separate and insufficient to validate a common body-handshape model. Their failures remain visible.

## All 198 reference regressions

* v2: **109 matched / 9 wrong / 80 no match**.
* v3: **127 matched / 10 wrong / 61 no match**.
* Completed reference playback: 197/198; insufficient tracking: 10.
* Exactly one normal-speed primary-reference attempt per word, using visible Watch → Practice → Record controls in the isolated in-page virtual camera. No practice-label override, user-history writes, or physical camera/microphone calls.
* These are reference regressions, not independent live-camera accuracy. All remaining failures and regressions are retained below.

## Frozen independent recording audit

| Route | Attempts | v2 correct / wrong / no match | v3 correct / wrong / no match | Unsupported accepts: v2 → v3 |
|---|---:|---|---|---|
| beginner / full | 747 | 394 / 23 / 330 | 502 / 28 / 217 | 174 → 87 / 1166 |
| capstone / full | 1206 | 515 / 30 / 661 | 633 / 29 / 544 | 103 → 42 / 689 |
| capstone / core | 89 | 55 / 0 / 34 | 55 / 0 / 34 | 103 → 103 / 1806 |
| capstone / extended | 261 | 168 / 2 / 91 | 172 / 2 / 87 | 92 → 31 / 1634 |

**Not every metric improves:** Beginner independent coverage improves substantially, but accepted wrong named signs increase from 23 to 28. Full-100 wrong signs decrease from 30 to 29. Unsupported accepts decrease in both. Settings were not retuned on these test results.

## Remaining reference failures

| Word | Route | Actual output | Outcome | Reason |
|---|---|---|---|---|
| AFTER | beginner | — | no match | Not enough tracked frames (4/5). |
| ANGRY | beginner | — | no match | ambiguous |
| APPLE | capstone/full | — | no match | ambiguous |
| ARTICULATESIGN | capstone/full | — | no match | ambiguous |
| BEE | capstone/full | — | no match | ambiguous |
| BEFORE | beginner | SCHOOL | wrong prediction | Possible match: SCHOOL. Top five: 1. SCHOOL · 2. YOUR / YOURS · 3. GOOD MORNING · 4. MONEY · 5. GOOD AFTERNOON. Verify before adding. |
| BREAKFAST | capstone/full | — | no match | ambiguous |
| BROTHER | beginner | — | no match | ambiguous |
| CALENDAR | capstone/full | — | no match | ambiguous |
| CANCER | capstone/full | — | no match | ambiguous |
| CATAPULT | capstone/full | — | no match | ambiguous |
| CEMETERY | capstone/full | — | no match | ambiguous |
| CHEESEGRATER | capstone/full | — | no match | ambiguous |
| CHILD | beginner | — | no match | Not enough tracked frames (3/5). |
| CLOTHES | beginner | — | no match | outside-vocabulary |
| COMB | capstone/full | — | no match | ambiguous |
| DECIDE | capstone/full | — | no match | ambiguous |
| DEVELOP | capstone/full | — | no match | ambiguous |
| DOG | capstone/full | — | no match | ambiguous |
| ERUPT | capstone/full | — | no match | ambiguous |
| FAMILY | beginner | — | no match | ambiguous |
| FINE | capstone/full | — | no match | ambiguous |
| FRIEND | beginner | — | no match | Not enough tracked frames (4/5). |
| GIVE | beginner | — | no match | ambiguous |
| GO | motion-manual | — | no match | Not enough clear hand tracking: hands visible in 8/34 frames. Keep your hands fully in view and use front lighting. |
| HAPPY | beginner | MY / MINE | wrong prediction | Possible match: MY / MINE. Top five: 1. MY / MINE · 2. HAPPY · 3. WELCOME · 4. BAD · 5. BREAD. Verify before adding. |
| HAVE | daily-manual | HOME | wrong prediction | Possible match: HOME. Check the word, then choose Add reviewed word. |
| HE / SHE | beginner | — | no match | ambiguous |
| HELLO | motion-manual | FOOD | wrong prediction | Possible match: “FOOD”. Check it before adding it to your message. |
| HOME | daily-manual | — | no match | Not enough clear hand tracking. Keep your hands in view and record again. |
| HOPE | capstone/full | — | no match | ambiguous |
| HOW | capstone/full | — | no match | ambiguous |
| HURDLE / TRIP | capstone/full | — | no match | ambiguous |
| JOKE | capstone/full | — | no match | ambiguous |
| KNIGHT | capstone/full | — | no match | ambiguous |
| LATER | beginner | — | no match | outside-vocabulary |
| LETTUCE | capstone/full | — | no match | ambiguous |
| MEACULPA | capstone/full | — | no match | ambiguous |
| MORNING | beginner | — | no match | ambiguous |
| MOUTH | capstone/full | — | no match | outside-vocabulary |
| MOVIE | capstone/full | DEVELOP1 | wrong prediction | Possible match: DEVELOP. Top five (100-word full): 1. DEVELOP · 2. MOVIE · 3. ELEVATOR · 4. CLOSE · 5. 8HOUR. Verify before adding. |
| NEED | beginner | — | no match | Not enough tracked frames (4/5). |
| NOON | capstone/full | — | no match | ambiguous |
| NOW | beginner | — | no match | ambiguous |
| OFFEND | capstone/full | — | no match | ambiguous |
| PAIN | motion-manual | NIGHT | wrong prediction | Possible match: “NIGHT”. Check it before adding it to your message. |
| PATIENT | capstone/full | — | no match | low-score |
| PHONE | beginner | — | no match | low-score |
| PONDER | capstone/full | — | no match | ambiguous |
| PRESS | capstone/full | — | no match | ambiguous |
| RAZOR | capstone/full | — | no match | ambiguous |
| RIVER | capstone/full | — | no match | ambiguous |
| SAD | beginner | WAIT | wrong prediction | Possible match: WAIT. Top five: 1. WAIT · 2. SAD · 3. WHAT · 4. SCARED · 5. AFTER. Verify before adding. |
| SCHOOL | beginner | THEY | wrong prediction | Possible match: THEY. Top five: 1. THEY · 2. SCHOOL · 3. TIME · 4. HOSPITAL · 5. WHO. Verify before adding. |
| SHAVE | capstone/full | — | no match | ambiguous |
| SINCE | capstone/full | — | no match | Not enough tracked frames (4/5). Keep your upper body and at least one hand visible. |
| SINK | capstone/full | — | no match | ambiguous |
| SISTER | beginner | — | no match | outside-vocabulary |
| SLIDE | capstone/full | — | no match | ambiguous |
| STORE | beginner | WALK | wrong prediction | Possible match: WALK. Top five: 1. WALK · 2. STORE · 3. STAND · 4. YESTERDAY · 5. INSIDE. Verify before adding. |
| STUDENT | beginner | — | no match | ambiguous |
| TAIL | capstone/full | — | no match | ambiguous |
| TAKE | beginner | — | no match | Not enough tracked frames (3/5). |
| THANK YOU | motion-manual | PLEASE | wrong prediction | Possible match: “PLEASE”. Check it before adding it to your message. |
| THIRD | capstone/full | — | no match | Not enough tracked frames (3/5). Keep your upper body and at least one hand visible. |
| THIRSTY | beginner | — | no match | ambiguous |
| VOMIT | capstone/full | — | no match | ambiguous |
| WALK TIGHTROPE CL | capstone/full | — | no match | ambiguous |
| WE | beginner | — | no match | Not enough tracked frames (4/5). |
| WHY | beginner | — | no match | ambiguous |
| YESTERDAY | beginner | — | no match | ambiguous |

## Evidence and next requirements

* `candidates/*.history.json`, `selection-*.json`, `frozen-selection.json`, and `calibration/` document fitting and selection before independent audits.
* `heldout-*.json` contains every independent attempted recording, including insufficient-tracking misses and unsupported signs.
* `virtual-final/final-all-198.json`, `virtual-final/summary.json`, and `repair-summary.json` retain all reference outcomes and before/after transitions.
* `pre-v3/` preserves configuration and published benchmarks for rollback; old weights remain unchanged.
* Tests: 175 frontend checks passed (2 platform skips), 47 targeted Python checks passed, and 12 active-runtime contract checks passed. The latter verify offline/server probability equality, ignored practice-label inputs, loaded identities, and blank-hand rejection. Test runs and scope are in `test-scope.json`. Broader legacy Python failures documented in v2 were not silently claimed fixed.
* Remaining manual-model confusions need new independent signer recordings and validation negatives. Body-model failures still need more variants/tracking robustness. Lowering a threshold or returning the selected practice word is not a fix.
* Updated runtime: http://127.0.0.1:8003/#learn. Earlier servers retain older in-memory models; use the new port for this release.
* Local research use only; no public deployment, dataset redistribution, external biometric upload, or user-message modification.

## Original nine errors and regressions

* BEFORE: wrong → wrong (SCHOOL).
* HAPPY: wrong → wrong (MY / MINE).
* HAVE: wrong → wrong (HOME).
* HELLO: wrong → wrong (FOOD).
* HERE: wrong → matched (HERE).
* PAIN: wrong → wrong (NIGHT).
* SICK: wrong → matched (SICK).
* SINK: wrong → no match (no accepted word).
* THANK YOU: wrong → wrong (PLEASE).

SICK uses an unchanged manual model; its successful reference take does not establish a retraining fix. Manual results vary with tracking. All 12 previously matched words that regressed to no match are retained in `previous-match-regressions.json`. The 30 recovered matches minus these 12 regressions produce a net gain of 18. Incorrect outputs increased from 9 to 10; this is not advertised as a complete error fix.
