from decimal import Decimal

from django.test import TestCase
from django.core import mail
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from logs.conversions import (
    DEFAULT_TARGET_HIGH_MMOL,
    DEFAULT_TARGET_LOW_MMOL,
    mgdl_to_mmol,
    reading_status,
    to_display,
)
from logs.models import GlucoseLog
from users.models import UserPreferences

User = get_user_model()


# view loads
class PasswordResetTest(TestCase):
    def setUp(self):
        # rate-limit counters live in the cache; clear so state cannot leak
        # between tests and trip a limit unrelated to what is being asserted
        cache.clear()

    def test_password_reset_page_loads(self):
        response = self.client.get(reverse("password_reset"))
        self.assertEqual(response.status_code, 200)


# email is queued
class PasswordResetEmailTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="test", email="test@example.com", password="pass"
        )

    def test_password_reset_sends_email(self):
        self.client.post(reverse("password_reset"), {"email": "test@example.com"})
        self.assertEqual(len(mail.outbox), 1)


class LoginTest(TestCase):
    """Covers login_view, which authenticates via form.get_user().

    Email is the USERNAME_FIELD, so the credential is submitted in the form's
    field named "username" — the rate limiter keys off that same field.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="loginuser", email="login@example.com", password="pw12345!"
        )

    def test_valid_credentials_log_the_user_in(self):
        response = self.client.post(
            reverse("glucoread-login"),
            {"username": "login@example.com", "password": "pw12345!"},
        )
        self.assertRedirects(response, reverse("glucoread-dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_wrong_password_does_not_log_in(self):
        response = self.client.post(
            reverse("glucoread-login"),
            {"username": "login@example.com", "password": "nope"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)


class RateLimitTest(TestCase):
    """The auth endpoints send mail and verify credentials, so they must throttle."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="ratetest", email="rate@example.com", password="pw12345!"
        )

    def test_password_reset_throttles_by_target_address(self):
        """3/h per address — an inbox must not be floodable."""
        url = reverse("password_reset")
        for _ in range(3):
            self.assertEqual(
                self.client.post(url, {"email": "rate@example.com"}).status_code, 302
            )
        self.assertEqual(
            self.client.post(url, {"email": "rate@example.com"}).status_code, 403
        )
        # only the allowed attempts actually sent mail
        self.assertEqual(len(mail.outbox), 3)

    def test_login_throttles_by_username(self):
        """5/5m per credential, so one account cannot be ground down."""
        url = reverse("glucoread-login")
        creds = {"username": "rate@example.com", "password": "wrong"}
        for _ in range(5):
            self.assertEqual(self.client.post(url, creds).status_code, 200)
        self.assertEqual(self.client.post(url, creds).status_code, 403)

    def test_register_throttles_by_ip(self):
        url = reverse("glucoread-register")
        for i in range(10):
            self.client.post(url, {"username": f"u{i}", "email": f"u{i}@example.com"})
        self.assertEqual(self.client.post(url, {}).status_code, 403)

    def test_get_requests_are_not_throttled(self):
        """Only POSTs are limited, so a blocked visitor can still read the form."""
        cache.clear()
        url = reverse("password_reset")
        for _ in range(3):
            self.client.post(url, {"email": "rate@example.com"})
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_rate_limit_cache_is_shared_not_per_process(self):
        """LocMemCache would make limits per-worker, silently 3x too lenient."""
        from django.conf import settings

        self.assertNotIn("locmem", settings.CACHES["default"]["BACKEND"].lower())
        cache.set("shared-probe", "v", 30)
        self.assertEqual(cache.get("shared-probe"), "v")

    def test_cache_table_name_matches_the_migrations(self):
        """0001 creates the table, 0002 renames it; the name is coupled in three
        places.

        Renaming one without the others leaves every rate-limited view raising
        ProgrammingError on a real database. The test runner creates cache
        tables automatically, so no other test can catch that drift.
        """
        from importlib import import_module

        from django.conf import settings

        create = import_module("main.migrations.0001_create_cache_table")
        rename = import_module("main.migrations.0002_rename_cache_table")

        # 0002 has to rename the exact table 0001 created, ...
        self.assertEqual(create.CACHE_TABLE, rename.OLD_TABLE)
        # ... and settings has to point at what the last migration leaves behind.
        self.assertEqual(
            settings.CACHES["default"]["LOCATION"], rename.NEW_TABLE
        )


