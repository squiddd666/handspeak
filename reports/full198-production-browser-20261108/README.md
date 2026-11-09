# Full-198 actual-app reference regression

**Recognition is not fully fixed.** This is a regression of previously used Watch references, not independent/new-signer accuracy.

Explicit-glossary score: **148 matched / 8 wrong / 42 no match**.
Literal strings: 99 equal / 57 unequal accepted labels / 42 no match. Legitimate predeclared dataset aliases are shown separately, not advertised as recognition improvements.

Verified 175 production API receipts and owned-process cleanup. All frozen run inputs remain unchanged.

## Remaining failures

| Word | Prediction | Attribution |
|---|---|---|
| 8HOUR | SOCCER2 | accepted-wrong-word |
| ANGRY | no match | model-rejection:ambiguous |
| APPLE | no match | model-rejection:ambiguous |
| ARTICULATESIGN | no match | model-rejection:ambiguous |
| BEFORE | SCHOOL | accepted-wrong-word |
| BITE | no match | capture-or-processing-timeout |
| BREAKFAST | no match | model-rejection:ambiguous |
| BROTHER | no match | model-rejection:ambiguous |
| CANCER | no match | model-rejection:ambiguous |
| CATAPULT | no match | model-rejection:ambiguous |
| CHEESEGRATER | no match | model-rejection:ambiguous |
| DEVELOP | no match | model-rejection:ambiguous |
| DOG | no match | model-rejection:outside-vocabulary |
| FINE | no match | model-rejection:ambiguous |
| FISH | no match | insufficient-hand-capture-or-encoding |
| FOOD | LIKE | accepted-wrong-word |
| FOREIGNER | no match | model-rejection:ambiguous |
| GO | no match | insufficient-hand-capture-or-encoding |
| HAVE | HOME | accepted-wrong-word |
| HE / SHE | no match | model-rejection:low-score |
| HELLO | FINISH | accepted-wrong-word |
| HOPE | no match | model-rejection:ambiguous |
| JOKE | no match | model-rejection:ambiguous |
| LATER | no match | source-playback-incomplete |
| MEACULPA | no match | model-rejection:low-score |
| MORNING | no match | model-rejection:ambiguous |
| NAME | no match | rejected-or-unattributed-no-match |
| NEED | no match | insufficient-body-tracking |
| NOON | no match | model-rejection:ambiguous |
| NOW | no match | model-rejection:low-score |
| OKAY | no match | capture-or-processing-timeout |
| PAIN | NIGHT | accepted-wrong-word |
| PATIENT | no match | model-rejection:ambiguous |
| PHONE | no match | model-rejection:low-score |
| PIPE | no match | model-rejection:ambiguous |
| RAZOR | no match | model-rejection:ambiguous |
| RIVER | no match | model-rejection:ambiguous |
| SAD | no match | model-rejection:ambiguous |
| SCHOOL | no match | model-rejection:ambiguous |
| SCROLLDOWN | no match | model-rejection:ambiguous |
| SHAVE | no match | model-rejection:ambiguous |
| SISTER | no match | model-rejection:ambiguous |
| STORE | no match | model-rejection:ambiguous |
| STUDENT | no match | model-rejection:ambiguous |
| TAIL | no match | model-rejection:ambiguous |
| TAKE | no match | model-rejection:ambiguous |
| THANK YOU | PLEASE | accepted-wrong-word |
| THIRSTY | I / ME | accepted-wrong-word |
| WALK TIGHTROPE CL | no match | model-rejection:ambiguous |
| WHY | no match | model-rejection:ambiguous |
