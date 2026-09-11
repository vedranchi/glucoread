# Project Knowledge: GlucoRead

* **Goal:** A modern, user-friendly web app for diabetes management — glucose and insulin
  tracking plus rough meal/macro tracking.
* **Project aims:** learning vehicle, a genuinely deployable app (live on an Oracle Always
  Free VM), and a portfolio piece. Favor correctness and clear, readable code.
* **Tech stack:** Python, Django 5.2, PostgreSQL, WhiteNoise, env-driven SMTP email
  (Gmail in prod, console backend in dev; anymail still installed for a later Resend swap),
  gunicorn, Docker, Caddy. Server-rendered templates — no client-side framework, no `fetch`.
* **Shape — one deployable, decided 2026-08-24.** Everything ships as a single Django
  app on the Oracle VM: the public landing page, the authenticated product, and the admin,
  all behind one Caddy instance at one domain. An earlier plan to split the marketing page
  into a standalone Next.js site on Vercel was **reversed** — don't reintroduce a separate
  frontend, a second host, or `NEXT_PUBLIC_*` wiring.
* **Virtualenv:** use `./env/bin/python` (e.g. `./env/bin/python manage.py check`).

## 1. Apps (where things live)
* `users` — custom email-login `User`, `UserPreferences` (mmol vs mg/dL), `HealthProfile`
  (diabetes type), auth, profile editing, password reset. Form logic sits in `services.py`.
* `logs` — the core: `GlucoseLog`, `InsulinLog`, `MealLog`, plus their log/add/edit/delete views.
* `dashboard` — post-login summary screen + glucose chart. Hosts the signup signal.
* `main` — shared `base.html`, the `home()` redirect, and `NoCacheMiddleware`.
* `landing` — the public marketing page rendered by `home()` for anonymous visitors.
  **Part of the product**, not a stopgap: GlucoRead ships as one Django deployment, so the
  landing page lives here and is styled with the same shared theme tokens as the app.
* `core` — settings/urls/wsgi.

## 2. Domain invariants — do not break these
* **Glucose is stored internally in mmol/L.** Convert to/from mg/dL only at the edges,
  driven by the user's `UserPreferences.glucose_unit`. Never persist mg/dL.
* **Soft deletes.** `GlucoseLog`/`InsulinLog`/`MealLog` use `is_deleted` + `deleted_at`.
  Every read query MUST filter `is_deleted=False`. Never hard-delete medical records.
  There is no soft-delete manager — the filter is applied by hand at every call site.
* **Per-user scoping.** Always filter records by `user=request.user`; use
  `get_object_or_404(Model, pk=pk, user=request.user)` so users can't touch others' data.
* **Profiles exist for every user.** The `post_save` signal in `dashboard/signals.py`
  creates `UserPreferences` and `HealthProfile`; service helpers use `get_or_create` as a
  safety net for legacy accounts. Keep both layers consistent.

## 3. Commands
```bash
docker compose up -d db                  # Postgres on 127.0.0.1:5433 — REQUIRED for tests
./env/bin/python manage.py check         # expect zero issues
./env/bin/python manage.py test          # needs the db above, else "Connection refused"
./env/bin/python manage.py runserver
```

> **`manage.py test` should find 166 tests, all passing** (verified 2026-09-10 on
> `chore/production-hardening`).
> Treat the number as a floor, not a fact — it goes stale. If the count *drops*, suspect
> test discovery before assuming tests were deleted: every app needs an `__init__.py`, and
> `logs/` silently lost its own once, which hid the whole core-domain suite from a green run.

CI runs that same suite under `DEBUG=False` (`.github/workflows/ci.yml`). To reproduce it
locally, run `collectstatic` **first**: with `DEBUG=False` the WhiteNoise manifest storage
raises `Missing staticfiles manifest entry` for every `{% static %}` tag until it has,
erroring most of the suite. Ordinary local runs pass only because `staticfiles/` is
already populated — a clean checkout is not so lucky.

## 4. Current state — perishable, dated 2026-08-31
**Renamed GlucoLog → GlucoRead (2026-08-31, legal).** The new domain is
`glucoread.com`. The rename was deliberately split: everything user-visible and
in-repo moved, while every name that also exists as *live state on the VM* was left
alone so a merge to `dev` could not break the running deploy.

