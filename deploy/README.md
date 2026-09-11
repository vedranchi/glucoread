# Deploying GlucoRead to the Oracle VM

Production runs as three containers via Docker Compose — **Caddy** (public, TLS) →
**web** (gunicorn) → **db** (Postgres) — reachable over HTTPS at a DuckDNS domain.
Caddy provisions the Let's Encrypt certificate automatically.

```
Internet ──443──▶ caddy ──proxy──▶ web:8000 (gunicorn/Django) ──▶ db:5432 (postgres)
                    │  serves /static/* and /media/* from shared volumes
```

## Files

| File | Role |
| --- | --- |
| `docker-compose.yml` | base: `db` service |
| `docker-compose.override.yml` | **dev only** (auto-loaded): publishes DB on localhost |
| `docker-compose.prod.yml` | **prod**: adds `web` + `caddy`, hardens `db` |
| `deploy/caddy/Caddyfile` | reverse proxy + auto-HTTPS + static/media. Lives in its own
  directory because compose bind-mounts the **directory**: a single-file mount pins an
  inode, and git replaces files, so the container kept serving a pre-merge copy. |
| `deploy/env.example` | template for repo-root `.env` |
| `deploy/email.env.example` | template for repo-root `email.env` |
| `deploy/backup.sh` | verified `pg_dump` + rotation (cron) |
| `deploy/restore.sh` | restore a dump; `--into` for a non-destructive drill |
| `deploy/duckdns.sh` | optional dynamic-DNS updater |
| `deploy/redeploy.sh` | pull-based deploy: GHCR image + config, restart only on change |
| `deploy/glucolog-redeploy.{service,timer}` | systemd units that run it every 3 min |
| `.github/workflows/ci.yml` | tests every change; builds + publishes the image from `dev` |

> **Prerequisite:** the prod-security settings in `core/settings.py` must be committed
> and present on the branch you deploy. The VM pulls from git.

---

## One-time VM setup

1. **Instance** — the live VM is `VM.Standard.E2.1.Micro`: **x86_64, 2 cores, 956 MiB
   RAM, no swap**, Ubuntu. (Earlier revisions of this file said "Ampere A1 (arm64)" —
   that was wrong, and it matters: 1 GB of RAM is why images are built in CI and not
   here.) Note the public IP and **reserve it** (Networking → Reserved public IPs) so it
   survives stop/start.

   Add swap — with 956 MiB total and ~630 MiB resident in the three containers, the box
   has no headroom:
   ```bash
   sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
   sudo mkswap /swapfile && sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   sudo sysctl -w vm.swappiness=10   # swap as a safety net, not a habit
   ```

2. **Open the ports (VCN ingress)** — Networking → your VCN → Security List → add
   ingress rules: TCP **80** and TCP **443** from `0.0.0.0/0` (22 already exists).

3. **Install Docker**
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker "$USER"      # then log out/in
   ```

4. **Fix the instance firewall (the Oracle gotcha)** — Ubuntu images ship a default
   `INPUT ... REJECT` rule that blocks 80/443 even after the ingress rule. Insert ACCEPTs
   above it and persist:
   ```bash
   sudo iptables -I INPUT 6 -p tcp --dport 80  -j ACCEPT
   sudo iptables -I INPUT 6 -p tcp --dport 443 -j ACCEPT
   sudo netfilter-persistent save
   ```
   (Check `sudo iptables -L INPUT --line-numbers` — the ACCEPTs must sit above the REJECT.)

5. **DuckDNS** — create the subdomain at duckdns.org and set its IP to the VM's public IP.
   If the IP isn't reserved, install `deploy/duckdns.sh` on a 5-min cron (see the script).

6. **Install rclone** (for the offsite backup push — see Backups below)
   ```bash
   sudo apt-get update && sudo apt-get install -y rclone
   ```

---

## Deploy

```bash
# 7. Get the code
git clone git@github.com:vedranchi/glucoread.git /opt/glucolog
cd /opt/glucolog
git checkout <deploy-branch>

