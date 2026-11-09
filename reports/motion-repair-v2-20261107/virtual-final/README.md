# Motion virtual-camera clip tests

**198/198 labels tested at normal speed:** 109 matched, 9 wrong predictions, 80 no matches (**55.1% reference matches**).

These are reference-video smoke tests, **not independent held-out or live-user accuracy**.
All 198 recognition labels now have separately sourced recorded benchmark badges; that is measurement coverage, not proof that every word recognizes reliably.

Virtual stream calls: 1. Physical camera calls: **0**. Microphone calls: **0**.
Excluded warm-ups: 0. Insufficient-tracking misses: 4.
Complete primary-clip playback: 197/198; the application's fixed capture window can truncate longer clips.

## Per-model results

| Actual capture route | Tested | Matched | Wrong | No match |
|---|---:|---:|---:|---:|
| beginner | 76 | 34 | 3 | 39 |
| capstone/core | 7 | 7 | 0 | 0 |
| capstone/extended | 12 | 12 | 0 | 0 |
| capstone/full | 79 | 38 | 1 | 40 |
| daily-manual | 5 | 3 | 1 | 1 |
| motion-manual | 19 | 15 | 4 | 0 |

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
| ANGRY | beginner | ANGRY | matched |
| ANYONE | capstone/full | ANYONE | matched |
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
| BEFORE | beginner | SCHOOL | wrong prediction |
| BELT | capstone/core | BELT1 | matched |
| BITE | capstone/full | BITE1 | matched |
| BOOK | motion-manual | BOOK | matched |
| BREAD | beginner | — | no match |
| BREAKFAST | capstone/full | — | no match |
| BROTHER | beginner | — | no match |
| CALENDAR | capstone/full | — | no match |
| CANCER | capstone/full | — | no match |
| CAPTURE | capstone/full | — | no match |
| CATAPULT | capstone/full | — | no match |
| CEMETERY | capstone/full | — | no match |
| CHEEK | capstone/full | — | no match |
| CHEESEGRATER | capstone/full | — | no match |
| CHILD | beginner | — | no match |
| CHRISTMAS | capstone/full | CHRISTMAS1 | matched |
| CLOSE | capstone/full | CLOSE | matched |
| CLOTHES | beginner | — | no match |
| COMB | capstone/full | — | no match |
| COME | beginner | COME | matched |
| CONFUSED | capstone/full | CONFUSED1 | matched |
| DARK | capstone/full | DARK1 | matched |
| DEAF | capstone/extended | DEAF1 | matched |
| DECIDE | capstone/full | — | no match |
| DEMAND | capstone/extended | DEMAND1 | matched |
| DEVELOP | capstone/full | DEVELOP1 | matched |
| DINNER | capstone/full | DINNER1 | matched |
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
| EVERYONE | beginner | EVERYONE | matched |
| FAMILY | beginner | FAMILY | matched |
| FATHER | beginner | FATHER | matched |
| FINE | capstone/full | — | no match |
| FINISH | motion-manual | FINISH | matched |
| FISH | motion-manual | FISH | matched |
| FLOAT | capstone/full | FLOAT1 | matched |
| FOOD | motion-manual | FOOD | matched |
| FOREIGNER | capstone/full | — | no match |
| FRIEND | beginner | — | no match |
| GIVE | beginner | — | no match |
| GO | motion-manual | GO | matched |
| GOOD | beginner | GOOD | matched |
| GOOD AFTERNOON | beginner | GOOD AFTERNOON | matched |
| GOOD MORNING | beginner | — | no match |
| GOOD NIGHT | beginner | GOOD NIGHT | matched |
| GOODBYE | beginner | GOODBYE | matched |
| GRAMMAR | capstone/full | GRAMMAR | matched |
| GUESS | capstone/full | — | no match |
| HALLOWEEN | capstone/full | HALLOWEEN1 | matched |
| HAPPY | beginner | MY / MINE | wrong prediction |
| HAVE | daily-manual | HOME | wrong prediction |
| HE / SHE | beginner | — | no match |
| HELICOPTER | capstone/full | HELICOPTER2 | matched |
| HELLO | motion-manual | DRINK | wrong prediction |
| HELP | beginner | — | no match |
| HERE | beginner | WHAT | wrong prediction |
| HOME | daily-manual | — | no match |
| HOPE | capstone/full | — | no match |
| HOSPITAL | capstone/full | HOSPITAL1 | matched |
| HOW | capstone/full | HOW1 | matched |
| HUNGRY | motion-manual | HUNGRY | matched |
| HURDLE / TRIP | capstone/full | — | no match |
| I / ME | beginner | I / ME | matched |
| IMPOSSIBLE | capstone/full | IMPOSSIBLE | matched |
| INSIDE | beginner | INSIDE | matched |
| INTUITIVE | capstone/full | INTUITIVE | matched |
| JEWELRY | capstone/full | JEWELRY | matched |
| JOKE | capstone/full | JOKE | matched |
| KNIGHT | capstone/full | KNIGHT1 | matched |
| KNOW | beginner | KNOW | matched |
| LATER | beginner | — | no match |
| LETTUCE | capstone/full | — | no match |
| LIKE | motion-manual | LIKE | matched |
| LOCK | capstone/extended | LOCK1 | matched |
| LOVE | daily-manual | LOVE | matched |
| LUNCH | capstone/full | — | no match |
| MAPLE | capstone/full | MAPLE | matched |
| MEACULPA | capstone/full | MEACULPA | matched |
| MEAT | capstone/full | MEAT1 | matched |
| MECHANIC | capstone/extended | MECHANIC1 | matched |
| MICROSCOPE | capstone/extended | MICROSCOPE1 | matched |
| MILK | beginner | MILK | matched |
| MONEY | beginner | — | no match |
| MORNING | beginner | — | no match |
| MOTHER | beginner | MOTHER | matched |
| MOUTH | capstone/full | MOUTH | matched |
| MOVIE | capstone/full | — | no match |
| MY / MINE | beginner | MY / MINE | matched |
| MYSELF | capstone/full | MYSELF | matched |
| NAME | daily-manual | NAME | matched |
| NEED | beginner | — | no match |
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
| PIPE | capstone/full | PIPE2 | matched |
| PLEASE | motion-manual | PLEASE | matched |
| PONDER | capstone/full | — | no match |
| PRESS | capstone/full | — | no match |
| RAZOR | capstone/full | — | no match |
| RIVER | capstone/full | — | no match |
| ROCKINGCHAIR | capstone/full | ROCKINGCHAIR1 | matched |
| RUN | beginner | RUN | matched |
| SAD | beginner | — | no match |
| SCARED | beginner | SCARED | matched |
| SCHOOL | beginner | — | no match |
| SCROLLDOWN | capstone/full | — | no match |
| SEE | motion-manual | SEE | matched |
| SHARK | capstone/full | SHARK1 | matched |
| SHAVE | capstone/full | — | no match |
| SHOCKED | capstone/full | — | no match |
| SICK | motion-manual | SEE | wrong prediction |
| SINCE | capstone/full | — | no match |
| SINK | capstone/full | IMPOSSIBLE | wrong prediction |
| SISTER | beginner | — | no match |
| SIT | beginner | SIT | matched |
| SLEEP | beginner | — | no match |
| SLIDE | capstone/full | — | no match |
| SOCCER | capstone/core | SOCCER2 | matched |
| SORRY | beginner | SORRY | matched |
| SQUEEZE | capstone/core | SQUEEZE | matched |
| STAND | beginner | — | no match |
| STOP | beginner | STOP | matched |
| STORE | beginner | — | no match |
| STUDENT | beginner | — | no match |
| SWEATER | capstone/full | SWEATER2 | matched |
| TAIL | capstone/full | — | no match |
| TAKE | beginner | TAKE | matched |
| TEACH | capstone/full | TEACH1 | matched |
| TEACHER | beginner | TEACHER | matched |
| THANK YOU | motion-manual | PLEASE | wrong prediction |
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
| TWINS | capstone/full | TWINS1 | matched |
| VLOG | capstone/core | VLOG | matched |
| VOMIT | capstone/full | — | no match |
| WAIT | beginner | WAIT | matched |
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
