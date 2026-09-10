import os
import sys

from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import staticfiles_storage
from django.test import override_settings
import logging
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.views.debug import ExceptionReporter

User = get_user_model()


class ErrorReportRedactionTest(TestCase):
    """A 500 mail must not carry the health data of the request that caused it.

    LOGGING mails 5xx to ADMINS. Django builds that mail from
    technical_500.txt, which renders the POST body, and its default filter
    redacts a value only when the *key* looks like a credential. In this app
    the ordinary field names are the sensitive ones -- `value` is a glucose
    reading, `note` is free text a patient wrote -- so a 500 during any log
    entry POST mailed the reading itself in clear text.

    Django already redacts the session cookie (by SESSION_COOKIE_NAME) and
    csrftoken (it contains "TOKEN"). The cookie assertions below cover the
    rest, which the stock filter passes through untouched.

    Asserted against the real report text rather than the filter's return
    value, so a future Django template change that reintroduces any of it is
    caught here.
    """

    factory = RequestFactory()

    def _report_text(self):
        request = self.factory.post(
            "/log/glucose/add",
            {"value": "17.4", "note": "felt awful after lunch", "context": "fasting"},
        )
        request.COOKIES["sessionid"] = "s3ss10n-c00k13-value"
        # Matches none of Django's patterns, so only the override redacts it.
        request.COOKIES["glucoread-last-reading"] = "17.4-mmol"

        try:
            raise ValueError("boom")
        except ValueError:
            return ExceptionReporter(request, *sys.exc_info()).get_traceback_text()

    @override_settings(DEBUG=False)
    def test_the_glucose_reading_is_not_in_the_report(self):
        report = self._report_text()
        self.assertNotIn("17.4", report)
        self.assertNotIn("felt awful after lunch", report)
        # The field names survive -- knowing which field was posted is the
        # diagnostic value, and a field name is not health data.
        self.assertIn("value", report)

    @override_settings(DEBUG=False)
    def test_no_cookie_value_reaches_the_report(self):
        report = self._report_text()
        self.assertNotIn("s3ss10n-c00k13-value", report)
        # The one Django's own patterns do not catch.
        self.assertNotIn("17.4-mmol", report)

    def test_the_filter_is_the_configured_one(self):
        self.assertEqual(
            settings.DEFAULT_EXCEPTION_REPORTER_FILTER,
            "main.reporting.PHISafeExceptionReporterFilter",
        )

    @override_settings(DEBUG=True)
    def test_local_debugging_still_sees_the_real_values(self):
        """Redacting the yellow debug page would only make development harder,
        and it is never mailed anywhere."""
        self.assertIn("17.4", self._report_text())


class ObservabilityConfigTest(TestCase):
    """Production failures were previously invisible.

    Django's default configuration mails unhandled 500s to ADMINS and does
    nothing else. ADMINS was unset and no LOGGING dict existed, so a production
    error reached no file, no stream and no inbox — and neither would a
    brute-force run against the auth endpoints.
    """

    def test_logging_is_configured(self):
        self.assertTrue(settings.LOGGING, "no LOGGING dict — 500s would be silent")
        self.assertIn("console", settings.LOGGING["handlers"])

    def test_server_errors_reach_a_stream_and_the_admins(self):
        handlers = {type(h).__name__ for h in logging.getLogger("django.request").handlers}
        self.assertIn("StreamHandler", handlers)
        self.assertIn("AdminEmailHandler", handlers)

    def test_loglevel_env_var_is_actually_read(self):
        """DJANGO_LOGLEVEL sat in .env unread for months; keep it wired."""
        self.assertEqual(
            logging.getLevelName(logging.getLogger("django").level),
            settings.DJANGO_LOGLEVEL,
        )

    def test_db_backend_logger_is_pinned_above_debug(self):
        """django.db.backends echoes query parameters at DEBUG — health data."""
        level = logging.getLogger("django.db.backends").level
        self.assertGreaterEqual(level, logging.INFO)


