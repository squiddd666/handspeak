# HandSpeak application operations

Live URL: https://handspeak.cvsu.dev. nginx terminates TLS and proxies to the loopback Python service on port 8000. The active website is `/opt/handspeak/current`; Git sources are kept separately at `/opt/handspeak/repository`.

## Accounts and administration

Visitors can use the translator without signing in. Guest saved messages are scoped to an opaque HttpOnly cookie; registration/sign-in transfers only that guest history to the account. Account history follows the account across devices. Session tokens are random, stored hashed in MariaDB, expire after seven days, and are revoked by sign-out, password resets, and deactivation. Passwords use salted scrypt (N=16384, r=8, p=5). Admin authorization is checked on each protected API request; registering cannot select a role.

The first administrator is created using `https://handspeak.cvsu.dev/#setup=TOKEN`, where TOKEN is the private content of `/opt/handspeak/data/admin-setup-token`. Read it only from the server as its owner/root. The token is created once when no administrator exists, deleted after setup, and never included in HTTP page requests (URL fragment). Do not commit or publish the token. Setup can be completed only once. No initial password is set by the deployment.

Users can change their password under Account. Administrators can create single-use reset links from `/admin.html`; they expire after 30 minutes. Identity must be checked before privately giving a link to its account owner. Email verification, email delivery, and MFA are not configured. The interface explicitly describes this recovery process. Existing feedback is visible only to administrators; aggregate ratings remain public. Legacy shared-history records are retained privately but cannot be assigned to a user without evidence of ownership.

If the sole administrator loses access, the server owner can run `sudo python3 /opt/handspeak/ops/admin_reset.py admin@example.com` over SSH to generate a private recovery link for that existing administrator. The command never creates a new account or changes a role. Substitute the actual administrator email; keep its output private.

## Private data and backups

Production uses MariaDB database `handspeak`, accessible locally through `/run/mysqld/mysqld.sock`. The systemd override sets `HANDSPEAK_DATA_DIR=/opt/handspeak/data` and `HANDSPEAK_MYSQL_CONFIG=/opt/handspeak/data/mysql.json`. That private file contains the restricted application login. The archived SQLite file is **not** updated after migration. Private data and source files are denied by nginx and the application static-file handler. Never put backups under the web root.

Sign into a website administrator account, open `/admin.html`, then choose **Open phpMyAdmin**. Its separate database login is in the server-owner-only file `/opt/handspeak/data/database-access.txt`. Never put that password in slides or Git. phpMyAdmin is protected by nginx `auth_request` against the website admin session, then by its own cookie authentication. A regular website account receives 403. The manager account can access only `handspeak`; root logins are disabled in phpMyAdmin. MariaDB listens only on loopback. The packaged PHP application runs through PHP-FPM; the website backend remains Python.

Schema and entity relationships are documented in [database/README.md](../database/README.md). `schema.sql` provisions a fresh database. `ops/migrate_to_mariadb.py` imports a stopped SQLite source into an empty MariaDB database transactionally and compares every row before commit. The root local socket is required for this one-time operation. The application user has data privileges only, not schema-management privileges.

`handspeak-backup.timer` creates a daily consistent MariaDB dump, checks dump completion and gzip integrity, and keeps the latest 14 `.sql.gz` snapshots in `/opt/handspeak/data/backups`. The backup credential file is `/opt/handspeak/data/mysql-backup.cnf`, mode 0600. These are on-server recovery copies; off-site disaster recovery is not configured. Check `systemctl status handspeak-backup.timer` and `journalctl -u handspeak-backup.service`. Run `sudo systemctl start handspeak-backup.service` before manual database edits. A dump was also restored into an isolated database as a deployment check.

For recovery, stop the website and take a fresh dump of its current state. Restore the chosen dump into an isolated database first and verify table counts and relations. Then restore the verified dump into `handspeak` through the root local socket; this replaces existing tables, so preserve the pre-restore dump. Revoke restored authentication sessions and password-reset tokens if an older backup could re-enable revoked credentials. Restart the service and verify health, sign-in, private history, and administrator access. Keep file permissions and the database application grants unchanged. Do not restore the historical SQLite copy into an active MariaDB deployment.

## Defense demonstration

Open `/defense.html` for the presentation walkthrough, architecture, privacy behavior, known recognition limits, and checks before presenting. Demonstrate learning videos, camera permission, experimental recognition, editing/saving a message, a second account's isolated history, feedback, and administrator tools. Do not show live passwords, private setup/reset links, password hashes, or user comments on presentation slides. The administrator can search users and download feedback CSV for evaluation. CSV fields are escaped against spreadsheet formulas.

## Deployment and checks

Installed server dependencies: MariaDB 11.8.6, phpMyAdmin 5.2.3, PHP-FPM 8.5, and the distribution `python3-pymysql` package. `ops/phpmyadmin.nginx.conf` is included in the HTTPS server block; `ops/phpmyadmin.config.php` belongs under `/etc/phpmyadmin/conf.d/`; `ops/php-security.ini` belongs under the installed PHP-FPM version’s `conf.d/`. Never copy a database credential into these public configuration templates. The live Python systemd process uses the distribution Python; training tests use their separate virtual environment.

To run MariaDB HTTP tests, use `HANDSPEAK_MYSQL_CONFIG=/opt/handspeak-staging/data/mysql-test.json PYTHONPATH=. /opt/handspeak-training/venv/bin/python training/test_application.py` from the repository. Tests erase their fixture tables and explicitly refuse any database except `handspeak_test`. Omit that environment variable for isolated temporary SQLite tests.

