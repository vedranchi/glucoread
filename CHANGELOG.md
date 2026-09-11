# Changelog

All notable changes to GlucoRead are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Caddyfile changes never reached production.** Compose bind-mounted
  `deploy/Caddyfile` as a single file. Docker resolves a file mount to an inode
  when the container starts, and git replaces files rather than editing them in
  place — so after every deploy the container went on serving the pre-merge
  Caddyfile, and `caddy reload` validated and applied that stale copy and logged
  success. The mount is now the `deploy/caddy/` directory, and `redeploy.sh`
  compares the container's copy against the checkout before trusting a reload.

### Security

- **Patched Django and Pillow up to their current security releases.** Django
  was nine patch releases behind on the 5.2 LTS line, which carries
  security-only fixes; four of the Highs land on paths this app exposes,
  including unencrypted email over STARTTLS (CVE-2026-7666) — the password
  reset path. Pillow closes an out-of-bounds write in the PSD decoder
  (CVE-2026-25990) plus a batch of decoder OOB reads and decompression bombs,
  all of which were reachable from the profile picture upload.
- **Narrowed the profile picture upload to JPEG, PNG and WebP, and capped its
  size.** It previously accepted all 70 extensions Pillow registers and fully
  decoded every one, with no size limit anywhere. Uploads are now checked for
  byte size, decoded format (not just filename) and pixel dimensions, and
  Caddy refuses an oversized body before it reaches the disk.
- **Stopped mailing health data to `ADMINS`.** Unhandled 500s are reported by
  email, and Django's report includes the POST body — redacting only keys that
  look like credentials. Here the ordinary field names are the sensitive ones,
  so a failed glucose submission mailed the reading itself in clear text.
- **Added a nonce-based Content-Security-Policy**, with no `'unsafe-inline'`
  in `script-src`. `/static/*` and `/media/*` now carry `nosniff`, and uploads
  are served sandboxed so navigating directly to one executes nothing.
- **Pinned Chart.js to an artefact whose hash can be verified.** The SRI hash
  covered a path jsdelivr generates on the fly rather than one that ships in
  the npm package, so it attested only to their minifier — and would have
  silently blanked the chart if that ever changed.

### Fixed

- **Mobile menu was unreachable once the page was scrolled.** Opening the
  drawer from the sticky topbar put it off the top of the screen and took the
  header with it, leaving the page locked until a reload. The frosted bar now
  paints on a pseudo-element (`backdrop-filter` on the bar itself made it the
  containing block for the fixed drawer), and the drawer contains its own scroll
  instead of locking `overflow` on `<html>` (which stopped `position: sticky`
  from working at all).

## [1.0.0] — 2026-08-31

First tagged release. The app has been running in production since 2026-08-23;
this marks the point at which it was deemed complete enough to version.

### Added

- **Glucose, insulin and meal logging** with per-user history and full add /
  edit / delete for each.
- **Dashboard** — today's totals, a recent-activity feed across all three log
  types, and a glucose trend chart you can page through day by day.
- **Email-based authentication** — signup, sign-in, and password reset, with no
  username field.
- **Unit preference** — mmol/L or mg/dL, per user, applied at the display edge
  only.
- **Light and dark themes** built on one shared token layer, and a responsive
  layout that collapses to a single column with a full-screen nav drawer.
- **Public landing page**, served from the same deployment as the app.
- **Demo data seeder** (`seed_demo_data`) that backdates two weeks of plausible
  history. Refuses to run unless `DEBUG=True`.
- Themed `403`, `404` and `500` pages. `500.html` is standalone by design — it
  has to render when something else is already broken.
- `CHANGELOG.md`, and `core.__version__` as a single source of truth.

### Security

- `SECURE_*` headers, `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` driven entirely
  by environment variables, on in production and off in development.
- Rate limiting on sign-in, registration and password reset — by IP and again by
  submitted credential, so one account cannot be ground down from rotating
  addresses.
- **PHI kept out of logs.** Glucose values and user identity are absent from
  model `__str__`, and `django.db.backends` is pinned above DEBUG so query
  parameters never reach the log stream.
- Removed the public JWT token endpoints, which were unthrottled, issued
  non-revocable tokens, and served no API.
- Cross-user isolation enforced by `user=request.user` scoping on every query and
  pinned by a dedicated test suite that asserts 404 rather than 403, so the
  existence of another user's record is never disclosed.
