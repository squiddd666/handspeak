# Public camera-validation preview

Live URL: https://handspeak.cvsu.dev/motion-preview-20261004/index.html

This is a separate test page. The main recognition vocabulary and model are not
changed. No backend or database deployment was needed. The dated directory is
immutable; use a new dated/versioned path for future candidates.

The preview supports CALL, FIND, FISH, HAVE, HOME, HUNGRY, MORNING, NIGHT, PAIN,
SEE and SICK as possible matches. It requests camera access, performs hand
tracking and classification locally, and provides a copyable diagnostic report.
It does not upload camera frames/landmarks, append sentence words or speak.
The expected-word control records the test intention without filtering predictions.

Recorded tests passed, but live-camera accuracy and continuous signing remain
unverified. The server's software-rendered camera was too slow for the short
recordings. A test on the user's actual OBS/browser setup is needed to distinguish
capture timing problems from classifier misses before main integration.

Checks: 37 targeted Python/JavaScript tests; browser/Python prediction parity
on 77 examples; static-page camera lifecycle, no-hand behavior, permission denial,
corrupt-model rejection, dependency-load failure and mobile-width checks.
Generated test-camera UI checks are not sign recognition accuracy tests.

Deployment copied only the 12 preview assets to a new directory atomically.
Existing main HTML and scripts retained their hashes. Asset hashes and rollback
instructions are in `deployment.json`; backup records are outside the webroot in
`/opt/handspeak/backups/motion-preview-20261004`.

For OBS verification: open the link, start the camera, select a supported expected
word, play/sign it once and pause, then use Copy test report. Also test an ordinary
movement. Report misses, incorrect words, repeated suggestions and perceived delay.
The copyable report contains timing/classification metadata, not video or landmarks.
