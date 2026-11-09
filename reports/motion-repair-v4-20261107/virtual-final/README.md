# Motion virtual-camera clip tests

**198/198 labels tested at normal speed:** 135 matched, 6 wrong predictions, 57 no matches (**68.2% reference matches**).

These are reference-video smoke tests, **not independent held-out or live-user accuracy**.
All 198 recognition labels now have separately sourced recorded benchmark badges; that is measurement coverage, not proof that every word recognizes reliably.

Virtual stream calls: 87. Physical camera calls: **0**. Microphone calls: **0**.
Excluded warm-ups: 0. Insufficient-tracking misses: 13.
Complete primary-clip playback: 196/198; the application's fixed capture window can truncate longer clips.

## Per-model results

| Actual capture route | Tested | Matched | Wrong | No match |
|---|---:|---:|---:|---:|
| beginner | 76 | 52 | 2 | 22 |
| capstone/core | 7 | 7 | 0 | 0 |
| capstone/extended | 12 | 12 | 0 | 0 |
| capstone/full | 79 | 47 | 0 | 32 |
| daily-manual | 5 | 4 | 0 | 1 |
| motion-manual | 19 | 13 | 4 | 2 |

## Interrupted source and continuation

Primary-reference virtual-camera audit assembled from the complete pre-outage prefix and a single continuation attempt for every remaining label. The continuation rebinds the virtual stream per reference; this is a test-source recovery, not a model accuracy improvement or a same-protocol single-run benchmark.

