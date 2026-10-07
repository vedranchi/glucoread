# GlucoRead

Glucose, insulin and meal tracking for people managing diabetes day to day, with a
dashboard that turns raw logs into a picture of the day.

[![CI](https://github.com/vedranchi/glucoread/actions/workflows/ci.yml/badge.svg?branch=dev)](https://github.com/vedranchi/glucoread/actions/workflows/ci.yml)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)
[![Django 5.2](https://img.shields.io/badge/django-5.2-0C4B33.svg)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Live:** [glucoread.com](https://glucoread.com)

> [!IMPORTANT]
> GlucoRead is a personal project for tracking your own readings. It is not a medical
> device, it gives no clinical advice, and nothing it displays should be used to make
> treatment decisions — talk to your care team instead.

![GlucoRead landing page](docs/screenshots/landing.png)

## Contents

- [Features](#features)
- [Screenshots](#screenshots)
- [Tech stack](#tech-stack)
- [Architecture](#architecture)
- [Design decisions](#design-decisions)
- [Getting started](#getting-started)
- [Testing](#testing)
- [Deployment](#deployment)
- [Known limitations](#known-limitations)
- [How this was built](#how-this-was-built)
- [License](#license)

## Features

- Glucose, insulin and meal logging with per-user history and full edit/delete
- Dashboard with daily totals, recent activity and a day-by-day glucose trend
- mmol/L or mg/dL display, per user, without touching stored data
- Email-based auth: signup, sign-in and password reset, with no username
- Soft deletes: log entries are archived, never destroyed
- Light and dark themes on one shared token layer; responsive down to phone width

## Screenshots

### Dashboard

![Dashboard](docs/screenshots/dashboard.png)

### Logging

| Glucose | Insulin | Meals |
| :---: | :---: | :---: |
| ![Glucose log](docs/screenshots/glucose-log.png) | ![Insulin log](docs/screenshots/insulin.png) | ![Meal log](docs/screenshots/meals.png) |

## Tech stack

| Layer | Choice |
| --- | --- |
| Backend | Python 3.13, Django 5.2 |
| Database | PostgreSQL 17 |
| Frontend | Server-rendered Django templates, no client-side framework |
| Static files | WhiteNoise |
| Email | Env-driven SMTP |
| Deployment | Docker, gunicorn, Caddy (reverse proxy and automatic TLS) |
| Hosting | Oracle Cloud Always Free VM |
| CI/CD | GitHub Actions → GHCR image → systemd timer pulls on the VM |
| Backups | Nightly verified Postgres dumps, synced to Backblaze B2 |

## Architecture

| App | Responsibility |
| --- | --- |
| `users` | Custom email-login `User`, `UserPreferences`, `HealthProfile`, auth, profile |
| `logs` | Core domain: `GlucoseLog`, `InsulinLog`, `MealLog` and their CRUD views |
| `dashboard` | Post-login summary screen and glucose chart |
| `main` | Shared base template, home routing, no-cache and CSP middleware |
| `landing` | Public marketing page |
| `core` | Settings, URLs, WSGI |

## Design decisions

Health data imposes constraints a typical CRUD app doesn't, and these are enforced across
the codebase rather than per view:

- **Glucose is stored only in mmol/L**, at three decimal places so the mg/dL round-trip is
  lossless. Conversion happens at the display edge, driven by a per-user preference, so unit
  choice can't corrupt stored data.
- **Soft deletes**, with `is_deleted=False` applied on every read path. Medical history isn't
  destroyed by a misclick.
- **Per-user scoping** on every query, backed by an isolation suite that asserts 404 rather
  than 403, because a 403 would confirm another user's record exists.
- **No PHI in logs.** Glucose values and identity are kept out of `__str__` and log output;
  `django.db.backends` is pinned above DEBUG so query parameters never leak.
- **Rate limiting** on sign-in, registration, password reset and the Django admin, by IP and
  by submitted credential.
- **Verified backups.** Each dump is checked for gzip integrity, a completion marker and its
  expected tables *before* rotation, then pushed off-site.

## Getting started

### Prerequisites

- Python 3.13+
- Docker (for the local Postgres container)

### Installation

```bash
git clone https://github.com/vedranchi/glucoread.git
cd glucoread

python3 -m venv env
./env/bin/pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env

# Generate a secret key; the sed doubles any `$` (see the note below)
./env/bin/python -c "from django.core.management.utils import get_random_secret_key as k; print(k())" | sed 's/\$/\$\$/g'
```

Paste the output into `SECRET_KEY` in `.env`.

> [!NOTE]
> `SECRET_KEY` and `DATABASE_URL` fail fast with no fallback, so this step isn't optional.
> Docker Compose interpolates `.env`, so a literal `$` in a value silently truncates it.
> Double each one to `$$`.

### Run

```bash
docker compose up -d db            # Postgres on 127.0.0.1:5433
./env/bin/python manage.py migrate
./env/bin/python manage.py runserver
```

### Demo data

Seed two weeks of history to see the dashboard populated:

```bash
./env/bin/python manage.py seed_demo_data --reset
```

This creates a `demo@glucoread.app` / `Demo1234!` account. The command refuses to run
unless `DEBUG=True`.

## Testing

```bash
docker compose up -d db
./env/bin/python manage.py collectstatic --noinput
./env/bin/python manage.py test
```

`collectstatic` is required on a fresh clone. The test runner forces `DEBUG=False`, which
switches WhiteNoise to manifest storage, and without a built manifest every `{% static %}`
tag raises. CI runs the same suite against a real Postgres service container.

## Deployment

Merging to `dev` ships:

1. GitHub Actions runs the test suite, builds the image and pushes it to GHCR.
2. A systemd timer on the VM pulls the image and restarts only when its digest changes.
   The VM never builds.
3. Tagging `v*` publishes a versioned image without moving the tag production follows.

See [`deploy/README.md`](deploy/README.md) for the full VM runbook.

## Known limitations

- `TIME_ZONE` is fixed to `Europe/Skopje`, so "today" rolls over at the wrong hour elsewhere.
- Log entries are timestamped "now" with no way to edit the time, so readings can't be
  back-filled.
- Soft deletes have no restore UI.
- Email changes aren't verified.
- crispy-forms is still installed but renders nothing; it is queued for removal.
- HSTS is set to 7 days pending a full certificate renewal cycle on the new domain.

## How this was built

A large share of the code was generated with Claude Code. The domain rules it has to work
within (mmol/L storage, soft-delete filtering, per-user scoping, no PHI in logs) are
written down in [`CLAUDE.md`](CLAUDE.md) and enforced by the test suite, so a generated
change is held to the same standard as a hand-written one. The architecture and the
decisions about what ships are not generated.

## License

Released under the [MIT License](LICENSE). © Vedran Chichov
