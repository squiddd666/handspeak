# Second motion-recognition repair and all-word verification

## Implemented

* Retrained the complete Beginner-79 checkpoint for 10 epochs with training-only aspect-ratio augmentation; selected using validation macro accuracy.
* Added predicted-class rejection gates only with at least three correct validation examples. Sparse classes retain the global policy. Each class keeps its global validation error/unsupported-sign budget.
* Retained the full-100 ensemble and applied validation-only recalibration; no test/practice target can select a label.
* Added same-frozen-frame full-image/pose-wrist crop hand recovery in a separate classic worker, isolated from Holistic WASM globals. Resting second hands do not trigger unnecessary recovery.
* Increased bounded real-frame sampling; cancellation releases snapshots/bitmaps and asynchronous recovery cannot enter another recording.
* Preserved previous weights, source/evidence, and archived accuracy counts. Published actual current counts, including zero-accuracy classes and tracking failures.

## All 198 reference checks

* Previous release: **84 matched / 9 wrong / 105 no match**.
* This release: **109 matched / 9 wrong / 80 no match**.
* Complete reference playback: 197/198. Insufficient-tracking misses: 4.
* Exactly one normal-speed primary-reference attempt per word through Watch → Practice → Record. No forced expected label, no adding reviewed text, no physical camera/microphone calls.
* These are previously seen reference-video regression results, **not independent or live-user accuracy**.

## Frozen independent extracted-recording audit

| Model / mode | Attempts | Prior correct / wrong / no match | Current correct / wrong / no match | Unsupported false accepts: prior → current |
|---|---:|---|---|---|
| beginner / full | 747 | 392 / 20 / 335 | 394 / 23 / 330 | 174 → 174 / 1166 |
| capstone / full | 1206 | 502 / 22 / 682 | 515 / 30 / 661 | 92 → 103 / 689 |
| capstone / core | 89 | 62 / 0 / 27 | 55 / 0 / 34 | 210 → 103 / 1806 |
| capstone / extended | 261 | 177 / 2 / 82 | 168 / 2 / 91 | 158 → 92 / 1634 |

**Mixed generalization:** validation improved, but the independent audit does not improve every metric. Beginner/full accept slightly more correct words but also more wrong words. Core/extended reject substantially more unsupported signs at the cost of some correct matches. Do not present this as all words being fixed or a universal accuracy improvement.

## Remaining incorrect and no-match words

