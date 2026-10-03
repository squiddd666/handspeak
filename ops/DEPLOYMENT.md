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