*Moved:* brand text (one spelling now, `GlucoRead`), the `glucoread-*` URL route
names, the `glucoread-theme` localStorage key, the cache table (`glucoread_cache`,
renamed by `main/migrations/0002`; 0001 still creates the old name so fresh installs
and production converge), the GitHub repo slug, and `demo@glucoread.app`.

*Deliberately still `glucolog`, needs a coordinated VM cutover:* the domain and
`SITE_DOMAIN`/`ALLOWED_HOSTS`/duckdns, the Postgres db/role/password and the
`glucolog_postgres_dev` volume, `/opt/glucolog`, the `glucolog_*` container names,
`ghcr.io/vedranchi/glucolog`, the `glucolog-redeploy` systemd units, the
`glucolog-*.sql.gz` backup prefix and its B2 remote, and the `GLUCOLOG_*` env vars.
**Do not "finish" these piecemeal** — `redeploy.sh` fast-forwards the VM checkout and
re-execs itself, so a `cd /opt/glucoread` merged before the directory is moved breaks
deploys silently. Note the HSTS open item below is unblocked once the domain moves.

**The repo rename is done, and its trap is worth remembering.** CI derives the image
name from `IMAGE_NAME: ${{ github.repository }}` (`.github/workflows/ci.yml`) while
`docker-compose.prod.yml` and `deploy/redeploy.sh` hard-code the path. Renaming the repo
without moving those two references would have left CI publishing to the new path while
the VM kept pulling the old tag — which still exists, so the pull succeeds, `redeploy.sh`
sees no drift, exits 0, and production silently stops receiving updates. All three now say
`ghcr.io/vedranchi/glucoread`.

**A renamed repo also means a new GHCR package, and new packages are private.** The VM
pulls anonymously, so the first publish under a new name needs the package flipped to
Public or every pull 403s. `redeploy.sh` fails safe there — it logs and leaves the running
app alone — so the symptom is "deploys stopped", not an outage.

**Live in production** at `https://glucoread.com` — first deploy 2026-08-23 on the Oracle
VM, running `dev`. Moved off `glucolog.duckdns.org` on 2026-08-31, onto a reserved Oracle
public IP. Caddy holds valid Let's Encrypt certs, all three containers are healthy, and the
security headers verify on the wire.

**One canonical hostname.** `deploy/caddy/Caddyfile` serves the app on `{$SITE_DOMAIN}` only;
`www.glucoread.com` and the old `glucolog.duckdns.org` are 301'd to it by a separate block.
Redirecting at the proxy means those never reach Django, so they must *not* be in
`ALLOWED_HOSTS` — and must not be in `SITE_DOMAIN` either. A hostname appearing in both the
app block and the redirect block is a fatal Caddy config error that takes the whole site
down, so change `.env` and the Caddyfile together.

**Caddy config changes need the container to actually see the new file — this has now
bitten twice.** `redeploy.sh` first ran `up -d web`, so a Caddyfile change landed in the
checkout and did nothing until Caddy restarted for some unrelated reason; that was fixed by
running `up -d` for the whole stack plus an explicit `caddy reload`. The *root* cause was
different and survived that fix: compose bind-mounted `deploy/Caddyfile` as a **single
file**, Docker resolves a file mount to an inode at container start, and git replaces files
rather than editing them in place. So after every fast-forward the container went on
reading the pre-merge Caddyfile — and `caddy reload` dutifully validated and applied that
stale file and logged "caddy reloaded". Confirmed on the VM 2026-09-10:
`docker exec glucolog_caddy grep -c nosniff /etc/caddy/Caddyfile` returned 0 while the
checkout returned 2.

The mount is now the **directory** `deploy/caddy/`, which resolves by path on every lookup,
and `redeploy.sh` diffs the container's copy against the checkout before reloading and
recreates the container if they differ. **Never mount a single file that git updates.**

**Rolling the image back across `main/0002` breaks rate limiting.** That migration renames
the cache table, and a rollback to a pre-rename image leaves `CACHES` pointing at a table
that no longer exists, so every rate-limited auth view raises `ProgrammingError`. The
migration is reversible — unapply it (`migrate main 0001`) as part of any such rollback.

**The VM is `VM.Standard.E2.1.Micro` — x86_64, 2 cores, 956 MiB RAM.** *Not* the Ampere A1
arm64 box this file and `deploy/README.md` both claimed until 2026-08-25. It now carries a
2 GB swapfile; before that it had none, with ~630 MiB of its 956 MiB already resident in
the three containers.

