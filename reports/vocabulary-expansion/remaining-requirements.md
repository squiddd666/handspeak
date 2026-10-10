# Requirements still preventing completion

Full 201-entry recognition is not complete. Listing a word or providing a lesson
video does not make it camera-recognizable.

## Missing verified training sources

GOOD EVENING, FEVER, STOMACHACHE, PHARMACY, CLASSMATE, POLICE STATION, MARKET, TAXI, DON'T TOUCH, UNSAFE, CALL POLICE, CALL AMBULANCE, DON'T HAVE.

These entries require verified ASL meanings/variants and usable source recordings.
Some English phrases require sequences of signs and non-manual grammar; they must
not be enabled by guessing a one-word label or English synonym. Source candidates
and lexical translations in the audit are leads, not approved training labels.

## Recognition failures

The broad 50-word candidate failed development screening. The latest 11-word
ordinary-action retraining passed development but failed known-recording regression
(21/44 correct, one wrong word, one ordinary false HOME). Stricter framing cutoffs,
embedding rejection, mirrored agreement, and a body-context diagnostic did not
resolve the observed grooming confusion. No failed replacement was promoted.

## Release evidence still needed

A replacement must pass unchanged word/negative checks on unused recordings after
its weights and decision rules are frozen, preserve existing supported vocabulary,
and pass continuous capture tests for misses, false suggestions, repeats and delay.
Existing video/OBS tests are useful but cannot establish accuracy on new people.
The current camera fixture still has queue overload on HUNGRY and insufficient
tracked frames on NIGHT on this server. These limitations remain open.

Training processes for the expanded ordinary-action experiment have completed;
the short-window experiment also completed and failed the ordinary regression.
The eight-new-word candidate also failed a fresh ordinary-action check (MORNING
on head massage). No training/evaluation job is currently running. Its planned
sign recordings were not downloaded or scored.
These jobs do not complete the full 201-word vocabulary or deploy automatically.
Raw media remains outside the served website. Current detailed evidence is in
`completion-status.md` and the linked experiment reports.
