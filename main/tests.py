import os

from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import staticfiles_storage
from django.test import override_settings
import logging
import re
from pathlib import Path

from django.conf import settings
from django.test import TestCase


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
