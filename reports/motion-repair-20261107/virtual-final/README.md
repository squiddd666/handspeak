# Motion virtual-camera clip tests

**198/198 labels tested at normal speed:** 84 matched, 9 wrong predictions, 105 no matches (**42.4% reference matches**).

These are reference-video smoke tests, **not independent held-out or live-user accuracy**.
All 198 recognition labels now have separately sourced recorded benchmark badges; that is measurement coverage, not proof that every word recognizes reliably.

Virtual stream calls: 1. Physical camera calls: **0**. Microphone calls: **0**.
Excluded warm-ups: 0. Insufficient-tracking misses: 27.
Complete primary-clip playback: 197/198; the application's fixed capture window can truncate longer clips.

## Per-model results

| Actual capture route | Tested | Matched | Wrong | No match |
|---|---:|---:|---:|---:|
| beginner | 76 | 23 | 2 | 51 |
| capstone/core | 7 | 6 | 0 | 1 |
| capstone/extended | 12 | 11 | 0 | 1 |
| capstone/full | 79 | 26 | 1 | 52 |
| daily-manual | 5 | 4 | 1 | 0 |
| motion-manual | 19 | 14 | 5 | 0 |

## Final project page

198/198 recognition labels have reference videos available here · 147 local research clips added. Recognition models remain separate; all 198 cannot be active as one vocabulary.

198 of 198 recognition labels have recorded test results. Separate-model benchmarks, not live-camera accuracy.

Verified in the normal project page, with the camera off. A screenshot is saved as watch-learn-updated.png. Disposable virtual-source fixtures are separate from index.html and excluded from Git.

## Limitations

* Reference clips are examples, not an independent test set. Some may overlap model inputs.
* A fixed application recording window can cut off longer clips; incomplete playback is reported, not silently excluded.
* Browser/hand-and-body tracking speed and sign variants can cause short clips to miss the tracking gate.
* Core/extended gates and the Beginner gate can refuse predictions; all refusals remain in the denominator.
* All 198 labels having recorded scores does not mean all 198 are verified-ready or active in one model.
* Post-fix camera-badge regressions are saved separately; they never replace this baseline or archived benchmark counts.

## Per-word results