class ProfileUpdateTest(TestCase):
    """The profile page is one <form> covering three model forms at once.

    Regression coverage for the bug where a failing section (e.g. a bad
    email) saved the other, unrelated sections anyway and reported success —
    the user's actual edit vanished with no error shown.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="profileuser", email="profile@example.com", password="pw12345!"
        )
        self.client.login(email="profile@example.com", password="pw12345!")

    def _post(self, **overrides):
        data = {
            "username": self.user.username,
            "email": self.user.email,
            "glucose_unit": "mmol",
            "diabetes_type": "type1",
            "target_low": "3.9",
            "target_high": "10.0",
            "bread_unit_grams": "12.0",
        }
        data.update(overrides)
        return self.client.post(reverse("user-profile"), data)

    def test_valid_edit_saves_every_section(self):
        response = self._post(username="renamed", glucose_unit="mg/dL")
        self.assertRedirects(response, reverse("user-profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "renamed")
        self.assertEqual(self.user.preferences.glucose_unit, "mg/dL")

    def test_invalid_section_saves_nothing_and_shows_the_error(self):
        response = self._post(email="not-an-email", glucose_unit="mg/dL")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid email address")

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "profile@example.com")
        # a sibling section that validated fine must not be saved either --
        # the old code saved it and reported false success
        self.assertEqual(self.user.preferences.glucose_unit, "mmol")


class NoPublicTokenEndpointsTest(TestCase):
    """The JWT endpoints were public, unthrottled and served no API.

    They verified credentials for anyone who asked and issued tokens that
    could not be revoked. Nothing consumed them. If an API is built later it
    needs throttling and a token blacklist, so these must not come back by
    accident.
    """

    def test_token_endpoints_are_gone(self):
        for url in ("/users/api/token/", "/users/api/token/refresh/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url).status_code, 404)


class LoginNextRedirectTest(TestCase):
    """@login_required appends ?next=; sign-in used to ignore it.

    The user asked for one page, authenticated, and landed on the dashboard
    instead. `next` is validated against the current host — an unchecked one is
    an open redirect.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="nextuser", email="next@example.com", password="pw12345!"
        )

    def test_login_required_view_sends_the_user_back_where_they_asked(self):
        target = reverse("add-glucose")
        response = self.client.get(target)
        self.assertRedirects(
            response, f"{reverse('glucoread-login')}?next={target}"
        )

        response = self.client.post(
            reverse("glucoread-login"),
            {"username": "next@example.com", "password": "pw12345!", "next": target},
        )
        self.assertRedirects(response, target)

    def test_login_without_next_lands_on_the_dashboard(self):
        response = self.client.post(
            reverse("glucoread-login"),
            {"username": "next@example.com", "password": "pw12345!"},
        )
        self.assertRedirects(response, reverse("glucoread-dashboard"))

    def test_offsite_next_is_ignored(self):
        response = self.client.post(
            reverse("glucoread-login"),
            {
                "username": "next@example.com",
                "password": "pw12345!",
                "next": "https://evil.example.com/steal",
            },
        )
        self.assertRedirects(response, reverse("glucoread-dashboard"))


class AdminLoginRateLimitTest(TestCase):
    """The admin ships its own login view, outside every decorator in `users`.

    That left the superuser credential — the most valuable one in the app —
    taking unlimited guesses on the most scanned path on the internet, while an
    ordinary user was capped at five attempts. This pins the fix, because the
    gap is invisible: nothing fails, the form just answers forever.
    """

    def setUp(self):
        cache.clear()

    def test_admin_login_is_throttled_by_credential(self):
        from django.urls import reverse

        url = reverse("admin:login")
        creds = {"username": "root@example.com", "password": "wrong"}

        # the limit is 5/5m per submitted username
        for attempt in range(5):
            response = self.client.post(url, creds)
            self.assertNotEqual(
                response.status_code, 403, f"blocked early on attempt {attempt + 1}"
            )

        self.assertEqual(self.client.post(url, creds).status_code, 403)

    def test_admin_login_page_still_loads_for_a_blocked_client(self):
        """Only POSTs are limited, so a locked-out visitor can still read the page."""
        from django.urls import reverse

        url = reverse("admin:login")
        for _ in range(6):
            self.client.post(url, {"username": "root@example.com", "password": "x"})
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_admin_path_is_configurable(self):
        """Production moves the admin off the default path scanners probe."""
        from django.conf import settings

        self.assertTrue(settings.ADMIN_PATH.endswith("/"))