# 8. Secrets (never committed)
cp deploy/env.example .env
python3 -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
#   → paste into SECRET_KEY; set ALLOWED_HOSTS / CSRF_TRUSTED_ORIGINS / SITE_DOMAIN to
#     your DuckDNS domain; set matching DB_PASSWORD + DATABASE_URL password.
#   → set ADMINS, or unhandled 500s are logged and nobody is told.
#   → DJANGO_LOGLEVEL=INFO is a sane start; DEBUG must stay False.
nano .env

cp deploy/email.env.example email.env
nano email.env               # SMTP host/user + Gmail App Password

# 9. Launch. Pulls the image CI published to GHCR — no build happens here.
#    `web` waits for Postgres to pass its healthcheck before starting, so the
#    boot-time migrate cannot race the database.
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f caddy   # watch cert issuance

# 10. Create an admin user
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web \
  python manage.py createsuperuser
```

Define a shell alias to save typing:
```bash
alias dcp='docker compose -f docker-compose.yml -f docker-compose.prod.yml'
```

---

## Verify (end-to-end)

- `curl -I https://<domain>/` → `200` and a valid cert (no TLS warning). `/` renders the
  landing page for anonymous visitors; `home()` only redirects once you are logged in.
  `curl -I https://<domain>/dashboard/` is the one that should `302` to `/users/login/`.
- Open `https://<domain>/users/register/` → styled page (CSS from `/static/`).
- Register → log in → dashboard → log a glucose reading.
- Upload a profile picture → shows from `/media/…`, and survives `dcp restart web`.
- `https://<domain>/admin/` loads and is styled; superuser logs in.
- Trigger a password reset → email arrives (confirms `email.env`).
- `/` (the landing page) renders styled, and its sign-in / create-account CTAs land on
  `/users/login/` and `/users/register/` on this same domain.
- `dcp down && dcp up -d` → DB rows and uploaded media persist (named volumes).
- Run `./deploy/backup.sh`, then restore it with `--into glucolog_drill` and confirm the row
  counts match. An untested backup is not a backup.

## Backups

Health records live on one volume, on one VM. `docker compose down -v` destroys
them irreversibly, and so does losing the instance. Take backups before there is
data worth losing.

```bash
./deploy/backup.sh          # writes backups/glucolog-<UTC stamp>.sql.gz
```

`pg_dump` runs *inside* the db container and reads the `POSTGRES_*` variables
already present there, so no credentials are passed from the host.

The dump is verified before anything is rotated — valid gzip, a completion
marker, and the expected tables present. A dump that fails any check is deleted
and **older backups are kept**, because rotating on the strength of a broken
backup is how backup histories quietly disappear. Retention defaults to 14 days
(`RETENTION_DAYS`).

Schedule it (03:30 daily):

```bash
crontab -e
30 3 * * * cd /opt/glucolog && ./deploy/backup.sh >> /var/log/glucolog-backup.log 2>&1
```

### Restore

**Drill — non-destructive.** Restores into a scratch database and prints row
counts. This is how you find out whether a backup is real:

```bash
./deploy/restore.sh backups/glucolog-<stamp>.sql.gz --into glucolog_drill
```

**Real restore — destructive.** Drops and replaces the live database, and
requires typing the database name to confirm:

```bash
./deploy/restore.sh backups/glucolog-<stamp>.sql.gz
```

> A backup that has never been restored is not a backup. Run the drill after the
> first deploy, and again whenever Postgres is upgraded.

### Offsite copy

Cronned `backup.sh` protects against a bad migration or an accidental `DROP` —
not against losing the VM, since the backups sit on the same instance as the
database. Two independent offsite copies close that gap:

**Primary — VM pushes to Backblaze B2.** After each verified dump and local
rotation, `backup.sh` sources `.env.backup` (a gitignored file on the VM,
never in git — same treatment as `.env`) and runs `rclone copy` to a private
B2 bucket:

```
B2_BUCKET=glucolog
RCLONE_CONFIG_B2GLUCOLOG_TYPE=b2
RCLONE_CONFIG_B2GLUCOLOG_ACCOUNT=<application key ID>
RCLONE_CONFIG_B2GLUCOLOG_KEY=<application key>
```

