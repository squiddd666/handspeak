# Targeted repair v4: frozen candidates and capture regression

The deployed v3 weights and calibration remain unchanged. Both v4 body-model candidates failed promotion; the manual candidate remains an untested experiment.

The capture fix requires an actual finite body pose during warm-up. Blank callbacks no longer count as readiness. This does not force a practice label or relax a rejection gate.

## All 198 normal-speed primary-reference checks

* Previous: 127 matched / 10 incorrect / 61 no match.
* Current: 135 matched / 6 incorrect / 57 no match.
* Recovered matches: 22; previous-match regressions: 14.
* Complete playback: 196/198. Physical camera and microphone calls: zero.
* Exactly one attempt per label, with unchanged clips and routes. These are reference regressions, not independent live-user accuracy; all misses remain in the denominator.

## Candidate decision

Beginner's reused held-out audit reduced wrong predictions from 28 to 21, but correct matches fell from 502 to 490. It failed the no-coverage-regression gate. Full-100 failed the all-mode validation gate. Neither is installed.
The hand-only manual experiment matched 38/107 validation clips, with 1 wrong and 68 no match. It has no held-out comparison against existing routes and is not installed.

## Remaining work

Tracking misses need complete, usable hand/body capture. Confusing signs need independent signer/variant data and body-location-aware recognition. A correct but rejected suggestion is not fixed by blindly lowering thresholds; validate coverage and both named-word and unsupported-sign errors before promotion.

| Word | Route | Actual output | Diagnosis |
|---|---|---|---|
| AFTER | beginner | — | correct top suggestion rejected |
| ANGRY | beginner | — | competing top suggestion rejected |
| APPLE | capstone/full | — | competing top suggestion rejected |
| BAD | beginner | — | correct top suggestion rejected |
| BEFORE | beginner | SCHOOL | accepted wrong label |
| BREAKFAST | capstone/full | — | correct top suggestion rejected |
| BROTHER | beginner | — | competing top suggestion rejected |
| CANCER | capstone/full | — | competing top suggestion rejected |
| CATAPULT | capstone/full | — | competing top suggestion rejected |
| CEMETERY | capstone/full | — | correct top suggestion rejected |
| CHEESEGRATER | capstone/full | — | correct top suggestion rejected |
| CLOTHES | beginner | — | competing top suggestion rejected |
| COMB | capstone/full | — | correct top suggestion rejected |
| DECIDE | capstone/full | — | correct top suggestion rejected |
| DEVELOP | capstone/full | — | correct top suggestion rejected |
| ERUPT | capstone/full | — | competing top suggestion rejected |
| FINE | capstone/full | — | competing top suggestion rejected |
| FINISH | motion-manual | — | no accepted manual match |
| FOREIGNER | capstone/full | — | correct top suggestion rejected |
| GO | motion-manual | — | insufficient tracking |
| HAPPY | beginner | — | competing top suggestion rejected |
| HAVE | daily-manual | — | no accepted manual match |
| HE / SHE | beginner | — | correct top suggestion rejected |
| HELLO | motion-manual | DRINK | accepted wrong label |
| HOPE | capstone/full | — | competing top suggestion rejected |
| HUNGRY | motion-manual | THANK YOU | accepted wrong label |
| HURDLE / TRIP | capstone/full | — | correct top suggestion rejected |
| JOKE | capstone/full | — | competing top suggestion rejected |
| LATER | beginner | — | insufficient tracking |
| LETTUCE | capstone/full | — | competing top suggestion rejected |
| MEACULPA | capstone/full | — | correct top suggestion rejected |
| MORNING | beginner | — | competing top suggestion rejected |
| NEED | beginner | — | insufficient tracking |
| NOON | capstone/full | — | correct top suggestion rejected |
| NOW | beginner | — | insufficient tracking |
| PAIN | motion-manual | NIGHT | accepted wrong label |
| PATIENT | capstone/full | — | insufficient tracking |
| PHONE | beginner | — | correct top suggestion rejected |
| PIPE | capstone/full | — | insufficient tracking |
| PRESS | capstone/full | — | correct top suggestion rejected |
| RAZOR | capstone/full | — | competing top suggestion rejected |
| SCHOOL | beginner | — | correct top suggestion rejected |
| SCROLLDOWN | capstone/full | — | correct top suggestion rejected |
| SHARK | capstone/full | — | correct top suggestion rejected |
| SHAVE | capstone/full | — | correct top suggestion rejected |
| SINCE | capstone/full | — | insufficient tracking |
| SISTER | beginner | — | competing top suggestion rejected |
| SORRY | beginner | — | insufficient tracking |
| STORE | beginner | — | insufficient tracking |
| STUDENT | beginner | — | competing top suggestion rejected |
| TAIL | capstone/full | — | insufficient tracking |
| THANK YOU | motion-manual | PLEASE | accepted wrong label |
| THEY | capstone/full | — | correct top suggestion rejected |
| THIRD | capstone/full | — | insufficient tracking |
| THIRSTY | beginner | — | competing top suggestion rejected |
| TOMORROW | beginner | — | correct top suggestion rejected |
| TRACTOR | capstone/full | — | correct top suggestion rejected |
| TWINS | capstone/full | — | insufficient tracking |
| WALK TIGHTROPE CL | capstone/full | — | competing top suggestion rejected |
| WE | beginner | — | insufficient tracking |
| WHO | beginner | — | correct top suggestion rejected |
| YESTERDAY | beginner | GOOD NIGHT | accepted wrong label |
| YOUR / YOURS | beginner | — | insufficient tracking |

Full scalar evidence is in virtual-final/final-all-198.json and virtual-final/summary.json. Candidate selection, frozen audit, failure lists and before/after transitions are retained beside this report. No published benchmark is replaced by reference-test results.

## Test-source interruption and continuation

The virtual stream stopped supplying the current decoded image at NAME. The original interrupted ledger retains all 41 post-onset attempts, including the canceled take. They are test-source failures, not valid model measurements.
The aggregate retains every one of the first 112 pre-outage outcomes, including wrong/no-match results, and one continuation result for each of the other 86 labels. Each continuation rebinds only the virtual stream using public camera controls. Source files, hashes, segments and runner protocols are disclosed in the aggregate.
This is not a same-protocol single-run benchmark or evidence of a model accuracy improvement. No best-of retry selection is used; the source-recovery boundary was chosen from the observed stream failure, not prediction quality.