class GlucoseTargetTest(TestCase):
    """The in-range band is per-user, stored in mmol/L, typed in either unit."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="targetuser", email="target@example.com", password="pw12345!"
        )
        self.client.login(email="target@example.com", password="pw12345!")

    def _post(self, **overrides):
        data = {
            "username": self.user.username,
            "email": self.user.email,
            "glucose_unit": "mmol",
            "diabetes_type": "type1",
            "target_low": "3.9",
            "target_high": "10.0",
            "bread_unit_grams": "12.0",
        }
        data.update(overrides)
        return self.client.post(reverse("user-profile"), data)

    def test_new_preferences_default_to_the_standard_band(self):
        prefs = self.user.preferences
        self.assertEqual(prefs.target_low, DEFAULT_TARGET_LOW_MMOL)
        self.assertEqual(prefs.target_high, DEFAULT_TARGET_HIGH_MMOL)

    def test_targets_typed_in_mmol_are_stored_as_typed(self):
        self._post(target_low="4.5", target_high="8.5")
        self.user.preferences.refresh_from_db()
        self.assertEqual(self.user.preferences.target_low, Decimal("4.5"))
        self.assertEqual(self.user.preferences.target_high, Decimal("8.5"))

    def test_targets_typed_in_mgdl_are_converted_before_storage(self):
        prefs = self.user.preferences
        prefs.glucose_unit = UserPreferences.GLUCOSE_UNIT_MGDL
        prefs.save()

        self._post(glucose_unit="mg/dL", target_low="80", target_high="160")
        prefs.refresh_from_db()

        self.assertEqual(prefs.target_low, mgdl_to_mmol(Decimal("80")))
        self.assertEqual(prefs.target_high, mgdl_to_mmol(Decimal("160")))
        # and the stored value reads back as the number that was typed
        self.assertEqual(to_display(prefs.target_low, True), 80.0)
        self.assertEqual(to_display(prefs.target_high, True), 160.0)

    def test_a_unit_change_reads_the_targets_in_the_unit_on_screen(self):
        """The page was rendered in mmol/L, so "4.0" means 4.0 mmol/L even
        though the same submit switches the account to mg/dL."""
        self._post(glucose_unit="mg/dL", target_low="4.0", target_high="9.0")
        prefs = self.user.preferences
        prefs.refresh_from_db()

        self.assertEqual(prefs.glucose_unit, "mg/dL")
        self.assertEqual(prefs.target_low, Decimal("4.0"))
        self.assertEqual(prefs.target_high, Decimal("9.0"))

    def test_upper_target_must_exceed_the_lower_one(self):
        response = self._post(target_low="9.0", target_high="5.0")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "must be above the lower target")

        self.user.preferences.refresh_from_db()
        self.assertEqual(self.user.preferences.target_low, DEFAULT_TARGET_LOW_MMOL)

    def test_equal_targets_are_rejected(self):
        response = self._post(target_low="6.0", target_high="6.0")
        self.assertContains(response, "must be above the lower target")

    def test_bread_unit_size_is_editable_and_rejects_a_zero_divisor(self):
        response = self._post(bread_unit_grams="10.0")
        self.assertRedirects(response, reverse("user-profile"))
        self.user.preferences.refresh_from_db()
        self.assertEqual(self.user.preferences.bread_unit_grams, Decimal("10.0"))

        response = self._post(bread_unit_grams="0")
        self.assertEqual(response.status_code, 200)
        self.user.preferences.refresh_from_db()
        # unchanged -- a zero would be a division by zero on every meal row
        self.assertEqual(self.user.preferences.bread_unit_grams, Decimal("10.0"))

    def test_reset_control_offers_the_defaults_in_mmol(self):
        response = self.client.get(reverse("user-profile"))
        self.assertContains(response, 'data-target-low="3.9"')
        self.assertContains(response, 'data-target-high="10.0"')

    def test_reset_control_converts_the_defaults_for_a_mgdl_user(self):
        """70.2, not a round 70 -- the honest conversion of the stored
        default. Rounding it in the template would move the user's band."""
        prefs = self.user.preferences
        prefs.glucose_unit = UserPreferences.GLUCOSE_UNIT_MGDL
        prefs.save()

        response = self.client.get(reverse("user-profile"))
        self.assertContains(response, 'data-target-low="70.2"')
        self.assertContains(response, 'data-target-high="180.0"')

    def test_reset_handler_is_inline_not_in_a_cacheable_static_file(self):
        """The page is no-store; profile.js is not. Serving the handler from
        the static file let a stale cached copy leave the button dead."""
        response = self.client.get(reverse("user-profile"))
        self.assertContains(response, "data-reset-targets")
        # the listener itself, not just the button, must be in the response
        self.assertContains(response, "addEventListener")

    def test_reset_button_does_not_submit_the_form(self):
        """It fills the inputs only; a default-type button inside the form
        would submit every section instead."""
        response = self.client.get(reverse("user-profile"))
        self.assertContains(response, 'type="button"')

    def test_an_implausible_target_is_rejected_in_the_users_own_unit(self):
        response = self._post(target_low="0.2", target_high="10.0")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "between 1 and 40 mmol/L")

        self.user.preferences.refresh_from_db()
        self.assertEqual(self.user.preferences.target_low, DEFAULT_TARGET_LOW_MMOL)


