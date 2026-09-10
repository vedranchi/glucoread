import secrets

from django.conf import settings


# middleware to prevent caching
class NoCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            response["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
        return response


# The directives that do not vary per request. The nonce is spliced into
# script-src below.
#
# script-src: 'self' for our own bundles, the CDN for Chart.js (pinned and
#   SRI-checked -- see dashboard.html), and a per-request nonce for the two
#   inline blocks that have to stay inline. Note that once a nonce is present
#   a browser IGNORES 'unsafe-inline' for scripts, which is the point: any
#   inline <script> without the nonce simply will not run. Adding one to a
#   template means adding nonce="{{ request.csp_nonce }}" with it.
#
# style-src: keeps 'unsafe-inline' for the handful of style="" attributes in
#   the templates, and deliberately carries NO nonce -- a nonce would disable
#   'unsafe-inline' here too and blank those elements. Style injection is a far
#   weaker vector than script injection, so this is a fair trade rather than a
#   hole.
#
# frame-ancestors replaces X-Frame-Options for browsers that honour it, and
# form-action stops an injected form posting credentials off-site.
# {nonce} below is substituted by str.replace, not str.format: a directive
# added later that legitimately contains a brace (a report-uri with a query,
# say) would make format() raise at request time on every page.
_NONCE_SLOT = "{nonce}"

_CSP_DIRECTIVES = (
    "default-src 'self'",
    f"script-src 'self' {_NONCE_SLOT} https://cdn.jsdelivr.net",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
)


class ContentSecurityPolicyMiddleware:
    """Serve a nonce-based CSP, and hand the nonce to the templates.

    Django 5.2 has no CSP support of its own. This is deliberately a few lines
    rather than a dependency: the policy is static apart from the nonce, and
    every inline script in the app is enumerable, so there is nothing here for
    a library to manage.

    The nonce is generated BEFORE the view runs, so the value rendered into the
    page and the value in the header are the same one. `request` is already in
    the template context via context_processors.request, so templates read
    {{ request.csp_nonce }} with no extra processor.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Report-only is the rollback lever. If a policy problem shows up in
        # production, this is a VM .env change rather than an image rollback --
        # the header still reports, but the browser stops enforcing it.
        self.header = (
            "Content-Security-Policy-Report-Only"
            if getattr(settings, "CSP_REPORT_ONLY", False)
            else "Content-Security-Policy"
        )

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)
        response = self.get_response(request)

        # Only HTML executes script. Skipping everything else keeps the header
        # off CSV exports and off the 304s WhiteNoise serves for static files.
        if "text/html" not in response.get("Content-Type", ""):
            return response

        # A response the middleware did not see rendered (a streaming file, an
        # early 304) can still be HTML, but it will not have used the nonce.
        # Setting the header regardless is correct: worst case it is stricter.
        policy = "; ".join(_CSP_DIRECTIVES).replace(
            _NONCE_SLOT, f"'nonce-{request.csp_nonce}'"
        )
        response.setdefault(self.header, policy)
        return response