| Expected | Capture route | Prediction | Result |
|---|---|---|---|
| 8HOUR | capstone/full | 8HOUR | matched |
| AFTER | beginner | — | no match |
| ANGRY | beginner | — | no match |
| ANYONE | capstone/full | — | no match |
| APPLE | capstone/full | — | no match |
| ARTICULATESIGN | capstone/full | — | no match |
| AXE | capstone/full | AXE1 | matched |
| BABY | motion-manual | BABY | matched |
| BACKPACK | capstone/full | BACKPACK1 | matched |
| BAD | beginner | BAD | matched |
| BAG | beginner | — | no match |
| BASEBALLCAP | capstone/extended | BASEBALLCAP | matched |
| BASKETBALL | capstone/full | BASKETBALL1 | matched |
| BATHROOM | beginner | — | no match |
| BEE | capstone/full | — | no match |
| BEFORE | beginner | — | no match |
| BELT | capstone/core | — | no match |
| BITE | capstone/full | BITE1 | matched |
| BOOK | motion-manual | LIKE | wrong prediction |
| BREAD | beginner | — | no match |
| BREAKFAST | capstone/full | — | no match |
| BROTHER | beginner | — | no match |
| CALENDAR | capstone/full | — | no match |
| CANCER | capstone/full | — | no match |
| CAPTURE | capstone/full | — | no match |
| CATAPULT | capstone/full | MAPLE | wrong prediction |
| CEMETERY | capstone/full | — | no match |
| CHEEK | capstone/full | — | no match |
| CHEESEGRATER | capstone/full | — | no match |
| CHILD | beginner | — | no match |
| CHRISTMAS | capstone/full | — | no match |
| CLOSE | capstone/full | CLOSE | matched |
| CLOTHES | beginner | — | no match |
| COMB | capstone/full | — | no match |
| COME | beginner | COME | matched |
| CONFUSED | capstone/full | CONFUSED1 | matched |
| DARK | capstone/full | — | no match |
| DEAF | capstone/extended | DEAF1 | matched |
| DECIDE | capstone/full | DECIDE1 | matched |
| DEMAND | capstone/extended | DEMAND1 | matched |
| DEVELOP | capstone/full | — | no match |
| DINNER | capstone/full | — | no match |
| DOG | capstone/full | DOG1 | matched |
| DOWNSIZE | capstone/full | DOWNSIZE1 | matched |
| DRAG | capstone/extended | DRAG1 | matched |
| DRINK | motion-manual | DRINK | matched |
| DUCK | capstone/extended | DUCK2 | matched |
| EAT | capstone/core | EAT1 | matched |
| EDIT | capstone/extended | EDIT1 | matched |
| ELEVATOR | capstone/full | ELEVATOR1 | matched |
| EMPTY | capstone/core | EMPTY2 | matched |
| ERUPT | capstone/full | — | no match |
| EVERYONE | beginner | — | no match |
| FAMILY | beginner | — | no match |
| FATHER | beginner | — | no match |
| FINE | capstone/full | — | no match |
| FINISH | motion-manual | FINISH | matched |
| FISH | motion-manual | SEE | wrong prediction |
| FLOAT | capstone/full | FLOAT1 | matched |
| FOOD | motion-manual | FOOD | matched |
| FOREIGNER | capstone/full | — | no match |
| FRIEND | beginner | — | no match |
| GIVE | beginner | — | no match |
| GO | motion-manual | GO | matched |
| GOOD | beginner | — | no match |
| GOOD AFTERNOON | beginner | GOOD AFTERNOON | matched |
| GOOD MORNING | beginner | — | no match |
| GOOD NIGHT | beginner | GOOD NIGHT | matched |
| GOODBYE | beginner | — | no match |
| GRAMMAR | capstone/full | GRAMMAR | matched |
| GUESS | capstone/full | — | no match |
| HALLOWEEN | capstone/full | — | no match |
| HAPPY | beginner | — | no match |
| HAVE | daily-manual | HOME | wrong prediction |
| HE / SHE | beginner | — | no match |
| HELICOPTER | capstone/full | HELICOPTER2 | matched |
| HELLO | motion-manual | DRINK | wrong prediction |
| HELP | beginner | — | no match |
| HERE | beginner | HERE | matched |
| HOME | daily-manual | HOME | matched |
| HOPE | capstone/full | — | no match |
| HOSPITAL | capstone/full | HOSPITAL1 | matched |
| HOW | capstone/full | — | no match |
| HUNGRY | motion-manual | THANK YOU | wrong prediction |
| HURDLE / TRIP | capstone/full | — | no match |
| I / ME | beginner | — | no match |
| IMPOSSIBLE | capstone/full | IMPOSSIBLE | matched |
| INSIDE | beginner | — | no match |
| INTUITIVE | capstone/full | INTUITIVE | matched |
| JEWELRY | capstone/full | JEWELRY | matched |
| JOKE | capstone/full | — | no match |
| KNIGHT | capstone/full | — | no match |
| KNOW | beginner | — | no match |
| LATER | beginner | — | no match |
| LETTUCE | capstone/full | — | no match |
| LIKE | motion-manual | LIKE | matched |
| LOCK | capstone/extended | — | no match |
| LOVE | daily-manual | LOVE | matched |
| LUNCH | capstone/full | — | no match |
| MAPLE | capstone/full | MAPLE | matched |
| MEACULPA | capstone/full | — | no match |
| MEAT | capstone/full | — | no match |
| MECHANIC | capstone/extended | MECHANIC1 | matched |
| MICROSCOPE | capstone/extended | MICROSCOPE1 | matched |
| MILK | beginner | MILK | matched |
| MONEY | beginner | — | no match |
| MORNING | beginner | — | no match |
| MOTHER | beginner | MOTHER | matched |
| MOUTH | capstone/full | — | no match |
| MOVIE | capstone/full | — | no match |
| MY / MINE | beginner | MY / MINE | matched |
| MYSELF | capstone/full | MYSELF | matched |
| NAME | daily-manual | NAME | matched |
| NEED | beginner | NEED | matched |
| NIGHT | motion-manual | NIGHT | matched |
| NO | motion-manual | NO | matched |
| NOON | capstone/full | — | no match |
| NOW | beginner | — | no match |
| OFFEND | capstone/full | OFFEND | matched |
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
| PONDER | capstone/full | — | no match |
| PRESS | capstone/full | — | no match |
| RAZOR | capstone/full | — | no match |
| RIVER | capstone/full | — | no match |
| ROCKINGCHAIR | capstone/full | ROCKINGCHAIR1 | matched |
| RUN | beginner | — | no match |
| SAD | beginner | WAIT | wrong prediction |
| SCARED | beginner | — | no match |
| SCHOOL | beginner | — | no match |
| SCROLLDOWN | capstone/full | — | no match |
| SEE | motion-manual | SEE | matched |
| SHARK | capstone/full | SHARK1 | matched |
| SHAVE | capstone/full | — | no match |
| SHOCKED | capstone/full | SHOCKED | matched |
| SICK | motion-manual | SICK | matched |
| SINCE | capstone/full | — | no match |
| SINK | capstone/full | — | no match |
| SISTER | beginner | — | no match |
| SIT | beginner | SIT | matched |
| SLEEP | beginner | — | no match |
| SLIDE | capstone/full | — | no match |
| SOCCER | capstone/core | SOCCER2 | matched |
| SORRY | beginner | SORRY | matched |
| SQUEEZE | capstone/core | SQUEEZE | matched |
| STAND | beginner | — | no match |
| STOP | beginner | — | no match |
| STORE | beginner | — | no match |
| STUDENT | beginner | STAND | wrong prediction |
| SWEATER | capstone/full | SWEATER2 | matched |
| TAIL | capstone/full | — | no match |
| TAKE | beginner | — | no match |
| TEACH | capstone/full | — | no match |
| TEACHER | beginner | — | no match |
| THANK YOU | motion-manual | THANK YOU | matched |
| THAT | beginner | THAT | matched |
| THERE | beginner | THERE | matched |
| THEY | capstone/full | — | no match |
| THIRD | capstone/full | — | no match |
| THIRSTY | beginner | — | no match |
| THIS | beginner | — | no match |
| TIME | beginner | TIME | matched |
| TIRED | beginner | — | no match |
| TODAY | beginner | TODAY | matched |
| TOMATO | capstone/full | — | no match |
| TOMORROW | beginner | — | no match |
| TRACTOR | capstone/full | — | no match |
| TWINS | capstone/full | — | no match |
| VLOG | capstone/core | VLOG | matched |
| VOMIT | capstone/full | VOMIT | matched |
| WAIT | beginner | — | no match |
| WAKE UP | beginner | WAKE UP | matched |
| WALK | beginner | — | no match |
| WALK TIGHTROPE CL | capstone/full | — | no match |
| WANT | daily-manual | WANT | matched |
| WATER | motion-manual | WATER | matched |
| WE | beginner | — | no match |
| WELCOME | beginner | WELCOME | matched |
| WHAT | beginner | — | no match |
| WHATFOR | capstone/extended | WHATFOR1 | matched |
| WHEN | beginner | WHEN | matched |
| WHERE | beginner | — | no match |
| WHICH | beginner | WHICH | matched |
| WHO | beginner | — | no match |
| WHY | beginner | — | no match |
| WORK | beginner | WORK | matched |
| YES | motion-manual | YES | matched |
| YESTERDAY | beginner | — | no match |
| YOU | beginner | YOU | matched |
| YOUR / YOURS | beginner | YOUR / YOURS | matched |

## Reproduce the report summary

```powershell
python scripts/summarize_motion_virtual_camera.py
```

The scalar-only source report includes clip hashes, status messages, selected model routes, and frame counts. It contains no video bytes or raw hand/body-coordinate arrays.
