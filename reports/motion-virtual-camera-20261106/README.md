# Motion virtual-camera clip tests

**198/198 labels tested at normal speed:** 69 matched, 23 wrong predictions, 106 no matches (**34.8% reference matches**).

These are reference-video smoke tests, **not independent held-out or live-user accuracy**.
All 198 recognition labels now have separately sourced recorded benchmark badges; that is measurement coverage, not proof that every word recognizes reliably.

Virtual stream calls: 2. Physical camera calls: **0**. Microphone calls: **0**.
Excluded warm-ups: 2. Insufficient-tracking misses: 79.
Complete primary-clip playback: 189/198; the application's fixed capture window can truncate longer clips.

## Per-model results

| Actual capture route | Tested | Matched | Wrong | No match |
|---|---:|---:|---:|---:|
| beginner | 76 | 15 | 1 | 60 |
| capstone/core | 7 | 3 | 0 | 4 |
| capstone/extended | 12 | 9 | 0 | 3 |
| capstone/full | 79 | 26 | 16 | 37 |
| daily-manual | 5 | 3 | 1 | 1 |
| motion-manual | 19 | 13 | 5 | 1 |

## Post-fix camera-badge checks

The displayed badge follows the **actual predicted label and model family**, not the expected reference word. The six checked contexts cover full-100, Beginner-79, default, daily, the active category pack, and core-7. Numeric-input replays produced wrong predictions and remain failures in the separate regression report; they are not counted as successful numeric detections. The I / ME slash-label detection displayed its Beginner benchmark. Known numeric/slash output-label handling is also covered by the no-camera unit tests.

| Expected reference | Actual prediction | Badge profile | Visible recorded result |
|---|---|---|---|
| 8HOUR | SOCCER2 | capstoneFull | Recorded accuracy: 72.7% (8/11 clips) · Full 100-word ST-GCN ensemble · recorded benchmark |
| I / ME | I / ME | beginner | Recorded accuracy: 63.6% (7/11 clips) · Beginner-79 ST-GCN need79-v1 · recorded benchmark |
| HELLO | FINISH | default | Recorded accuracy: 58.3% (7/12 clips) · Default six-word model with per-word distance cutoffs |
| NAME | NAME | daily | Recorded accuracy: 72.7% (8/11 clips) · Five-word server preview |
| SEE | SEE | active category pack | Recorded accuracy: 100% (3/3 clips) · Pack words (DTW) preview |
| PEG | PEG2 | capstoneCore | Recorded accuracy: 87.5% (7/8 clips) · Core 7-word ST-GCN · recorded benchmark |

## Final project page

198/198 recognition labels have reference videos available here · 147 local research clips added. Recognition models remain separate; all 198 cannot be active as one vocabulary.

198 of 198 recognition labels have recorded test results. Separate-model benchmarks, not live-camera accuracy.

Verified in the normal project page, with the camera off. A screenshot is saved as watch-learn-updated.png. Disposable virtual-source fixtures are separate from index.html and excluded from Git.

## Limitations

* Reference clips are examples, not an independent test set. Some may overlap model inputs.
* A fixed application recording window can cut off longer clips; incomplete playback is reported, not silently excluded.
* Browser/hand-and-body tracking speed and sign variants can cause short clips to miss the tracking gate.
* Core/extended gates and the Beginner gate can refuse predictions; all refusals remain in the denominator.
* All 198 labels having archived recorded scores does not mean all 198 are verified-ready or active in one model.
* Post-fix camera-badge regressions are saved separately; they never replace this baseline or archived benchmark counts.

## Per-word results