| Word | Route | Actual output | Outcome | Reason |
|---|---|---|---|---|
| AFTER | beginner | — | no match | low-score |
| APPLE | capstone/full | — | no match | ambiguous |
| ARTICULATESIGN | capstone/full | — | no match | ambiguous |
| BAG | beginner | — | no match | low-score |
| BATHROOM | beginner | — | no match | low-score |
| BEE | capstone/full | — | no match | ambiguous |
| BEFORE | beginner | SCHOOL | wrong prediction | Possible match: SCHOOL. Top five: 1. SCHOOL · 2. YOUR / YOURS · 3. GOOD AFTERNOON · 4. AFTER · 5. MONEY. Verify before adding. |
| BREAD | beginner | — | no match | low-score |
| BREAKFAST | capstone/full | — | no match | ambiguous |
| BROTHER | beginner | — | no match | low-score |
| CALENDAR | capstone/full | — | no match | ambiguous |
| CANCER | capstone/full | — | no match | ambiguous |
| CAPTURE | capstone/full | — | no match | ambiguous |
| CATAPULT | capstone/full | — | no match | ambiguous |
| CEMETERY | capstone/full | — | no match | ambiguous |
| CHEEK | capstone/full | — | no match | ambiguous |
| CHEESEGRATER | capstone/full | — | no match | ambiguous |
| CHILD | beginner | — | no match | Not enough tracked frames (4/5). |
| CLOTHES | beginner | — | no match | low-score |
| COMB | capstone/full | — | no match | ambiguous |
| DECIDE | capstone/full | — | no match | ambiguous |
| ERUPT | capstone/full | — | no match | ambiguous |
| FINE | capstone/full | — | no match | ambiguous |
| FOREIGNER | capstone/full | — | no match | ambiguous |
| FRIEND | beginner | — | no match | low-score |
| GIVE | beginner | — | no match | low-score |
| GOOD MORNING | beginner | — | no match | low-score |
| GUESS | capstone/full | — | no match | Not enough tracked frames (4/5). Keep your upper body and at least one hand visible. |
| HAPPY | beginner | MY / MINE | wrong prediction | Possible match: MY / MINE. Top five: 1. MY / MINE · 2. HAPPY · 3. WELCOME · 4. BREAD · 5. GOOD. Verify before adding. |
| HAVE | daily-manual | HOME | wrong prediction | Possible match: HOME. Check the word, then choose Add reviewed word. |
| HE / SHE | beginner | — | no match | low-score |
| HELLO | motion-manual | DRINK | wrong prediction | Possible match: “DRINK”. Check it before adding it to your message. |
| HELP | beginner | — | no match | low-score |
| HERE | beginner | WHAT | wrong prediction | Possible match: WHAT. Top five: 1. WHAT · 2. HERE · 3. TODAY · 4. NOW · 5. HELP. Verify before adding. |
| HOME | daily-manual | — | no match | Not enough clear hand tracking. Keep your hands in view and record again. |
| HOPE | capstone/full | — | no match | ambiguous |
| HURDLE / TRIP | capstone/full | — | no match | ambiguous |
| LATER | beginner | — | no match | low-score |
| LETTUCE | capstone/full | — | no match | ambiguous |
| LUNCH | capstone/full | — | no match | ambiguous |
| MONEY | beginner | — | no match | low-score |
| MORNING | beginner | — | no match | low-score |
| MOVIE | capstone/full | — | no match | ambiguous |
| NEED | beginner | — | no match | Not enough tracked frames (2/5). |
| NOON | capstone/full | — | no match | ambiguous |
| NOW | beginner | — | no match | low-score |
| OKAY | beginner | — | no match | low-score |
| PAIN | motion-manual | NIGHT | wrong prediction | Possible match: “NIGHT”. Check it before adding it to your message. |
| PATIENT | capstone/full | — | no match | ambiguous |
| PHONE | beginner | — | no match | low-score |
| PONDER | capstone/full | — | no match | ambiguous |
| PRESS | capstone/full | — | no match | ambiguous |
| RAZOR | capstone/full | — | no match | ambiguous |
| RIVER | capstone/full | — | no match | ambiguous |
| SAD | beginner | — | no match | low-score |
| SCHOOL | beginner | — | no match | low-score |
| SCROLLDOWN | capstone/full | — | no match | ambiguous |
| SHAVE | capstone/full | — | no match | ambiguous |
| SHOCKED | capstone/full | — | no match | ambiguous |
| SICK | motion-manual | SEE | wrong prediction | Possible match: “SEE”. Check it before adding it to your message. |
| SINCE | capstone/full | — | no match | ambiguous |
| SINK | capstone/full | IMPOSSIBLE | wrong prediction | Possible match: IMPOSSIBLE. Top five (100-word full): 1. IMPOSSIBLE · 2. SINK · 3. VOMIT · 4. CALENDAR · 5. DEVELOP. Verify before adding. |
| SISTER | beginner | — | no match | low-score |
| SLEEP | beginner | — | no match | low-score |
| SLIDE | capstone/full | — | no match | ambiguous |
| STAND | beginner | — | no match | low-score |
| STORE | beginner | — | no match | low-score |
| STUDENT | beginner | — | no match | low-score |
| TAIL | capstone/full | — | no match | ambiguous |
| THANK YOU | motion-manual | PLEASE | wrong prediction | Possible match: “PLEASE”. Check it before adding it to your message. |
| THEY | capstone/full | — | no match | ambiguous |
| THIRD | capstone/full | — | no match | ambiguous |
| THIRSTY | beginner | — | no match | low-score |
| THIS | beginner | — | no match | low-score |
| TIRED | beginner | — | no match | low-score |
| TOMATO | capstone/full | — | no match | ambiguous |
| TOMORROW | beginner | — | no match | low-score |
| TRACTOR | capstone/full | — | no match | ambiguous |
| VOMIT | capstone/full | — | no match | ambiguous |
| WALK | beginner | — | no match | low-score |
| WALK TIGHTROPE CL | capstone/full | — | no match | ambiguous |
| WE | beginner | — | no match | low-score |
| WHAT | beginner | — | no match | low-score |
| WHERE | beginner | — | no match | low-score |
| WHO | beginner | — | no match | low-score |
| WHY | beginner | — | no match | low-score |
| WORK | beginner | — | no match | low-score |
| YESTERDAY | beginner | — | no match | low-score |
| YOU | beginner | — | no match | low-score |

## Evidence and limitations

* `selection.json`, training history, validation archives, and calibration audits freeze selection before independent evaluation.
* `virtual-final/final-all-198.json`, `virtual-final/summary.json`, and `repair-summary.json` retain every result and before/after transition.
* `heldout-*.json` excludes primary Watch references and checks disjoint source/signers. Synthetic GOOD greetings are not natural continuous phrase recordings.
* Tests: 175 frontend checks passed (2 platform skips), plus 48 targeted Python recognition/report checks. The broader Python suite is not all-passing: after installing the missing QuickJS dependency, it ran 126 tests with 8 failures and 3 errors in legacy/dependency/platform paths. See `test-scope.json` and `python-all-tests-with-dependencies.txt`; these were not hidden or described as passed.
* Remaining failures require diverse independent recordings and better tracking/model features. Lowering thresholds until a reference passes would inflate wrong predictions.
* Updated local runtime: http://127.0.0.1:8002/#learn. Port 8001 had a stale in-memory Beginner checkpoint; it was not counted as v2 verification.
* No public deployment, external biometric upload, or user history modification was performed. Research references remain localhost-only.