class ReadingStatusTest(TestCase):
    """Classification is driven by the band it is handed, not by a constant."""

    def test_classifies_against_the_supplied_band(self):
        low, high = Decimal("4.0"), Decimal("9.0")
        self.assertEqual(reading_status(Decimal("3.9"), low, high)[1], "Low")
        self.assertEqual(reading_status(Decimal("4.0"), low, high)[1], "In range")
        self.assertEqual(reading_status(Decimal("9.0"), low, high)[1], "In range")
        self.assertEqual(reading_status(Decimal("9.1"), low, high)[1], "High")

    def test_the_same_reading_changes_status_when_the_band_narrows(self):
        reading = Decimal("9.5")
        wide = reading_status(reading, Decimal("3.9"), Decimal("10.0"))
        narrow = reading_status(reading, Decimal("4.0"), Decimal("9.0"))
        self.assertEqual(wide[1], "In range")
        self.assertEqual(narrow[1], "High")


class TimeInRangeUsesUserTargetsTest(TestCase):
    """The rail meter and header chip must follow the user's own band."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="tiruser", email="tir@example.com", password="pw12345!"
        )
        self.client.login(email="tir@example.com", password="pw12345!")
        now = timezone.now()
        for value in ("5.0", "9.5", "11.0"):
            GlucoseLog.objects.create(
                user=self.user, value=Decimal(value), measured_at=now
            )

    def test_default_band_counts_two_of_three_in_range(self):
        response = self.client.get(reverse("glucoread-dashboard"))
        self.assertEqual(response.context["time_in_range"], 67)
        self.assertEqual(response.context["in_range_count"], 2)

    def test_narrowing_the_band_drops_the_reading_that_no_longer_fits(self):
        prefs = self.user.preferences
        prefs.target_high = Decimal("9.0")
        prefs.save()

        response = self.client.get(reverse("glucoread-dashboard"))
        self.assertEqual(response.context["in_range_count"], 1)
        self.assertEqual(response.context["time_in_range"], 33)

    def test_the_chart_band_is_labelled_with_the_users_own_targets(self):
        prefs = self.user.preferences
        prefs.target_low = Decimal("4.4")
        prefs.target_high = Decimal("9.0")
        prefs.save()

        response = self.client.get(reverse("glucoread-dashboard"))
        self.assertEqual(response.context["range_low"], 4.4)
        self.assertEqual(response.context["range_high"], 9.0)