**Deploying is automatic — merging to `dev` ships.** Actions runs the tests, builds the
image, pushes it to `ghcr.io/vedranchi/glucolog:dev`; a systemd timer on the VM
(`deploy/redeploy.sh`, every 3 min) pulls and restarts `web` only when the digest changed.
**Never build the image on the VM.** It takes ~7m40s there and is IO-bound, not
network-bound — `mkdir && chown` on two empty dirs costs 32s while PyPI streams at
12 MB/s. The long silence reads as a hang, and an abandoned build leaves the *old
container running*: exactly how #37's design refresh sat merged-but-undeployed for a day.

The security-audit work (#25–#35) is all merged: `SECURE_*` from env, NaN/Infinity
rejected, JWT endpoints removed, env-driven SMTP, auth rate limiting, cross-user isolation
tests, verified backups, PHI stripped from `__str__`, db healthcheck gate and pinned deps.
Since then: the design refresh (#37, one shared token layer in
`main/static/main/css/theme.css` plus a light/dark switch), CI-built images (#39–#40),
offsite B2 backups (#45), and the v1 correctness pass (#49).

**Releases.** `git push --tags` on a `v*` tag builds and publishes `:1.0.0`, `:1.0` and
`:latest` — and deliberately does *not* move `:dev`, so cutting a release cannot change what
production is running. `core.__version__` and `CHANGELOG.md` are bumped in the same commit
as the tag.

* **`main` tracks the last release**; `dev` is the default branch and the integration
  branch, and is what production deploys. Don't work on `main`.

**Deploy gotcha, learned the hard way:** Compose interpolates `$` in `.env`, so a
`SECRET_KEY` containing `$` is silently truncated (you get a `variable is not set` warning
and a different key than the file shows). Escape every literal `$` as `$$`.

**Open items:** HSTS is at 7 days (`SECURE_HSTS_SECONDS`). Raising it to a year is gated on
moving off `duckdns.org` — preload is the only reason to want a full year, and preloading a
subdomain of a registrable domain you don't own pins HTTPS onto borrowed infrastructure,
with removal measured in browser release trains. A year is also unrecoverable from the
server: withdrawing it needs valid HTTPS serving `max-age=0`, which is exactly what a failed
renewal takes away. Revisit on a custom domain.

Also open, and deferred to v1.1: `TIME_ZONE` is hardcoded to `Europe/Skopje` for every user,
so "today" rolls over at the wrong hour elsewhere; log entries are always stamped "now" with
no way to edit the time, so a missed reading can't be back-filled; soft deletes have no
restore UI, though the landing page copy implies one; and changing your email — the login
credential — is unverified.

**Source of truth for longer context:** `deploy/README.md` (the VM runbook), and `HANDOFF.md`
(project state — **local-only, gitignored, never commit it**).

## 5. Coding style
* Follow Django best practices and PEP 8. Match the style of the file you're editing.
* Write clean, single-purpose functions; comment the *why*, not the obvious.
* Prefer DB-level aggregation (`annotate`/`aggregate`/`TruncDate`) over looping in Python.
* **Never compute a total in a template.** Django's `add` filter coerces through `int()`,
  so it silently truncates decimals and returns `""` for a NULL operand — which
  `|default:"0"` then renders as a real zero. That shipped a wrong insulin total to
  production. Aggregate in the view.
* Validate user input (reject negatives/garbage for units, macros, glucose values). The log
  add/edit views hand-parse `request.POST` with no ModelForms — the root cause of the known
  validation bugs, so take extra care adding fields there. Note `max_length` is a *form*
  constraint: `Model.save()` does not truncate, so free-text fields need an explicit length
  check (`logs.views.logs.clean_text`) or Postgres raises `DataError` as a 500.
* On a validation error, **re-render with the submission**, don't `redirect()` — a redirect
  rebuilds the form from the database and throws away what the user typed.

## 6. Git & workflow — strict
* **Verify against `origin` before claiming anything is broken or missing** — but note
  `git fetch` may fail here with `Permission denied (publickey)`. If it does, say so
  plainly; remote-tracking refs are then stale local copies, so don't present them as live.
* `origin/dev` is the true integration branch (currently ~21 commits ahead of `origin/main`;
  `main` is effectively abandoned).
* **Branch per change.** Create a `feature/`, `fix/`, or `chore/` branch off the synced
  `dev` before working. Never commit directly to `dev` or `main`.
* **PRs target `dev`**, not `main`. Use the `gh` CLI (`gh pr create --base dev`).
* Commit/push only when asked. Never commit secrets — `.env`, `email.env`, and
  `.claude/` are gitignored; keep them that way.

## 7. Verify before claiming done
* Run `manage.py check` after changes (expect zero issues), and
  `manage.py makemigrations --check --dry-run` — CI fails on migration drift.
* Where behavior changes, exercise it (run the server / add a test) rather than asserting
  it works. Report failures honestly with output.
* If you couldn't run something, say that — never imply a test passed when it didn't run.

## 8. Config & security
* `DEBUG` comes from the environment only (`env("DEBUG")`); never hard-code it. Set
  `DEBUG=False` for the Oracle deployment.
* `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SECURE_PROXY_SSL_HEADER`, and the `SECURE_*`
  block **already exist and are committed** at `core/settings.py:34-70` — env-driven,
  on-in-prod/off-in-dev. **Do not re-implement them.**
* The site hostname is env-driven end to end (`ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`,
  `SITE_DOMAIN` for Caddy), so moving domains is a VM `.env` change, not a code change.
* `SECRET_KEY` and `DATABASE_URL` intentionally fail fast with no fallback. Keep it that way.
* Health data is PHI: keep glucose values and user identity out of logs, `__str__`, and
  anything shipped to a third-party error reporter.

## 9. Known gotchas
* **crispy-forms and Bootstrap are dead weight, not a conflict.** An earlier note here
  warned that `CRISPY_TEMPLATE_PACK = "bootstrap5"` clashed with the Bootstrap **4.6.2** in
  `main/base.html`. It doesn't: crispy renders *nothing* anywhere — one
  `{% load crispy_forms_tags %}` in `profile.html` with no `|crispy` filter or `{% crispy %}`
  tag, and every field hand-rendered. Bootstrap styles nothing either; every
  Bootstrap-looking class in the templates is a custom class in `base.css`. Both are queued
  for removal in v1.1 — that's a deletion, not a migration.
* **The public JWT endpoints are GONE** (removed in #29) — don't reintroduce them. The DRF
  packages are already out of `requirements.txt`; the only remaining reference is the
  docstring of the regression test that asserts the URLs 404.
* **Python 3.14 locally vs 3.13 in Docker** — local runs don't exercise the deployed
  interpreter.
* **Media is served only when `DEBUG`** (`core/urls.py:15-16`); Caddy serves it in prod.
* **`NoCacheMiddleware`** (`main/middleware.py`) forces no-store on every authenticated
  page — relevant when debugging anything cache-related.
* **Chart.js is the only CDN script, and it is pinned + SRI-checked.** An earlier note
  here said the `integrity=` was missing; that has not been true since #37. What *was*
  wrong until the hardening pass is subtler: the hash covered
  `dist/chart.umd.min.js`, a path that does not exist in the npm package — jsdelivr
  synthesises it by minifying `chart.umd.js` on request. So the hash attested only to
  jsdelivr's minifier output, and a change on their side would fail SRI and silently
  blank the chart. Both tags now name `dist/chart.umd.js`, whose hash is verifiable
  against the npm tarball. Bootstrap is not loaded from anywhere; see the crispy/Bootstrap
  note above.
* **There is a Content-Security-Policy, and it is nonce-based**
  (`main.middleware.ContentSecurityPolicyMiddleware`). `script-src` has no
  `'unsafe-inline'`, so **any inline `<script>` you add needs
  `nonce="{{ request.csp_nonce }}"` or the browser silently refuses to run it**, and
  inline `on*=` handlers cannot be used at all — use `data-confirm` and the delegated
  listener in `base.js`. `style-src` deliberately keeps `'unsafe-inline'` and takes no
  nonce, so `style=""` attributes are fine. `CSP_REPORT_ONLY=True` in the VM `.env`
  disarms enforcement without an image rollback.
* **Django's `{# ... #}` comment is single-line only.** A multi-line one is not a comment;
  its text renders into the page. Use `{% comment %}` for anything spanning lines — this
  shipped a literal `<script>` into `_theme_head.html` for exactly one commit.

## 10. Teaching mode
* Explain the *why* and trade-offs before/with changes; pace work in phases. This project
  doubles as a learning exercise.
