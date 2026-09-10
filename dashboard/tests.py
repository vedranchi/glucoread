import re
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from logs.models import GlucoseLog, InsulinLog, MealLog

User = get_user_model()


class DashboardAccessTest(TestCase):
    def test_redirect_if_not_logged_in(self):
        self.client.logout()
        response = self.client.get(reverse("glucoread-dashboard"))
        self.assertEqual(response.status_code, 302)


class DashboardContextTest(TestCase):
    def setUp(self):
        # email is the USERNAME_FIELD, so login must use the email credential
        self.user = User.objects.create_user(
            username="test", email="test@example.com", password="test123"
        )
        self.client.login(email="test@example.com", password="test123")

    def test_dashboard_context_contains_recent_activity(self):
        response = self.client.get(reverse("glucoread-dashboard"))
        self.assertIn("recent_activity", response.context)


class DashboardAggregationTest(TestCase):
    """Covers the DB-level aggregation that replaced summing querysets in Python."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="agguser", email="agg@example.com", password="pw12345!"
        )
        self.client.login(email="agg@example.com", password="pw12345!")

    def test_averages_and_totals_reflect_todays_logs(self):
        GlucoseLog.objects.create(user=self.user, value=Decimal("5.0"))
        GlucoseLog.objects.create(user=self.user, value=Decimal("7.0"))
        InsulinLog.objects.create(
            user=self.user, insulin_type="bolus", units=Decimal("2.5")
        )
        MealLog.objects.create(user=self.user, carbs=Decimal("30.0"))
        # a meal with no carbs entered must not crash SUM or drop the other total
        MealLog.objects.create(user=self.user, carbs=None)

        response = self.client.get(reverse("glucoread-dashboard"))

        self.assertEqual(response.context["avg_glucose"], Decimal("6.0"))
        self.assertEqual(response.context["total_insulin"], Decimal("2.5"))
        self.assertEqual(response.context["carbs_consumed"], Decimal("30.0"))
        self.assertEqual(response.context["glucose_count_today"], 2)
        self.assertEqual(response.context["meal_count_today"], 2)

    def test_no_logs_today_reports_none_not_zero(self):
        response = self.client.get(reverse("glucoread-dashboard"))
        self.assertIsNone(response.context["avg_glucose"])
        self.assertIsNone(response.context["total_insulin"])
        self.assertIsNone(response.context["carbs_consumed"])


class RecentActivityLabelTest(TestCase):
    """MealLog.note is nullable, and the demo seeder creates meals without one.

    The label was built with an f-string, so those rendered as the literal text
    "Meal (None)" in Recent Activity — including in the screenshots.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="labeluser", email="label@example.com", password="pw12345!"
        )
        self.client.login(email="label@example.com", password="pw12345!")

    def _labels(self):
        response = self.client.get(reverse("glucoread-dashboard"))
        return [item["label"] for item in response.context["recent_activity"]]

    def test_meal_without_a_note_has_no_none_in_its_label(self):
        MealLog.objects.create(user=self.user, note=None, context="lunch")
        self.assertEqual(self._labels(), ["Meal"])

    def test_meal_with_a_note_still_shows_it(self):
        MealLog.objects.create(user=self.user, note="Chicken wrap", context="lunch")
        self.assertEqual(self._labels(), ["Meal (Chicken wrap)"])

class ExternalScriptIntegrityTest(TestCase):
    """Every third-party script must be pinned AND hash-checked.

    Chart.js is the only script this app loads from a CDN, and it runs on the
    authenticated dashboard with full DOM access. A version pin alone does not
    help if the CDN serves something else under that version, so the tag needs
    `integrity`. This asserts it over the rendered HTML rather than the
    template source, so a tag added via an include or a base template is
    covered too.
    """

    # src="..." on any absolute URL, plus whatever else is in the tag.
    _EXTERNAL_SCRIPT = re.compile(
        r"<script\b[^>]*\bsrc=[\"']https?://[^>]*>", re.IGNORECASE | re.DOTALL
    )

    def setUp(self):
        self.user = User.objects.create_user(
            username="sri", email="sri@example.com", password="pw12345!"
        )

    def _assert_all_pinned(self, html, page):
        tags = self._EXTERNAL_SCRIPT.findall(html)
        for tag in tags:
            self.assertIn(
                "integrity=",
                tag,
                f"{page} loads a script from a third party with no subresource "
                f"integrity hash: {tag[:120]}",
            )
            # Without CORS the browser cannot read the response to hash it, and
            # silently declines to enforce integrity at all.
            self.assertIn("crossorigin=", tag, f"{page}: {tag[:120]}")
        return tags

    def test_the_dashboard_pins_every_external_script(self):
        self.client.login(email="sri@example.com", password="pw12345!")
        response = self.client.get(reverse("glucoread-dashboard"))
        tags = self._assert_all_pinned(
            response.content.decode(), "the dashboard"
        )
        # Guards the regex itself: if it stops matching, the loop above passes
        # vacuously and this test would protect nothing.
        self.assertTrue(tags, "expected the dashboard to load Chart.js from a CDN")

    def test_the_landing_page_pins_every_external_script(self):
        response = self.client.get(reverse("glucoread-home"))
        tags = self._assert_all_pinned(
            response.content.decode(), "the landing page"
        )
        self.assertTrue(tags, "expected the landing page to load Chart.js from a CDN")
