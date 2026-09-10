#!/usr/bin/env bash
#
# Pull-based deploy. Run on a systemd timer (deploy/glucolog-redeploy.timer);
# see deploy/README.md for installation.
#
# Checks GHCR for a newer image published by CI, and the deploy branch for
# changed compose/proxy config. Restarts the app only when something actually
# changed, so the timer is free to run often and stay silent.
#
# Deliberately pull-based: nothing inbound is opened, and no VM SSH key has to
# live in GitHub Secrets.
set -euo pipefail

cd /opt/glucolog

COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
BRANCH="${GLUCOLOG_BRANCH:-dev}"
IMAGE="ghcr.io/vedranchi/glucoread:${GLUCOLOG_TAG:-dev}"
CONTAINER="glucolog_web"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

changed=0

# Survives the re-exec below. Without it the re-executed process starts fresh,
# re-runs the config check against an already-fast-forwarded checkout, sees no
# difference, and forgets the config ever moved.
config_changed="${GLUCOLOG_CONFIG_CHANGED:-0}"
if [ "$config_changed" -eq 1 ]; then
    changed=1
fi

# --- config: compose files, Caddyfile, deploy scripts ---------------------
# --ff-only so a surprise divergence fails loudly instead of auto-merging on a
# production host. .env and email.env are gitignored and untouched by this.
config_before="$(git rev-parse HEAD)"
git fetch --quiet origin "$BRANCH"
if ! git merge --ff-only --quiet "origin/$BRANCH" 2>/dev/null; then
    log "ERROR: cannot fast-forward to origin/$BRANCH — the VM checkout has diverged."
    log "       Resolve by hand in /opt/glucolog; leaving the running app alone."
    exit 1
fi
config_after="$(git rev-parse HEAD)"

if [ "$config_before" != "$config_after" ]; then
    log "config updated: ${config_before:0:7} -> ${config_after:0:7}"
    changed=1
    config_changed=1

    # That pull may have just rewritten *this file*. Bash reads a script lazily
    # by byte offset, so editing one mid-run can make it resume at the wrong
    # place and execute garbage. Re-exec so the rest of the deploy runs the
    # version we actually just fetched. The guard stops it looping.
    if [ -z "${GLUCOLOG_REEXEC:-}" ]; then
        log "re-executing $0 after self-update"
        GLUCOLOG_REEXEC=1 GLUCOLOG_CONFIG_CHANGED=1 exec "$0" "$@"
    fi
fi

# --- image: whatever CI last published ------------------------------------
if ! "${COMPOSE[@]}" pull --quiet web; then
    log "ERROR: could not pull $IMAGE — leaving the running app alone."
    exit 1
fi

# Compare what the container is actually running against what we intend to run,
# rather than whether this particular pull changed anything. Those two answers
# differ whenever the image moved by some route other than this script: someone
# pulled by hand, the container was recreated from a stale local build, or the
# compose image reference itself changed. A pull-diff check calls every one of
# those "no change" and leaves production on the wrong image indefinitely.
# Converging on desired state is self-healing and costs one extra inspect.
running="$(docker inspect "$CONTAINER" --format '{{.Image}}' 2>/dev/null || echo none)"
desired="$(docker image inspect "$IMAGE" --format '{{.Id}}')"

if [ "$running" != "$desired" ]; then
    log "image drift: running ${running#sha256:}, want ${desired#sha256:}"
    changed=1
fi

if [ "$changed" -eq 0 ]; then
    exit 0
fi

# The container runs migrate + collectstatic on boot, so `up -d` is the whole
# deploy.
#
# All services, not just `web`. The config step above fast-forwards the
# Caddyfile and the compose files, but this used to recreate only `web` — so a
# proxy change landed in the checkout and was never applied, then took effect at
# whatever unrelated moment Caddy happened to restart next. Compose is
# declarative and only recreates what actually differs, so naming no service is
# both correct and a no-op for anything unchanged.
log "redeploying"
"${COMPOSE[@]}" up -d

# Caddy's config is bind-mounted, and compose compares service definitions
# rather than the contents of what those services mount. So `up -d` leaves the
# proxy running its old in-memory config however much the Caddyfile on disk has
# changed -- which is how a redirect could ship, appear deployed, and do
# nothing. Reload it explicitly.
#
# `caddy reload` over `restart`: it adapts and validates the new config first
# and keeps the running one if that fails, so a broken Caddyfile fails this step
# loudly instead of taking the site down. Verified against caddy:2 -- exit 1 on a
# bad config, container still serving.
#
# But a reload is only as good as the file the CONTAINER can see, and that is
# not automatically the file in this checkout. The Caddyfile used to be mounted
# as a single file; Docker resolves that to an inode at container start, and git
# replaces files rather than editing them in place, so after a fast-forward the
# container went on reading the pre-merge Caddyfile. `caddy reload` then
# validated and applied that stale file and reported success -- a green log line
# for a change that never landed. That is how the security headers on /static/
# and /media/ sat merged and undeployed.
#
# The mount is a directory now (docker-compose.prod.yml), which does not have
# that failure mode. This compares anyway rather than trusting it: the whole
# point is that the previous failure was silent, and only a comparison against
# the checkout can catch the next variant of it.
if [ "$config_changed" -eq 1 ]; then
    if ! "${COMPOSE[@]}" exec -T caddy cat /etc/caddy/Caddyfile 2>/dev/null \
        | diff -q - deploy/caddy/Caddyfile > /dev/null 2>&1; then
        log "caddy cannot see the checked-out Caddyfile — recreating the container"
        # Recreating re-resolves the mount. It costs a moment of downtime on the
        # proxy and gives up reload's validate-first safety, so it is the
        # fallback rather than the routine path.
        "${COMPOSE[@]}" up -d --force-recreate caddy
    else
        log "reloading caddy"
        if "${COMPOSE[@]}" exec -T caddy \
            caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile; then
            log "caddy reloaded"
        else
            log "ERROR: caddy reload failed — the proxy is still serving the previous"
            log "       config. Fix the Caddyfile; the app itself is unaffected."
        fi
    fi
fi

# Untagged parents of the image we just replaced. Disk is cheap here (39G free)
# but an unbounded image history on a free-tier box is not.
docker image prune -f --filter "dangling=true" > /dev/null

log "deploy complete: $("${COMPOSE[@]}" ps --format '{{.Name}} {{.Status}}' web)"