The interrupted source ledger is preserved separately. The aggregate keeps every pre-outage outcome and one continuation attempt per remaining word; it does not choose best-of retries. Both runner hashes and source-report hashes are recorded. This is not a same-protocol single-run model benchmark.

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
| ANYONE | capstone/full | ANYONE | matched |
| APPLE | capstone/full | — | no match |
| ARTICULATESIGN | capstone/full | ARTICULATESIGN | matched |
| AXE | capstone/full | AXE1 | matched |
| BABY | motion-manual | BABY | matched |
| BACKPACK | capstone/full | BACKPACK1 | matched |
| BAD | beginner | — | no match |
| BAG | beginner | BAG | matched |
| BASEBALLCAP | capstone/extended | BASEBALLCAP | matched |
| BASKETBALL | capstone/full | BASKETBALL1 | matched |
| BATHROOM | beginner | BATHROOM | matched |
| BEE | capstone/full | BEE1 | matched |
| BEFORE | beginner | SCHOOL | wrong prediction |
| BELT | capstone/core | BELT1 | matched |
| BITE | capstone/full | BITE1 | matched |
| BOOK | motion-manual | BOOK | matched |
| BREAD | beginner | BREAD | matched |
| BREAKFAST | capstone/full | — | no match |
| BROTHER | beginner | — | no match |
| CALENDAR | capstone/full | CALENDAR1 | matched |
| CANCER | capstone/full | — | no match |
| CAPTURE | capstone/full | CAPTURE | matched |
| CATAPULT | capstone/full | — | no match |
| CEMETERY | capstone/full | — | no match |
| CHEEK | capstone/full | CHEEK | matched |
| CHEESEGRATER | capstone/full | — | no match |
| CHILD | beginner | CHILD | matched |
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
| DEVELOP | capstone/full | — | no match |
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
| FINISH | motion-manual | — | no match |
| FISH | motion-manual | FISH | matched |
| FLOAT | capstone/full | FLOAT1 | matched |
| FOOD | motion-manual | FOOD | matched |
| FOREIGNER | capstone/full | — | no match |
| FRIEND | beginner | FRIEND | matched |
| GIVE | beginner | GIVE | matched |
| GO | motion-manual | — | no match |
| GOOD | beginner | GOOD | matched |
| GOOD AFTERNOON | beginner | GOOD AFTERNOON | matched |
| GOOD MORNING | beginner | GOOD MORNING | matched |
| GOOD NIGHT | beginner | GOOD NIGHT | matched |
| GOODBYE | beginner | GOODBYE | matched |
| GRAMMAR | capstone/full | GRAMMAR | matched |
| GUESS | capstone/full | GUESS1 | matched |
| HALLOWEEN | capstone/full | HALLOWEEN1 | matched |
| HAPPY | beginner | — | no match |
| HAVE | daily-manual | — | no match |
| HE / SHE | beginner | — | no match |
| HELICOPTER | capstone/full | HELICOPTER2 | matched |
| HELLO | motion-manual | DRINK | wrong prediction |
| HELP | beginner | HELP | matched |
| HERE | beginner | HERE | matched |
| HOME | daily-manual | HOME | matched |
| HOPE | capstone/full | — | no match |
| HOSPITAL | capstone/full | HOSPITAL1 | matched |
| HOW | capstone/full | HOW1 | matched |
| HUNGRY | motion-manual | THANK YOU | wrong prediction |
| HURDLE / TRIP | capstone/full | — | no match |
| I / ME | beginner | I / ME | matched |
| IMPOSSIBLE | capstone/full | IMPOSSIBLE | matched |
| INSIDE | beginner | INSIDE | matched |
| INTUITIVE | capstone/full | INTUITIVE | matched |
| JEWELRY | capstone/full | JEWELRY | matched |
| JOKE | capstone/full | — | no match |
| KNIGHT | capstone/full | KNIGHT1 | matched |
| KNOW | beginner | KNOW | matched |
| LATER | beginner | — | no match |
| LETTUCE | capstone/full | — | no match |
| LIKE | motion-manual | LIKE | matched |
| LOCK | capstone/extended | LOCK1 | matched |
| LOVE | daily-manual | LOVE | matched |
| LUNCH | capstone/full | LUNCH1 | matched |
| MAPLE | capstone/full | MAPLE | matched |
| MEACULPA | capstone/full | — | no match |
| MEAT | capstone/full | MEAT1 | matched |
| MECHANIC | capstone/extended | MECHANIC1 | matched |
| MICROSCOPE | capstone/extended | MICROSCOPE1 | matched |
| MILK | beginner | MILK | matched |
| MONEY | beginner | MONEY | matched |
| MORNING | beginner | — | no match |
| MOTHER | beginner | MOTHER | matched |
| MOUTH | capstone/full | MOUTH | matched |
| MOVIE | capstone/full | MOVIE1 | matched |
| MY / MINE | beginner | MY / MINE | matched |
| MYSELF | capstone/full | MYSELF | matched |
| NAME | daily-manual | NAME | matched |
| NEED | beginner | — | no match |
| NIGHT | motion-manual | NIGHT | matched |
| NO | motion-manual | NO | matched |
| NOON | capstone/full | — | no match |
| NOW | beginner | — | no match |
| OFFEND | capstone/full | OFFEND | matched |
| OKAY | beginner | OKAY | matched |
| OTHER | capstone/extended | OTHER | matched |
| OUTSIDE | beginner | OUTSIDE | matched |
| PAIN | motion-manual | NIGHT | wrong prediction |
| PARTY | capstone/extended | PARTY1 | matched |
| PATIENT | capstone/full | — | no match |
| PEG | capstone/core | PEG2 | matched |
| PHONE | beginner | — | no match |
| PIPE | capstone/full | — | no match |
| PLEASE | motion-manual | PLEASE | matched |
| PONDER | capstone/full | PONDER | matched |
| PRESS | capstone/full | — | no match |
| RAZOR | capstone/full | — | no match |
| RIVER | capstone/full | RIVER1 | matched |
| ROCKINGCHAIR | capstone/full | ROCKINGCHAIR1 | matched |
| RUN | beginner | RUN | matched |
| SAD | beginner | SAD | matched |
| SCARED | beginner | SCARED | matched |
| SCHOOL | beginner | — | no match |
| SCROLLDOWN | capstone/full | — | no match |
| SEE | motion-manual | SEE | matched |
| SHARK | capstone/full | — | no match |
| SHAVE | capstone/full | — | no match |
| SHOCKED | capstone/full | SHOCKED | matched |
| SICK | motion-manual | SICK | matched |
| SINCE | capstone/full | — | no match |
| SINK | capstone/full | SINK | matched |
| SISTER | beginner | — | no match |
| SIT | beginner | SIT | matched |
| SLEEP | beginner | SLEEP | matched |
| SLIDE | capstone/full | SLIDE2 | matched |
| SOCCER | capstone/core | SOCCER2 | matched |
| SORRY | beginner | — | no match |
| SQUEEZE | capstone/core | SQUEEZE | matched |
| STAND | beginner | STAND | matched |
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
| THIS | beginner | THIS | matched |
| TIME | beginner | TIME | matched |
| TIRED | beginner | TIRED | matched |
| TODAY | beginner | TODAY | matched |
| TOMATO | capstone/full | TOMATO | matched |
| TOMORROW | beginner | — | no match |
| TRACTOR | capstone/full | — | no match |
| TWINS | capstone/full | — | no match |
| VLOG | capstone/core | VLOG | matched |
| VOMIT | capstone/full | VOMIT | matched |
| WAIT | beginner | WAIT | matched |
| WAKE UP | beginner | WAKE UP | matched |
| WALK | beginner | WALK | matched |
| WALK TIGHTROPE CL | capstone/full | — | no match |
| WANT | daily-manual | WANT | matched |
| WATER | motion-manual | WATER | matched |
| WE | beginner | — | no match |
| WELCOME | beginner | WELCOME | matched |
| WHAT | beginner | WHAT | matched |
| WHATFOR | capstone/extended | WHATFOR1 | matched |
| WHEN | beginner | WHEN | matched |
| WHERE | beginner | WHERE | matched |
| WHICH | beginner | WHICH | matched |
| WHO | beginner | — | no match |
| WHY | beginner | WHY | matched |
| WORK | beginner | WORK | matched |
| YES | motion-manual | YES | matched |
| YESTERDAY | beginner | GOOD NIGHT | wrong prediction |
| YOU | beginner | YOU | matched |
| YOUR / YOURS | beginner | — | no match |

## Reproduce the report summary

```powershell
python scripts/summarize_motion_virtual_camera.py
```

The scalar-only source report includes clip hashes, status messages, selected model routes, and frame counts. It contains no video bytes or raw hand/body-coordinate arrays.