1. Run the Python regression suite with the training venv. Application tests use an isolated temporary database.
2. Run browser end-to-end checks against a staging database, never the production database.
3. Back up production data and the old application files before changing a release.
4. Deploy application files, increment modified frontend asset query versions, and restart `handspeak.service` only for backend changes.
5. Verify HTTPS, API health, account and admin access controls, denied private paths, and mobile rendering.

Cloudflare client IPs are restored only from published trusted proxy networks so per-client login limits do not group all visitors behind the same edge server. The authentication attempt limit is 20 requests per client per ten minutes and is process-local. Recheck trusted proxy ranges after network changes. TLS auto-renewal remains enabled.

Recognition is experimental. The six-word default and three-word optional preview are not a validated continuous-sign translator. See the model evaluation files before making accuracy claims.

Security implementation references: [OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) and [OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).

## Public sign-in removal — October 11, 2026

The public translator no longer presents account login or registration. Guest messages remain scoped to the browser cookie; clearing it removes access. Existing account sessions and saved records are preserved. Administrator access is available at /account.html?signin=1; /admin.html links to that page. Legacy /?signin=1, setup fragments, and reset fragments redirect to the separate access page without putting fragment tokens into the query string. Authentication and administrator API protections remain enabled. The registration prompt is hidden on the separate administrator page.

## Sentence workflow and learning administration — October 11, 2026

The public page has editable sentence chips, FINISH/LLM/speech progress, an optional seven-step guide, larger text, speech speed and Stop speech. Alt+Shift+S speaks, E edits and X stops speech outside text fields and dialogs. Recorded correct, wrong and missed counts remain separate from live match quality; these changes do not improve model accuracy.

Administrators can edit vocabulary descriptions, hide words from public lessons and recognition, assign existing practice clips or upload MP4 videos (20 MiB maximum, 120 seconds maximum). Use videos with appropriate rights and retain attribution. Uploads are probed using the installed /usr/bin/ffprobe; only /opt/handspeak/current/media/signs needs group write permission for the handspeak service. Uploading a lesson does not train a recognition model.

Apply ops/migrations/20261011-experience.sql to MariaDB after a private database backup before deploying experience.py and server.py. The public /api/vocabulary-settings exposes only lesson overrides. /api/admin/experience, /api/admin/vocabulary-settings, /api/admin/practice-video and /api/admin/match-feedback require an active administrator. /api/match-feedback requires explicit consent and stores predicted/expected labels and model identifier, without camera frames or landmarks. Administrators mark reports reviewed or dismissed; reports never trigger training automatically.

Regression checks: training/test_application.py and training/test_experience.py run with HANDSPEAK_MYSQL_CONFIG unset using temporary SQLite/files; training/ux/check_full_experience.py uses mocked API responses against loopback and writes no production data. Public dependencies are pinned in the single-word publisher runtime snapshot to prevent future word releases overwriting UI changes.

## Storage and origin IP — October 17, 2026

Google Cloud metadata confirms external IPv4 34.143.254.67. The disk is 100 GiB; the root filesystem has expanded to approximately 96 GiB, with 53 GiB free at verification. nginx IP host entries now use the new address; the retired sslip.io alias redirects to the canonical domain. Backend services continue using loopback and need no IP change.

Direct HTTPS using the canonical hostname and the new origin IP returns 200, including /api/health. Cloudflare-proxied handspeak.cvsu.dev returned 522 at verification. The zone owner must check/update its origin A record to 34.143.254.67 (and remove any obsolete origin AAAA record if present). No Cloudflare credentials or DNS connector are available in this session, so external DNS was not modified.

The current TLS certificate also includes handspeak.34.177.106.163.sslip.io. After canonical DNS is restored, reissue the handspeak certificate for handspeak.cvsu.dev alone and verify renewal; the retired IP-based name can no longer be validated at this server. Keep the existing certificate until a successful replacement is obtained.

The owner subsequently updated Cloudflare DNS. Public HTTPS and /api/health returned 200 and the local LLM reported available. The handspeak certificate was successfully reissued for handspeak.cvsu.dev alone, expiring January 15, 2027, and nginx was reloaded. certbot.timer remains enabled.
Certificate renewal dry-run also passed using the canonical hostname alone.

## Android hand-tracking recovery — October 19, 2026

A camera preview without hand outlines can result from detector failure before classification. Previously a runtime GPU error closed the main hand detector permanently until restart. Both main-thread and worker detectors now retry once on CPU; a second failure is surfaced without repeated retries. Interrupted sequences are discarded on recovery, and stopped/restarted camera sessions reject stale recovery results. Camera diagnostics now include trackerState and trackerError. Video playback is explicitly muted and inline.

Verified with unit tests and Android Chrome browser emulation using the HELLO practice clip, an injected GPU error, and a real CPU MediaPipe detector. This is not a physical Android device test or a word-accuracy claim. If the phone still shows no outlines, request its Camera diagnostics, browser version, and device model; inspect rawHands versus usableHands before changing detection or classifier thresholds. Test harness: training/ux/check_android_tracking.py (--live uses deployed application assets).

## Accuracy display correction — October 20, 2026

The five-word server preview display now matches the deployed per-word-cutoff model: 51/66 supported clips correct, 15 misses, no wrong supported label, and 3/48 unsupported clips falsely accepted. Its displayed SHA-256 is the deployed private model hash `ecb9c8e061876c9ca50af4b9f5faab55d78a530798ac653798f9e95c37fefb67`. The prior 44/66, 2/48 text and base-model hash were stale.

The seven-word expanded preview is now off by default because its recorded check produced 30/46 correct and 11/16 unsupported false matches; GO produced 1/6 correct. Users may explicitly enable it for testing. The evaluation table reports wrong and missed counts as “Not separated” for this profile because the current published summary does not separate those outcomes. These are recorded-clip results, not live-camera accuracy.