| Expected | Capture route | Prediction | Result |
|---|---|---|---|
| 8HOUR | capstone/full | 8HOUR | matched |
| AFTER | beginner | — | no match |
| ANGRY | beginner | — | no match |
| ANYONE | capstone/full | ANYONE | matched |
| APPLE | capstone/full | — | no match |
| ARTICULATESIGN | capstone/full | HOPE | wrong prediction |
| AXE | capstone/full | SHARK1 | wrong prediction |
| BABY | motion-manual | PLEASE | wrong prediction |
| BACKPACK | capstone/full | — | no match |
| BAD | beginner | — | no match |
| BAG | beginner | BAG | matched |
| BASEBALLCAP | capstone/extended | BASEBALLCAP | matched |
| BASKETBALL | capstone/full | BASKETBALL1 | matched |
| BATHROOM | beginner | — | no match |
| BEE | capstone/full | BREAKFAST1 | wrong prediction |
| BEFORE | beginner | — | no match |
| BELT | capstone/core | — | no match |
| BITE | capstone/full | BITE1 | matched |
| BOOK | motion-manual | BOOK | matched |
| BREAD | beginner | BREAD | matched |
| BREAKFAST | capstone/full | BEE1 | wrong prediction |
| BROTHER | beginner | — | no match |
| CALENDAR | capstone/full | RIVER1 | wrong prediction |
| CANCER | capstone/full | BREAKFAST1 | wrong prediction |
| CAPTURE | capstone/full | — | no match |
| CATAPULT | capstone/full | — | no match |
| CEMETERY | capstone/full | — | no match |
| CHEEK | capstone/full | — | no match |
| CHEESEGRATER | capstone/full | — | no match |
| CHILD | beginner | — | no match |
| CHRISTMAS | capstone/full | CHRISTMAS1 | matched |
| CLOSE | capstone/full | — | no match |
| CLOTHES | beginner | — | no match |
| COMB | capstone/full | TEACH1 | wrong prediction |
| COME | beginner | — | no match |
| CONFUSED | capstone/full | CONFUSED1 | matched |
| DARK | capstone/full | DARK1 | matched |
| DEAF | capstone/extended | DEAF1 | matched |
| DECIDE | capstone/full | — | no match |
| DEMAND | capstone/extended | — | no match |
| DEVELOP | capstone/full | DEVELOP1 | matched |
| DINNER | capstone/full | DINNER1 | matched |
| DOG | capstone/full | — | no match |
| DOWNSIZE | capstone/full | DOWNSIZE1 | matched |
| DRAG | capstone/extended | DRAG1 | matched |
| DRINK | motion-manual | DRINK | matched |
| DUCK | capstone/extended | DUCK2 | matched |
| EAT | capstone/core | — | no match |
| EDIT | capstone/extended | EDIT1 | matched |
| ELEVATOR | capstone/full | ELEVATOR1 | matched |
| EMPTY | capstone/core | — | no match |
| ERUPT | capstone/full | — | no match |
| EVERYONE | beginner | — | no match |
| FAMILY | beginner | — | no match |
| FATHER | beginner | — | no match |
| FINE | capstone/full | DEAF1 | wrong prediction |
| FINISH | motion-manual | FINISH | matched |
| FISH | motion-manual | — | no match |
| FLOAT | capstone/full | FLOAT1 | matched |
| FOOD | motion-manual | FOOD | matched |
| FOREIGNER | capstone/full | — | no match |
| FRIEND | beginner | — | no match |
| GIVE | beginner | — | no match |
| GO | motion-manual | LIKE | wrong prediction |
| GOOD | beginner | GOOD | matched |
| GOOD AFTERNOON | beginner | — | no match |
| GOOD MORNING | beginner | GOOD | wrong prediction |
| GOOD NIGHT | beginner | — | no match |
| GOODBYE | beginner | — | no match |
| GRAMMAR | capstone/full | GRAMMAR | matched |
| GUESS | capstone/full | — | no match |
| HALLOWEEN | capstone/full | — | no match |
| HAPPY | beginner | — | no match |
| HAVE | daily-manual | HOME | wrong prediction |
| HE / SHE | beginner | — | no match |
| HELICOPTER | capstone/full | — | no match |
| HELLO | motion-manual | HELLO | matched |
| HELP | beginner | — | no match |
| HERE | beginner | HERE | matched |
| HOME | daily-manual | — | no match |
| HOPE | capstone/full | — | no match |
| HOSPITAL | capstone/full | HOSPITAL1 | matched |
| HOW | capstone/full | — | no match |
| HUNGRY | motion-manual | HUNGRY | matched |
| HURDLE / TRIP | capstone/full | WALK-TIGHTROPE-CL | wrong prediction |
| I / ME | beginner | I / ME | matched |
| IMPOSSIBLE | capstone/full | — | no match |
| INSIDE | beginner | — | no match |
| INTUITIVE | capstone/full | INTUITIVE | matched |
| JEWELRY | capstone/full | JEWELRY | matched |
| JOKE | capstone/full | MOUTH | wrong prediction |
| KNIGHT | capstone/full | LUNCH1 | wrong prediction |
| KNOW | beginner | — | no match |
| LATER | beginner | — | no match |
| LETTUCE | capstone/full | LETTUCE1 | matched |
| LIKE | motion-manual | LIKE | matched |
| LOCK | capstone/extended | — | no match |
| LOVE | daily-manual | LOVE | matched |
| LUNCH | capstone/full | — | no match |
| MAPLE | capstone/full | MAPLE | matched |
| MEACULPA | capstone/full | — | no match |
| MEAT | capstone/full | — | no match |
| MECHANIC | capstone/extended | MECHANIC1 | matched |
| MICROSCOPE | capstone/extended | — | no match |
| MILK | beginner | — | no match |
| MONEY | beginner | — | no match |
| MORNING | beginner | — | no match |
| MOTHER | beginner | MOTHER | matched |
| MOUTH | capstone/full | — | no match |
| MOVIE | capstone/full | — | no match |
| MY / MINE | beginner | MY / MINE | matched |
| MYSELF | capstone/full | MYSELF | matched |
| NAME | daily-manual | NAME | matched |
| NEED | beginner | — | no match |
| NIGHT | motion-manual | NIGHT | matched |
| NO | motion-manual | NO | matched |
| NOON | capstone/full | — | no match |
| NOW | beginner | — | no match |
| OFFEND | capstone/full | — | no match |
| OKAY | beginner | — | no match |
| OTHER | capstone/extended | OTHER | matched |
| OUTSIDE | beginner | OUTSIDE | matched |
| PAIN | motion-manual | NIGHT | wrong prediction |
| PARTY | capstone/extended | PARTY1 | matched |
| PATIENT | capstone/full | — | no match |
| PEG | capstone/core | PEG2 | matched |
| PHONE | beginner | — | no match |
| PIPE | capstone/full | — | no match |
| PLEASE | motion-manual | PLEASE | matched |
| PONDER | capstone/full | LETTUCE1 | wrong prediction |
| PRESS | capstone/full | — | no match |
| RAZOR | capstone/full | RAZOR2 | matched |
| RIVER | capstone/full | RIVER1 | matched |
| ROCKINGCHAIR | capstone/full | ROCKINGCHAIR1 | matched |
| RUN | beginner | RUN | matched |
| SAD | beginner | — | no match |
| SCARED | beginner | — | no match |
| SCHOOL | beginner | — | no match |
| SCROLLDOWN | capstone/full | SCROLLDOWN | matched |
| SEE | motion-manual | SEE | matched |
| SHARK | capstone/full | — | no match |
| SHAVE | capstone/full | — | no match |
| SHOCKED | capstone/full | — | no match |
| SICK | motion-manual | SEE | wrong prediction |
| SINCE | capstone/full | — | no match |
| SINK | capstone/full | SINK | matched |
| SISTER | beginner | — | no match |
| SIT | beginner | — | no match |
| SLEEP | beginner | — | no match |
| SLIDE | capstone/full | SLIDE2 | matched |
| SOCCER | capstone/core | SOCCER2 | matched |
| SORRY | beginner | — | no match |
| SQUEEZE | capstone/core | — | no match |
| STAND | beginner | STAND | matched |
| STOP | beginner | — | no match |
| STORE | beginner | — | no match |
| STUDENT | beginner | — | no match |
| SWEATER | capstone/full | SWEATER2 | matched |
| TAIL | capstone/full | LETTUCE1 | wrong prediction |
| TAKE | beginner | — | no match |
| TEACH | capstone/full | — | no match |
| TEACHER | beginner | — | no match |
| THANK YOU | motion-manual | THANK YOU | matched |
| THAT | beginner | — | no match |
| THERE | beginner | — | no match |
| THEY | capstone/full | — | no match |
| THIRD | capstone/full | — | no match |
| THIRSTY | beginner | — | no match |
| THIS | beginner | — | no match |
| TIME | beginner | TIME | matched |
| TIRED | beginner | TIRED | matched |
| TODAY | beginner | — | no match |
| TOMATO | capstone/full | — | no match |
| TOMORROW | beginner | — | no match |
| TRACTOR | capstone/full | BELT1 | wrong prediction |
| TWINS | capstone/full | — | no match |
| VLOG | capstone/core | VLOG | matched |
| VOMIT | capstone/full | RIVER1 | wrong prediction |
| WAIT | beginner | — | no match |
| WAKE UP | beginner | WAKE UP | matched |
| WALK | beginner | — | no match |
| WALK TIGHTROPE CL | capstone/full | HURDLE/TRIP1 | wrong prediction |
| WANT | daily-manual | WANT | matched |
| WATER | motion-manual | NO | wrong prediction |
| WE | beginner | — | no match |
| WELCOME | beginner | — | no match |
| WHAT | beginner | — | no match |
| WHATFOR | capstone/extended | WHATFOR1 | matched |
| WHEN | beginner | — | no match |
| WHERE | beginner | — | no match |
| WHICH | beginner | WHICH | matched |
| WHO | beginner | — | no match |
| WHY | beginner | — | no match |
| WORK | beginner | — | no match |
| YES | motion-manual | YES | matched |
| YESTERDAY | beginner | — | no match |
| YOU | beginner | — | no match |
| YOUR / YOURS | beginner | YOUR / YOURS | matched |

## Reproduce the report summary

```powershell
python scripts/summarize_motion_virtual_camera.py
```

The scalar-only source report includes clip hashes, status messages, selected model routes, and frame counts. It contains no video bytes or raw hand/body-coordinate arrays.
