# Final-defense application readiness — October 21, 2026

## Recognition scope for presentation

- Recommended focused demo: HELLO, THANK YOU, PLEASE, YES, NO, FINISH, NAME, HOME, HAVE, WANT, LOVE.
- The six on-device words matched 59/72 recorded held-out clips. Four of 12 unsupported DRINK clips were falsely accepted.
- The five-word opt-in server preview matched 51/66 held-out clips. Three of 48 unsupported clips were falsely accepted.
- These results are recorded-clip evidence, not live-camera accuracy. Every suggestion requires user review before speech.
- The unreliable seven-word extra preview is excluded from the recommended defense flow because 11/16 unsupported clips were falsely accepted.
- The separate 100-word retrieval model remains experimental: 68.85% recorded top-1 and 87% top-5, with live-camera and per-word reliability unverified.
- The ASL-Citizen 2,731-label dataset is research data, not a ready recognizer. Its complete catalog is not republished because the accompanying Microsoft research license prohibits distributing the data or modifications.

## Deployed

- Live website: https://handspeak.cvsu.dev
- MariaDB replaces SQLite for production persistence; Python backend connects using a restricted data-only database account. PHP is used for phpMyAdmin.
- phpMyAdmin at `/phpmyadmin/` requires both a website administrator session and its separate database login. Guest requests redirect to sign-in; ordinary accounts receive 403. Root database login is disabled there. Database service is loopback-only.
- Admin dashboard shows the database engine, a phpMyAdmin link, account search, and feedback CSV export.
- Public presentation guide: https://handspeak.cvsu.dev/defense.html. Schema/ERD and operations instructions are in `database/README.md` and `ops/DEPLOYMENT.md`.
- Existing accounts, private saved history, message editing/reuse/export/delete, feedback, account recovery, admin activation controls, gesture videos, and experimental recognition remain available.

## Evidence

- Full regression suite: 59 tests passed. Backend suite additionally passed all 14 tests against MariaDB.
- Staging MariaDB browser flows passed: first-admin setup, registration, private history, message save/reuse/delete, CSV export, feedback, reset links, deactivation, password change, sign-out, mobile layout; no JavaScript page errors.
- Live browser checks passed: health, defense guide, admin database overview/search, feedback export, phpMyAdmin login/table listing, guest/member access restrictions, and access revocation after website logout. No JavaScript page errors. Temporary test accounts were removed afterward; first-owner setup token remains unused.
- Migration rehearsal preserved every row from a populated fixture: 2 users, 8 gestures, 1 saved message with Unicode, 1 detection, 1 feedback record, 1 password reset. Production migration compared every row; at cutover it contained 8 gestures and no account/history/feedback rows. The original SQLite file is retained privately as a historical snapshot.
- Scheduled MariaDB dump succeeded. Its eight tables were restored into an isolated database and counts verified. Restore database was removed afterward. Backups retain 14 compressed dumps; no off-site copy is configured.
- Sensitive source/database URLs returned 404; private nginx authorization URL returned 404. nginx configuration test passed; app, nginx, MariaDB, and PHP-FPM are active.

Evidence files in `/opt/handspeak/live-test-results`: `defense-regression-tests.log`, `mariadb-application-tests.log`, `mariadb-browser-tests.log`, `defense-live-browser.json`, `mariadb-migration-fixture.json`, `mariadb-production-migration.json`, and `mariadb-backup-restore.json`.

## Presenter handoff and limits

Read `/opt/handspeak/data/database-access.txt` privately over SSH/IDE for the one-use administrator setup link and separate database credentials. Do not include this file or its contents in slides, screenshots, public reports, or Git. Choose your own website administrator email and password through the setup link.

Application checks do not establish new recognition accuracy. No model was trained or promoted in this database task. Default six-word recognition and three extra preview words remain experimental; rehearse on the presentation camera and explain the published limitations. The face feature tracks visible landmarks/movements, not identity or internal emotion. Email verification, mail delivery, and MFA are not configured; account recovery uses administrator-issued reset links.
