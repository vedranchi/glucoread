"""Static file storage.

Production is unchanged: WhiteNoise's manifest storage, which hashes every
filename, so a changed file gets a new URL and caches can never serve a stale
one.

Development has no such protection. WhiteNoise skips hashing when DEBUG is on,
runserver's static handler sends only a Last-Modified header — no Cache-Control
and no ETag — and a browser handed that applies *heuristic* freshness: roughly
a tenth of the file's age. An asset that has sat unchanged for a week therefore
earns hours of no-revalidate caching, so editing it changes nothing on screen
and the edit looks like it failed. That has now cost two debugging rounds.

Appending the source file's mtime gives the URL the same property hashing gives
it in production, without requiring collectstatic on every edit.
"""

import os

from django.conf import settings
from django.contrib.staticfiles import finders
from whitenoise.storage import CompressedManifestStaticFilesStorage


class CacheBustingStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """Manifest storage in production; mtime-stamped URLs in development."""

    def url(self, name, force=False):
        url = super().url(name, force)

        # DEBUG is read per call rather than at import, so the test suite —
        # which forces DEBUG off — still exercises the manifest path exactly as
        # CI and production do. Without that, a missing manifest entry would
        # stop being caught locally.
        if not settings.DEBUG:
            return url

        # finders.find resolves through the app directories, which is where the
        # file being edited actually lives. STATIC_ROOT holds whatever the last
        # collectstatic copied there, and would report a stale mtime.
        source = finders.find(name)
        if not source:
            return url

        try:
            stamp = int(os.path.getmtime(source))
        except OSError:
            return url

        separator = "&" if "?" in url else "?"
        return f"{url}{separator}v={stamp}"
