"""What an unhandled 500 is allowed to say about the request that caused it.

`core.settings.LOGGING` mails 5xx to ADMINS so production failures are not
silent. Django builds that mail from `technical_500.txt`, which renders the
POST body and the cookies through SafeExceptionReporterFilter -- and that
filter redacts a value only when its *key* matches
API|AUTH|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE, or is the session cookie
name.

That heuristic is built for credentials, and it is the wrong shape for this
app. Here the ordinary field names are the sensitive ones: `value` is a
glucose reading, `units` an insulin dose, `note` free text a patient wrote.
None of them look like a credential, so a 500 during any log-entry POST mailed
the reading itself in clear text. Verified against the stock filter: a POST of
value=17.4 comes back in the report as `value = '17.4'`.

Cookies are the lesser half -- Django already redacts `sessionid` (by
SESSION_COOKIE_NAME) and `csrftoken` (it contains "TOKEN"). Redacting the rest
makes the posture default-deny, so a cookie added later is not exposed by the
mere fact that nobody thought to name it after a credential.

CLAUDE.md section 8 says health data stays out of logs and out of anything
shipped to an error reporter. This mail is an error reporter.
"""

from django.views.debug import SafeExceptionReporterFilter


class PHISafeExceptionReporterFilter(SafeExceptionReporterFilter):
    """Redact the whole request body and every cookie, not just credentials.

    Both overrides defer to `is_active()`, which is `DEBUG is False`. So the
    local yellow debug page still shows real values -- redacting there would
    only make development harder, and a developer looking at that page already
    has the data in front of them. Production, where the report is mailed, is
    where this bites.
    """

    def get_post_parameters(self, request):
        if request is None:
            return {}
        if not self.is_active(request):
            return super().get_post_parameters(request)
        # Key names are kept: knowing *which* field was posted is most of the
        # diagnostic value, and a field name is not health data.
        return {key: self.cleansed_substitute for key in request.POST}

    def get_safe_cookies(self, request):
        if not self.is_active(request):
            return super().get_safe_cookies(request)
        if not hasattr(request, "COOKIES"):
            return {}
        return {key: self.cleansed_substitute for key in request.COOKIES}