- Production VM address and SSH key path removed from the repository and moved to
  environment variables.

### Fixed

- **The weekly insulin Total was arithmetically wrong.** It was computed in the
  template with the `add` filter, which coerces through `int()`: half-unit doses
  were truncated, and a day with no basal dose reported a total of `0` however
  much bolus insulin it contained.
- **Over-long text returned a 500.** `max_length` is a form-layer constraint and
  these views hand-parse `request.POST`, so a long meal description or insulin
  brand reached Postgres and raised `DataError`.
- **Editing a meal destroyed stored data.** Nullable macro fields were pre-filled
  as `0`, so re-saving an unchanged meal overwrote NULLs with zeroes, and the
  calorie recompute clobbered a stored value.
- **Validation errors discarded user input.** All three log forms redirected on
  error, rebuilding fields from the database; they now re-render with the
  submission intact.
- **Glucose storage and display branched on different tests**, so an unexpected
  unit preference would display as mmol/L but be divided by 18 on the way in.
- mmol/L readings rendered at the three decimals they are stored at
  (`5.573 mmol/L`); display conversion now lives in one place.
- Sign-in ignored `?next=`, landing users on the dashboard instead of the page
  they had asked for.
- The dashboard rendered the literal string `Meal (None)` for meals without a
  description.
- The profile page silently discarded edits when one section failed validation.
- NaN and Infinity were accepted for glucose and macro values — Postgres
  `numeric` stores them, and one would have poisoned a user's totals permanently.
- The glucose chart drew points in arbitrary order, zigzagging the line.
- Both profiles are now created on signup idempotently, so legacy accounts can't
  end up without one.

### Infrastructure

- **Deployed** on an Oracle Cloud Always Free VM behind Caddy with automatic
  Let's Encrypt TLS, on its own domain at **glucoread.com**. The previous
  `glucolog.duckdns.org` address and `www` both redirect to it permanently, so
  there is exactly one canonical origin for sessions, cookies and HSTS.
- **Automatic deploys** — GitHub Actions runs the suite under `DEBUG=False`
  against a real Postgres service container, builds the image and pushes it to
  GHCR; a systemd timer on the VM pulls and restarts only when the image digest
  has actually changed. The VM never builds.
- Release tags now build too, publishing `:1.0.0`, `:1.0` and `:latest` without
  moving the `:dev` tag production follows.
- CI fails on missing migrations, so a model change cannot ship without its
  migration and silently drift the production schema.
- **Verified nightly backups** — each dump is checked for gzip integrity, a
  completion marker and its expected tables *before* rotation, then pushed
  off-site to Backblaze B2, with a documented restore drill.
- `web` gated on a database healthcheck, container logs capped, all dependencies
  pinned.
- Proxy configuration is now actually applied by a deploy. `redeploy.sh`
  recreated only the app container, so a Caddyfile change reached the VM and sat
  inert until Caddy next restarted for an unrelated reason.

### Changed

- **Renamed GlucoLog to GlucoRead** for legal reasons, across everything
  user-visible: brand text, URL route names, the theme preference key, the demo
  account, and the repository itself. Names that also exist as live state on the
  VM — the Postgres database and its volume, container names, `/opt/glucolog`,
  the systemd units, the backup prefix and the `GLUCOLOG_*` variables — were
  deliberately left alone so the rename could not break a running deploy.
  The one exception is the cache table, renamed by `main/0002`, which is
  reversible and covered by a test coupling both migrations to `settings.CACHES`.
  Saved light/dark theme preferences reset once, since the storage key moved.

### Known limitations

- `TIME_ZONE` is fixed to `Europe/Skopje` for every user, so "today" rolls over
  at the wrong hour outside that zone.
- Log entries are always timestamped "now" and the time cannot be edited, so
  back-filling a missed reading isn't possible yet.
- Soft deletes are implemented, but there is no restore UI.
- Changing your email address — the login credential — is not verified.
- crispy-forms and a Bootstrap 4 stylesheet are still loaded but render nothing;
  the CDN tags are version-pinned but carry no `integrity` attribute.
- HSTS is held at 7 days pending a move to a custom domain.

[Unreleased]: https://github.com/vedranchi/glucoread/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/vedranchi/glucoread/releases/tag/v1.0.0
