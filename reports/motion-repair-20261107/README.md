# Motion recognition repair and all-word audit

## What changed

* Buffered distinct camera frames across a busy tracker, excluded countdown frames, drained inference, and bounded temporary image memory.
* Fixed specialist/default routing and prevented empty-hand input from producing word predictions.
* Retrained Beginner-79 with corrected MORNING and synthetic joined greeting labels, masked missing hands, and anatomical mirror averaging.
* Retained the existing full-100 ensemble: the retrained candidate did not beat it on validation.
* Froze checkpoint-bound rejection gates on validation only; primary Watch references were excluded from independent held-out audits.
* Published exact current per-word results separately from the archived benchmarks, including 0% results and tracking misses.

## Independent held-out recordings

The same corrected test attempts are used in each before/after comparison. Known-word results and unsupported false accepts are separate. Tracking failures count as misses.

| Model / setting | Attempts | Before correct / wrong / no match | After correct / wrong / no match | Unsupported false accepts: before → after |
|---|---:|---|---|---|
| beginner / full | 747 | 308 / 40 / 399 | 392 / 20 / 335 | 166 → 174 / 1166 |
| capstone / full | 1206 | 692 / 234 / 280 | 502 / 22 / 682 | 589 → 92 / 689 |
| capstone / core | 89 | 61 / 0 / 28 | 62 / 0 / 27 | 229 → 210 / 1806 |
| capstone / extended | 261 | 160 / 0 / 101 | 177 / 2 / 82 | 222 → 158 / 1634 |

**Tradeoff:** the full-100 recalibration reduces wrong labels but increases refusals and reduces correct acceptances. It is not an across-the-board accuracy improvement. Beginner known-word performance improves, but its unsupported false-accept count rises slightly.

## All 198 Watch → Practice → Record checks

Exactly one normal-speed baseline attempt per label, using the same primary reference MP4s as the earlier run. No expected label was substituted, no reviewed word was added, and no physical webcam or microphone was activated.

* Before: **69 matched / 23 wrong / 106 no match**.
* After: **84 matched / 9 wrong / 105 no match**.
* Complete clip playback: 197/198. Insufficient-tracking misses: 27.
* This is a reference-video regression, not held-out accuracy and not evidence that all 198 words are ready.

## Remaining wrong/no-match reference words