The application key is scoped to just that bucket (not the master key). The
bucket has Object Lock on (Governance mode, ~30-day retention), so a leaked
key or a buggy script can't delete existing backups within that window — it
can only add new ones. This push is best-effort: if it fails (network, B2
outage), the job logs a warning and still exits 0, since the verified local
dump is already safe and rotation must not be skipped over it.

**Secondary — developer machine pulls via rsync.** `deploy/pull_backups.sh`
`rsync`s `/opt/glucolog/backups/` down to this machine's own gitignored
`backups/` dir, over the same deploy-key SSH access used to reach the VM.
Scheduled via `launchd`
(`~/Library/LaunchAgents/com.glucolog.pullbackups.plist`), daily at 09:00
local time — only runs while that Mac is on, which is why B2 is the primary
copy and this is a second, independent one. Run it by hand any time with
`./deploy/pull_backups.sh`; check `launchctl list | grep glucolog` to confirm
the job is loaded, and `~/Library/Logs/glucolog-pull-backups.log` for its
output.

The script takes the VM address and key from the environment — this repository
is public, so neither belongs in it:

```bash
export GLUCOLOG_VM_HOST=ubuntu@<vm-ip>
export GLUCOLOG_SSH_KEY=~/.ssh/<key>
```

It exits immediately with a named error if either is unset, rather than hanging
on a connection to nowhere. **The launch agent must set both too** — a plist
does not inherit your shell profile, so add them to its `EnvironmentVariables`
dict or the scheduled pull will fail every morning while manual runs succeed.

### Gaps to close

- Dumps contain health data. `backups/` is gitignored and excluded from the
  image; keep it that way, and treat any copy — local, B2, or elsewhere — as
  PHI.
- Nothing alerts on a failed backup or a failed offsite push. Until something
  does, check the log.

## Logs and error alerts

Everything logs to stdout, so `docker logs` is the collection point:

```bash
dcp logs -f web            # app + gunicorn access log
dcp logs --tail=200 web    # recent
```

gunicorn runs with `--access-logfile -` and `--error-logfile -`, so requests and
worker errors both appear there. `--timeout 60` replaces the 30s default, which
silently killed slow requests.

`DJANGO_LOGLEVEL` in `.env` sets the level (default `INFO`). `django.db.backends`
is pinned at `INFO` regardless — at `DEBUG` it echoes query parameters, which for
this app means glucose readings in the logs.

**Set `ADMINS` in `.env`** or unhandled 500s are logged and nothing else:

```
ADMINS=Vedran <you@example.com>
```

Mail goes out over the same SMTP as password reset, so it only works once
`email.env` is configured.

> Docker's json log driver is unbounded. Cap it before the free-tier disk fills:
> add `--log-opt max-size=10m --log-opt max-file=3` to the daemon config, or a
> `logging:` block per service in the compose file.

## Update / redeploy — automatic

**Merging to `dev` deploys.** `.github/workflows/ci.yml` runs the test suite, and on
`dev` builds the image and pushes it to `ghcr.io/vedranchi/glucolog:dev`. A systemd
timer on the VM polls every 3 minutes and restarts `web` only when the image digest or
the compose config actually changed.

Nothing inbound is opened and no VM SSH key lives in GitHub Secrets — the VM pulls, CI
never pushes to it.

```
push to dev ─▶ Actions: test ─▶ build ─▶ GHCR:dev
                                           │
                       glucolog-redeploy.timer (VM, every 3 min)
                                           │
                       digest changed? ─yes─▶ compose up -d web
```

### Why the VM does not build

A full `docker build` on this box takes **~7m40s**, and it is IO-bound, not
network-bound: PyPI pulls at 12 MB/s, but `mkdir && chown` on two empty directories
takes 32 seconds and exporting the image layer takes 84. It runs alongside the live
Postgres in 956 MiB of RAM. It *does* finish — but the long silent stretch during the
wheel downloads reads as a hang, and an abandoned build leaves the **old container
still running**, which is how a merged UI change can sit undeployed for days. CI builds
it on a 4-core runner instead; the VM's share of a deploy is now a ~100 MB pull.

