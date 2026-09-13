import re
from datetime import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
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

    Chart.js is the only script this app loads from a CDN, and it loads on the
    authenticated dashboard only, with full DOM access. A version pin alone
    does not help if the CDN serves something else under that version, so the
    tag needs `integrity`. This asserts it over the rendered HTML rather than
    the template source, so a tag added via an include or a base template is
    covered too. The landing page carries no third-party script at all -- see
    the test below, which holds it to that.
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

    def test_the_landing_page_loads_no_third_party_script(self):
        """The landing page must load nothing executable from a third party.

        It used to draw its hero chart with Chart.js and was asserted to pin
        that tag. The figures are now inline SVG over static example data, so
        there is no CDN script left to pin -- and the page's own copy claims
        "no analytics script, no advertising network and no third-party tag on
        any page". That claim is what this now guards: a stronger property than
        the pinning it replaces, and the one a reader is relying on.

        `_assert_all_pinned` still runs, so the rule survives if a script is
        ever added back; the regex itself is guarded by the dashboard test
        above, which does still load Chart.js.
        """
        response = self.client.get(reverse("glucoread-home"))
        html = response.content.decode()
        self._assert_all_pinned(html, "the landing page")
        self.assertEqual(
            self._EXTERNAL_SCRIPT.findall(html),
            [],
            "the landing page states it carries no third-party tag; it now loads one",
        )


class ChartLabelTimezoneTest(TestCase):
    """The chart's x-axis has to agree with every other time on the page.

    `measured_at` comes back from the database as an aware UTC datetime, and
    strftime() formats whatever tzinfo it carries. So the labels were UTC while
    the activity list beside them went through the |date filter, which
    localises — the two disagreed by the offset.

    Across midnight it was worse than an offset. The queryset orders by real
    time and filters on the *local* date, so a local day's readings came out in
    the right order but carried the previous UTC day's hours: an axis reading
    22:00, 23:00, 00:00, 01:00 for one day.

    chart_date is passed explicitly throughout so these do not depend on what
    "today" is when the suite runs.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="tz", email="tz@example.com", password="pw12345!"
        )
        self.client.login(email="tz@example.com", password="pw12345!")

    def _reading_at(self, year, month, day, hour, minute):
        """Create a reading at a wall-clock time in the project's timezone."""
        moment = timezone.make_aware(
            datetime(year, month, day, hour, minute),
            timezone.get_current_timezone(),
        )
        return GlucoseLog.objects.create(
            user=self.user, value=Decimal("5.5"), measured_at=moment
        )

    def _labels_for(self, date_string):
        response = self.client.get(
            reverse("glucoread-dashboard"), {"chart_date": date_string}
        )
        return response.context["glucose_labels"]

    def test_a_reading_is_labelled_with_the_time_it_was_taken(self):
        self._reading_at(2026, 1, 15, 14, 30)
        self.assertEqual(self._labels_for("2026-01-15"), ["14:30"])

    def test_a_reading_just_after_midnight_keeps_its_own_date(self):
        """The case that made the axis wrap. In January the project timezone is
        UTC+1, so 00:30 local is 23:30 UTC on the *previous* day."""
        self._reading_at(2026, 1, 15, 0, 30)
        self.assertEqual(self._labels_for("2026-01-15"), ["00:30"])

    def test_a_summer_reading_uses_the_summer_offset(self):
        """July is UTC+2, so a fixed offset would not have fixed this either —
        it has to go through the timezone, not a constant."""
        self._reading_at(2026, 7, 15, 9, 15)
        self.assertEqual(self._labels_for("2026-07-15"), ["09:15"])

    def test_a_whole_day_reads_in_order_without_wrapping(self):
        for hour, minute in ((0, 15), (8, 0), (13, 45), (23, 50)):
            self._reading_at(2026, 1, 15, hour, minute)
        labels = self._labels_for("2026-01-15")
        self.assertEqual(labels, ["00:15", "08:00", "13:45", "23:50"])
        # Ordering is by real time, so a correct axis is also a sorted one.
        self.assertEqual(labels, sorted(labels))

    def test_the_labels_agree_with_the_activity_feed(self):
        """Both surfaces render the same reading; they must not disagree."""
        self._reading_at(2026, 1, 15, 6, 45)
        response = self.client.get(
            reverse("glucoread-dashboard"), {"chart_date": "2026-01-15"}
        )
        chart_label = response.context["glucose_labels"][0]
        feed_time = timezone.localtime(
            GlucoseLog.objects.get(user=self.user).measured_at
        ).strftime("%H:%M")
        self.assertEqual(chart_label, feed_time)