| Expected word | Model setting | Actual output | Result | Rejection reason | Tracked frames |
|---|---|---|---|---|---:|
| AFTER | beginner | — | no match | — | — |
| ANGRY | beginner | — | no match | low-score | 7 |
| ANYONE | capstone/full | — | no match | ambiguous | 11 |
| APPLE | capstone/full | — | no match | ambiguous | 5 |
| ARTICULATESIGN | capstone/full | — | no match | ambiguous | 11 |
| BAG | beginner | — | no match | low-score | 11 |
| BATHROOM | beginner | — | no match | — | — |
| BEE | capstone/full | — | no match | — | — |
| BEFORE | beginner | — | no match | low-score | 13 |
| BELT | capstone/core | — | no match | — | — |
| BOOK | motion-manual | LIKE | wrong prediction | — | 7 |
| BREAD | beginner | — | no match | low-score | 11 |
| BREAKFAST | capstone/full | — | no match | ambiguous | 9 |
| BROTHER | beginner | — | no match | low-score | 5 |
| CALENDAR | capstone/full | — | no match | ambiguous | 9 |
| CANCER | capstone/full | — | no match | ambiguous | 15 |
| CAPTURE | capstone/full | — | no match | — | — |
| CATAPULT | capstone/full | MAPLE | wrong prediction | — | 6 |
| CEMETERY | capstone/full | — | no match | ambiguous | 8 |
| CHEEK | capstone/full | — | no match | ambiguous | 10 |
| CHEESEGRATER | capstone/full | — | no match | ambiguous | 18 |
| CHILD | beginner | — | no match | — | — |
| CHRISTMAS | capstone/full | — | no match | — | — |
| CLOTHES | beginner | — | no match | low-score | 7 |
| COMB | capstone/full | — | no match | ambiguous | 6 |
| DARK | capstone/full | — | no match | ambiguous | 7 |
| DEVELOP | capstone/full | — | no match | ambiguous | 6 |
| DINNER | capstone/full | — | no match | — | — |
| ERUPT | capstone/full | — | no match | ambiguous | 5 |
| EVERYONE | beginner | — | no match | low-score | 9 |
| FAMILY | beginner | — | no match | low-score | 5 |
| FATHER | beginner | — | no match | low-score | 9 |
| FINE | capstone/full | — | no match | ambiguous | 11 |
| FISH | motion-manual | SEE | wrong prediction | — | 6 |
| FOREIGNER | capstone/full | — | no match | — | — |
| FRIEND | beginner | — | no match | low-score | 5 |
| GIVE | beginner | — | no match | low-score | 7 |
| GOOD | beginner | — | no match | low-score | 5 |
| GOOD MORNING | beginner | — | no match | low-score | 11 |
| GOODBYE | beginner | — | no match | low-score | 6 |
| GUESS | capstone/full | — | no match | — | — |
| HALLOWEEN | capstone/full | — | no match | ambiguous | 8 |
| HAPPY | beginner | — | no match | low-score | 5 |
| HAVE | daily-manual | HOME | wrong prediction | — | 5 |
| HE / SHE | beginner | — | no match | low-score | 6 |
| HELLO | motion-manual | DRINK | wrong prediction | — | 20 |
| HELP | beginner | — | no match | low-score | 5 |
| HOPE | capstone/full | — | no match | — | — |
| HOW | capstone/full | — | no match | — | — |
| HUNGRY | motion-manual | THANK YOU | wrong prediction | — | 11 |
| HURDLE / TRIP | capstone/full | — | no match | ambiguous | 9 |
| I / ME | beginner | — | no match | low-score | 6 |
| INSIDE | beginner | — | no match | low-score | 7 |
| JOKE | capstone/full | — | no match | ambiguous | 8 |
| KNIGHT | capstone/full | — | no match | ambiguous | 7 |
| KNOW | beginner | — | no match | — | — |
| LATER | beginner | — | no match | low-score | 34 |
| LETTUCE | capstone/full | — | no match | — | — |
| LOCK | capstone/extended | — | no match | low-score | 7 |
| LUNCH | capstone/full | — | no match | ambiguous | 7 |
| MEACULPA | capstone/full | — | no match | — | — |
| MEAT | capstone/full | — | no match | ambiguous | 5 |
| MONEY | beginner | — | no match | low-score | 6 |
| MORNING | beginner | — | no match | low-score | 7 |
| MOUTH | capstone/full | — | no match | — | — |
| MOVIE | capstone/full | — | no match | ambiguous | 6 |
| NOON | capstone/full | — | no match | ambiguous | 5 |
| NOW | beginner | — | no match | low-score | 6 |
| OKAY | beginner | — | no match | — | — |
| PAIN | motion-manual | NIGHT | wrong prediction | — | 21 |
| PATIENT | capstone/full | — | no match | — | — |
| PHONE | beginner | — | no match | low-score | 7 |
| PIPE | capstone/full | — | no match | — | — |
| PONDER | capstone/full | — | no match | ambiguous | 10 |
| PRESS | capstone/full | — | no match | ambiguous | 5 |
| RAZOR | capstone/full | — | no match | ambiguous | 7 |
| RIVER | capstone/full | — | no match | ambiguous | 8 |
| RUN | beginner | — | no match | low-score | 8 |
| SAD | beginner | WAIT | wrong prediction | — | 6 |
| SCARED | beginner | — | no match | low-score | 5 |
| SCHOOL | beginner | — | no match | — | — |
| SCROLLDOWN | capstone/full | — | no match | ambiguous | 6 |
| SHAVE | capstone/full | — | no match | ambiguous | 8 |
| SINCE | capstone/full | — | no match | — | — |
| SINK | capstone/full | — | no match | ambiguous | 8 |
| SISTER | beginner | — | no match | low-score | 6 |
| SLEEP | beginner | — | no match | low-score | 5 |
| SLIDE | capstone/full | — | no match | ambiguous | 11 |
| STAND | beginner | — | no match | low-score | 8 |
| STOP | beginner | — | no match | low-score | 5 |
| STORE | beginner | — | no match | low-score | 6 |
| STUDENT | beginner | STAND | wrong prediction | — | 8 |
| TAIL | capstone/full | — | no match | ambiguous | 7 |
| TAKE | beginner | — | no match | low-score | 5 |
| TEACH | capstone/full | — | no match | ambiguous | 6 |
| TEACHER | beginner | — | no match | low-score | 5 |
| THEY | capstone/full | — | no match | ambiguous | 5 |
| THIRD | capstone/full | — | no match | — | — |
| THIRSTY | beginner | — | no match | low-score | 8 |
| THIS | beginner | — | no match | — | — |
| TIRED | beginner | — | no match | low-score | 5 |
| TOMATO | capstone/full | — | no match | — | — |
| TOMORROW | beginner | — | no match | low-score | 7 |
| TRACTOR | capstone/full | — | no match | ambiguous | 10 |
| TWINS | capstone/full | — | no match | — | — |
| WAIT | beginner | — | no match | — | — |
| WALK | beginner | — | no match | low-score | 7 |
| WALK TIGHTROPE CL | capstone/full | — | no match | ambiguous | 13 |
| WE | beginner | — | no match | low-score | 5 |
| WHAT | beginner | — | no match | low-score | 6 |
| WHERE | beginner | — | no match | low-score | 6 |
| WHO | beginner | — | no match | — | — |
| WHY | beginner | — | no match | low-score | 5 |
| YESTERDAY | beginner | — | no match | low-score | 9 |

## Evidence and access

* `heldout-beginner.json` and `heldout-capstone.json`: scalar per-record and per-label independent audits.
* `current-accuracy-provenance.json`: deployed hashes, calibration identity, source-report hashes, preserved archive confirmation.
* `virtual-final/final-all-198.json`, `virtual-final/summary.json`, and `virtual-final/README.md`: full virtual-camera evidence and all 198 per-word results.
* `repair-summary.json`: machine-readable comparison and remaining failure list.
* `server-*-status.json` and `server-contract-tests.json`: actual updated runtime and no-hands/consent rejection checks.
* Updated local project: http://127.0.0.1:8001/#learn. The pre-existing port-8000 process was left intact; the updated runtime uses port 8001.

## Limitations

* A single matching Watch reference does not prove reliable recognition of other signers.
* The full-100 gate deliberately trades fewer wrong outputs for more no matches; overall recall did not improve.
* Beginner unsupported false accepts increased from 166 to 174 in 1166 held-out attempts, despite fewer known-word errors.
* Synthetic GOOD greeting training does not verify natural continuous greeting recognition.
* Remaining failures need improved tracking or additional diverse, independently evaluated signing data, not forced expected-label outputs.
* Research videos are restricted to localhost non-commercial use and have not been publicly deployed.