### Install the timer (one-time)

```bash
sudo cp /opt/glucolog/deploy/glucolog-redeploy.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now glucolog-redeploy.timer
systemctl list-timers glucolog-redeploy   # confirm it is scheduled
```

The GHCR package must be **public** for the unauthenticated pull to work. After the
first CI run, set it at
`github.com/users/vedranchi/packages/container/glucolog/settings` → Change visibility →
Public. (The image holds only application code; every secret arrives at runtime through
`env_file`.) To keep it private instead, log the VM in once with a read-only PAT:
`echo <PAT> | docker login ghcr.io -u vedranchi --password-stdin`.

### Watching and forcing a deploy

```bash
journalctl -u glucolog-redeploy -f        # deploy log; silent when nothing changed
sudo systemctl start glucolog-redeploy    # deploy right now, don't wait for the timer
/opt/glucolog/deploy/redeploy.sh          # same thing, in the foreground
```

`redeploy.sh` refuses to act and exits non-zero if the VM checkout has diverged from
`origin/dev` (it fast-forwards only) or if the image pull fails — in both cases the
running app is left alone.

### Manual fallback

If GHCR or Actions is unavailable and you must build on the VM, it still works — budget
about eight minutes and expect the long silences:

```bash
cd /opt/glucolog && git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## Troubleshooting

- **Cert won't issue** → 80/443 not reachable: re-check VCN ingress **and** the instance
  iptables (step 4); confirm DuckDNS resolves to the VM IP (`dig +short <domain>`).
- **`DisallowedHost` / CSRF 403** → `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` in `.env`
  must include the exact domain (CSRF with `https://` scheme).
- **`web` restarting in a loop** → `dcp ps` shows `db` health. `web` only starts once
  Postgres reports healthy, so a stuck `db` means the database never came up: check
  `dcp logs db` and that `DB_*` in `.env` match `DATABASE_URL`.
- **Static 404 / unstyled admin** → check `web` logs for the collectstatic step and that
  the `static_data` volume mounted. Confirm with
  `curl -I https://<domain>/static/admin/css/base.css` (expect `200`). Note the *stock
  Django admin theme is not your Bootstrap theme* — a plain-looking admin that loads its
  own dark header and sidebar is working correctly, not unstyled.
- **Password reset email never arrives** → don't guess, ask the mail backend directly:
  ```bash
  dcp exec web python manage.py shell -c "
  from django.conf import settings
  from django.core.mail import send_mail
  print(settings.EMAIL_BACKEND, settings.EMAIL_HOST, settings.EMAIL_HOST_USER)
  print('password set:', bool(settings.EMAIL_HOST_PASSWORD))
  send_mail('test', 'body', None, ['you@example.com'])"
  ```
  - `SMTPAuthenticationError (535 ... BadCredentials)` → Gmail is rejecting the password.
    It must be an **App Password** (16 chars, no spaces, unquoted) from
    `myaccount.google.com/apppasswords`, which requires 2FA on the account. Gmail has
    refused plain account passwords for SMTP since 2022, and always fails with this exact
    error. `password set: True` only means non-empty, not valid.
  - Sends fine from the shell but the reset form still mails nothing → Django's
    `PasswordResetForm` shows the same confirmation whether or not the address matches a
    real account (deliberate, prevents account enumeration). Check the address is exactly
    the one on the account.
  - **After editing `email.env`, recreate the container** — `env_file` is read at container
    creation, so `dcp restart web` will *not* pick up the change:
    `dcp up -d --force-recreate web`.
- **`WARN[0000] The "..." variable is not set` on every compose command** → a value in
  `.env` contains a literal `$`, which Compose reads as interpolation and replaces with an
  empty string. The app then runs with a *different* value than the file shows — silently.
  Escape each literal `$` as `$$`. Most likely to bite a generated `SECRET_KEY`.