class MobileNavDrawerCssTest(TestCase):
    """The landing page's mobile drawer is `position: fixed` inside the topbar.

    Two properties of the topbar can take it off the screen, and both shipped
    together: `backdrop-filter` on the bar itself makes the bar the containing
    block for its fixed descendants (so the drawer resolved against 68px of bar
    instead of the viewport and collapsed off the top), and locking scroll with
    `overflow: hidden` on the root leaves `position: sticky` with no scrollport,
    dropping the whole bar — close button included — to its static position far
    above the fold. Neither is visible in a unit test, so guard the source.
    """

    CSS = Path(settings.BASE_DIR) / "main" / "static" / "main" / "css" / "theme.css"

    # matches `selector {...}` blocks, which is enough for this flat stylesheet
    RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")

    def _blocks_for(self, selector):
        css = self.CSS.read_text()
        return [
            body
            for sel, body in self.RULE.findall(css)
            if any(part.strip() == selector for part in sel.split(","))
        ]

    def test_the_topbar_itself_creates_no_containing_block(self):
        blocks = self._blocks_for(".topbar") + self._blocks_for(".topbar.is-stuck")
        self.assertTrue(blocks, "no .topbar rules found — has theme.css moved?")

        for body in blocks:
            for prop in ("backdrop-filter", "filter", "transform", "perspective"):
                self.assertNotIn(
                    prop,
                    body,
                    f"{prop} on .topbar itself captures the fixed mobile drawer; "
                    "paint the frosted bar on .topbar::before instead",
                )

    def test_the_frosted_bar_is_still_painted(self):
        """The fix must not have quietly deleted the blur along with the bug."""
        stuck = "".join(self._blocks_for(".topbar.is-stuck::before"))
        self.assertIn("backdrop-filter", stuck)
        self.assertIn("-webkit-backdrop-filter", stuck)

    def test_the_open_drawer_does_not_lock_scroll_on_the_root(self):
        css = self.CSS.read_text()
        for sel, body in self.RULE.findall(css):
            if "#menu.open" in sel or "nav-open" in sel:
                self.assertNotIn(
                    "overflow",
                    body,
                    "an overflow lock on <html> breaks the sticky topbar; "
                    "contain the drawer's own scroll instead",
                )


class StaticCacheBustingTest(TestCase):
    """Development static URLs must change when the file does.

    Production hashes filenames, so it is already safe; the regression this
    guards is the dev case, where an edited asset kept its URL and browsers
    went on serving the cached copy.
    """

    ASSET = "main/css/app.css"

    @override_settings(DEBUG=True)
    def test_debug_urls_carry_the_source_mtime(self):
        url = staticfiles_storage.url(self.ASSET)
        self.assertIn("?v=", url)

        stamp = url.split("?v=")[1]
        self.assertTrue(stamp.isdigit(), url)
        self.assertEqual(
            int(stamp), int(os.path.getmtime(finders.find(self.ASSET)))
        )

    @override_settings(DEBUG=True)
    def test_a_touched_file_gets_a_new_url(self):
        source = finders.find(self.ASSET)
        original = os.stat(source)
        before = staticfiles_storage.url(self.ASSET)
        try:
            os.utime(source, (original.st_atime, original.st_mtime + 60))
            self.assertNotEqual(staticfiles_storage.url(self.ASSET), before)
        finally:
            os.utime(source, (original.st_atime, original.st_mtime))

    @override_settings(DEBUG=False)
    def test_production_urls_are_untouched(self):
        """Outside DEBUG this must behave exactly as the manifest storage it
        subclasses — hashed name, no query string bolted on."""
        self.assertNotIn("?v=", staticfiles_storage.url(self.ASSET))

    @override_settings(DEBUG=True)
    def test_an_unknown_asset_does_not_raise(self):
        self.assertNotIn("?v=", staticfiles_storage.url("does/not/exist.css"))


