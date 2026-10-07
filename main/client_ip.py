"""The client address the rate limiter counts against.

django-ratelimit's `key="ip"` reads REMOTE_ADDR by default. Behind Caddy that is
the proxy container's address for every request, so each per-IP limit became one
bucket shared by the whole internet: ten failed sign-ins from anyone locked
everyone out for five minutes, and registration and password reset were capped
site-wide.

Caddy records the real peer in X-Forwarded-For. Only its *last* entry is
trustworthy -- anything before it arrived from the client and can say anything
-- so that is the one used. Trusting the header at all is safe only because
`web` is reachable solely through Caddy (docker-compose.prod.yml exposes it to
the compose network and publishes nothing), which is why it is a setting that
defaults to on only when DEBUG is off.
"""

import ipaddress

from django.conf import settings


def client_ip(request):
    """Return the address to rate-limit this request by."""
    if getattr(settings, "TRUST_PROXY_CLIENT_IP", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        candidate = forwarded.rsplit(",", 1)[-1].strip()
        try:
            # Round-trip through ipaddress so a malformed header can neither
            # 500 the view (ratelimit builds an ip_network from this) nor be
            # used to mint a fresh bucket per request.
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            pass
    # No proxy in front (dev), or a header we can't use: fall back to the peer.
    # Behind the proxy that is the shared bucket again -- stricter, never looser.
    return request.META["REMOTE_ADDR"]