class ContentSecurityPolicyTest(TestCase):
    """The policy has to be enforced AND the pages have to survive it.

    A CSP that ships with an un-nonced inline script does not fail loudly --
    the browser silently declines to run it, and here that would mean the theme
    never resolves before paint and the target-reset button does nothing. So
    these assert both halves: the header is present and strict, and every
    inline script in the app carries the nonce that lets it run.
    """

    NONCE = re.compile(r"'nonce-([A-Za-z0-9_-]+)'")

    def setUp(self):
        self.user = User.objects.create_user(
            username="csp", email="csp@example.com", password="pw12345!"
        )

    def test_html_responses_carry_the_policy(self):
        response = self.client.get(reverse("glucoread-home"))
        self.assertIn("Content-Security-Policy", response)

    def test_the_policy_closes_the_directives_that_matter(self):
        policy = self.client.get(reverse("glucoread-home"))["Content-Security-Policy"]
        self.assertIn("default-src 'self'", policy)
        self.assertIn("object-src 'none'", policy)
        self.assertIn("base-uri 'self'", policy)
        self.assertIn("form-action 'self'", policy)
        self.assertIn("frame-ancestors 'none'", policy)

    def test_script_src_does_not_allow_inline(self):
        """The whole point of the nonce. 'unsafe-inline' in script-src would
        make the policy decorative against the injection it exists to stop."""
        policy = self.client.get(reverse("glucoread-home"))["Content-Security-Policy"]
        script_src = next(
            part for part in policy.split("; ") if part.startswith("script-src")
        )
        self.assertNotIn("'unsafe-inline'", script_src)
        self.assertNotIn("'unsafe-eval'", script_src)

    def test_style_src_keeps_unsafe_inline_and_takes_no_nonce(self):
        """A nonce in style-src would disable 'unsafe-inline' for styles too
        and blank every style="" attribute in the templates."""
        policy = self.client.get(reverse("glucoread-home"))["Content-Security-Policy"]
        style_src = next(
            part for part in policy.split("; ") if part.startswith("style-src")
        )
        self.assertIn("'unsafe-inline'", style_src)
        self.assertNotIn("nonce-", style_src)

    def test_the_nonce_in_the_header_is_the_one_in_the_page(self):
        response = self.client.get(reverse("glucoread-home"))
        nonce = self.NONCE.search(response["Content-Security-Policy"]).group(1)
        self.assertIn(
            f'<script nonce="{nonce}">'.encode(),
            response.content,
            "the inline theme script does not carry the header's nonce, so a "
            "browser would refuse to run it",
        )

    def test_every_inline_script_on_an_authenticated_page_is_nonced(self):
        self.client.login(email="csp@example.com", password="pw12345!")
        for name in ("glucoread-dashboard", "user-profile", "add-glucose"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                html = response.content.decode()
                nonce = self.NONCE.search(
                    response["Content-Security-Policy"]
                ).group(1)
                for tag in re.findall(r"<script\b[^>]*>", html):
                    if "src=" in tag or 'type="application/json"' in tag:
                        continue
                    self.assertIn(
                        f'nonce="{nonce}"',
                        tag,
                        f"{name} has an inline script the CSP would block: {tag}",
                    )

    def test_the_nonce_is_not_reused_between_requests(self):
        first = self.client.get(reverse("glucoread-home"))
        second = self.client.get(reverse("glucoread-home"))
        self.assertNotEqual(
            self.NONCE.search(first["Content-Security-Policy"]).group(1),
            self.NONCE.search(second["Content-Security-Policy"]).group(1),
        )

    def test_no_template_uses_an_inline_event_handler(self):
        """Inline on* handlers cannot be authorised by a nonce, so one added
        later would stop working under this policy. Caught here instead."""
        offenders = []
        pattern = re.compile(r'\son(?:click|submit|change|input|load|error)\s*=')
        for template in Path(settings.BASE_DIR).glob("*/templates/**/*.html"):
            if pattern.search(template.read_text()):
                offenders.append(str(template.relative_to(settings.BASE_DIR)))
        self.assertEqual(offenders, [], f"inline event handlers found: {offenders}")

    @override_settings(CSP_REPORT_ONLY=True)
    def test_report_only_is_the_rollback_lever(self):
        """Re-instantiating the middleware is what a process restart does; the
        header name is read once at startup, not per request."""
        from main.middleware import ContentSecurityPolicyMiddleware

        middleware = ContentSecurityPolicyMiddleware(lambda request: None)
        self.assertEqual(
            middleware.header, "Content-Security-Policy-Report-Only"
        )
