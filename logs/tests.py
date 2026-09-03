import csv
import io
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.forms.models import model_to_dict
from django.urls import reverse
from logs.models import GlucoseLog, InsulinLog, MealLog
from logs.conversions import (
    DEFAULT_BREAD_UNIT_GRAMS,
    MMOL_QUANTUM,
    MMOL_TO_MGDL,
    mgdl_to_mmol,
    to_bread_units,
)
from users.models import UserPreferences
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


# test the glucose log model
class GlucoseLogModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test", password="tester123")

    def test_glucose_log_creation(self):
        log = GlucoseLog.objects.create(
            user=self.user, value=6.0, measured_at="2025-01-01T20:00:00Z"
        )
        # test user and value data
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.value, 6.0)

    def test_string_representation_contains_no_health_data(self):
        """__str__ is captured by tracebacks, error reporters and admin logs.

        This test previously asserted the opposite — that the reading appeared
        in __str__ — which is exactly the behaviour that would have shipped a
        patient's glucose value to any third-party error reporter.
        """
        log = GlucoseLog.objects.create(
            user=self.user, value=Decimal("5.8"), measured_at="2025-01-01T21:00:00Z"
        )
        rendered = str(log)
        self.assertNotIn("5.8", rendered)
        self.assertNotIn(self.user.username, rendered)
        self.assertNotIn("2025-01-01", rendered)
        # still identifies the row well enough to look it up on purpose
        self.assertEqual(rendered, f"GlucoseLog #{log.pk}")

    def test_all_log_models_keep_measurements_out_of_str(self):
        insulin = InsulinLog.objects.create(
            user=self.user, units=Decimal("8.5"), insulin_type="bolus"
        )
        meal = MealLog.objects.create(
            user=self.user, carbs=Decimal("42.0"), context="lunch"
        )
        self.assertEqual(str(insulin), f"InsulinLog #{insulin.pk}")
        self.assertNotIn("8.5", str(insulin))
        self.assertEqual(str(meal), f"MealLog #{meal.pk}")
        self.assertNotIn("lunch", str(meal))


class SevenDayWindowTest(TestCase):
    """The 7-day detail list is a rolling window, not a calendar range.

    Replaces a test that logged in with positional create_user() args — setting
    email="test123" and an unusable password — so the login silently failed and
    was never asserted, and which then queried the ORM directly. It would have
    passed with logs/views/ deleted.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="window", email="window@example.com", password="pw12345!"
        )
        self.client.login(email="window@example.com", password="pw12345!")

    def test_only_the_last_seven_days_reach_the_page(self):
        recent = GlucoseLog.objects.create(user=self.user, value=Decimal("5.2"))
        GlucoseLog.objects.create(user=self.user, value=Decimal("6.8"))
        GlucoseLog.objects.filter(pk=recent.pk).update(
            measured_at=timezone.now() - timedelta(days=10)
        )

        response = self.client.get(reverse("log-glucose"))
        self.assertEqual(response.status_code, 200)
        values = [r["value"] for r in response.context["recent_seven_days"]]
        self.assertEqual(values, [6.8])

    def test_a_soft_deleted_reading_is_excluded(self):
        GlucoseLog.objects.create(
            user=self.user, value=Decimal("7.1"), is_deleted=True
        )
        response = self.client.get(reverse("log-glucose"))
        self.assertEqual(response.context["recent_seven_days"], [])


# unit conversion
class UnitConversionTest(TestCase):
    """Exercises the real conversion path through the views.

    The previous version of this test multiplied two numbers together inside
    its own assertion and imported nothing from the application, so it would
    have passed with every conversion in the codebase deleted.

    Glucose is stored canonically in mmol/L; mg/dL exists only at the edges.
    A bug here shows the user a reading that is wrong by a factor of 18, which
    is the most dangerous class of error this app can produce.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="mgdl", email="mgdl@example.com", password="pw12345!"
        )
        prefs = self.user.preferences
        prefs.glucose_unit = UserPreferences.GLUCOSE_UNIT_MGDL
        prefs.save()
        self.client.login(email="mgdl@example.com", password="pw12345!")

    def test_mgdl_input_is_stored_as_mmol(self):
        self.client.post(
            reverse("add-glucose"), {"value": "100", "context": "fasting"}
        )
        log = GlucoseLog.objects.get(user=self.user)
        # 100 / 18 = 5.5555... quantised to three decimal places
        self.assertEqual(log.value, Decimal("5.556"))

    def test_mgdl_user_sees_mgdl_on_the_log_page(self):
        GlucoseLog.objects.create(user=self.user, value=Decimal("5.556"))
        response = self.client.get(reverse("log-glucose"))
        self.assertEqual(response.context["unit_label"], "mg/dL")
        # 5.556 * 18 = 100.008 -> 100.0. What was entered as 100 mg/dL comes
        # back as 100 mg/dL; at 1 decimal place this read 100.8.
        self.assertEqual(response.context["current_glucose_value"], 100.0)

    def test_every_accepted_mgdl_value_round_trips_exactly(self):
        """Storing in mmol/L must not perturb what a mg/dL user typed.

        The two units share no common grid, so the stored precision has to be
        fine enough that quantising and converting back lands on the original.
        Sweeping the whole accepted range is what pins that: spot-checking
        passes at 2 decimal places too, where 44% of values are actually off.
        Fails if GlucoseLog.value.decimal_places and MMOL_QUANTUM drift apart.
        """
        for mgdl in range(20, 701):
            stored = mgdl_to_mmol(Decimal(mgdl))
            displayed = round(float(stored) * MMOL_TO_MGDL, 1)
            self.assertEqual(
                displayed, float(mgdl), f"{mgdl} mg/dL -> {stored} -> {displayed}"
            )

    def test_stored_precision_matches_the_quantum(self):
        """MMOL_QUANTUM is only correct if the column can actually hold it."""
        field = GlucoseLog._meta.get_field("value")
        self.assertEqual(
            Decimal(1).scaleb(-field.decimal_places).normalize(),
            MMOL_QUANTUM.normalize(),
        )

    def test_mmol_user_sees_the_stored_value_untouched(self):
        other = User.objects.create_user(
            username="mmol", email="mmol@example.com", password="pw12345!"
        )
        GlucoseLog.objects.create(user=other, value=Decimal("5.6"))
        self.client.force_login(other)
        response = self.client.get(reverse("log-glucose"))
        self.assertEqual(response.context["unit_label"], "mmol/L")
        self.assertEqual(response.context["current_glucose_value"], 5.6)


class CrossUserIsolationTest(TestCase):
    """One user must never reach another user's medical records.

    Authorisation is enforced by `get_object_or_404(..., user=request.user)` in
    every log view. That is correct today but nothing pinned it, so a single
    dropped filter in a future refactor would leak another person's glucose,
    insulin and meal history with the whole suite still green.

    404 is asserted rather than 403 on purpose: a 403 would confirm the record
    exists, which is itself a disclosure.
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner", email="owner@example.com", password="pw12345!"
        )
        self.intruder = User.objects.create_user(
            username="intruder", email="intruder@example.com", password="pw12345!"
        )
        self.glucose = GlucoseLog.objects.create(
            user=self.owner, value=Decimal("6.2"), note="owner glucose"
        )
        self.insulin = InsulinLog.objects.create(
            user=self.owner, units=Decimal("8.0"), insulin_type="bolus"
        )
        self.meal = MealLog.objects.create(
            user=self.owner, carbs=Decimal("45.0"), context="lunch"
        )
        self.client.login(email="intruder@example.com", password="pw12345!")

    def _cases(self):
        return [
            ("glucose", "edit-glucose", "delete-glucose", self.glucose),
            ("insulin", "edit-insulin", "delete-insulin", self.insulin),
            ("meal", "edit-meal", "delete-meal", self.meal),
        ]

    def test_cannot_open_another_users_edit_form(self):
        for label, edit, _delete, obj in self._cases():
            with self.subTest(model=label):
                response = self.client.get(reverse(edit, kwargs={"pk": obj.pk}))
                self.assertEqual(response.status_code, 404)

    def test_cannot_edit_another_users_record(self):
        payloads = {
            "glucose": {"value": "9.9", "context": "fasting"},
            "insulin": {"units": "99", "insulin_type": "basal"},
            "meal": {"carbs": "999", "context": "dinner"},
        }
        for label, edit, _delete, obj in self._cases():
            with self.subTest(model=label):
                before = obj.__class__.objects.get(pk=obj.pk)
                response = self.client.post(
                    reverse(edit, kwargs={"pk": obj.pk}), payloads[label]
                )
                self.assertEqual(response.status_code, 404)
                after = obj.__class__.objects.get(pk=obj.pk)
                # the owner's data must be byte-for-byte untouched
                self.assertEqual(
                    model_to_dict(before), model_to_dict(after), f"{label} was modified"
                )

    def test_cannot_delete_another_users_record(self):
        for label, _edit, delete, obj in self._cases():
            with self.subTest(model=label):
                response = self.client.post(reverse(delete, kwargs={"pk": obj.pk}))
                self.assertEqual(response.status_code, 404)
                obj.refresh_from_db()
                self.assertFalse(obj.is_deleted, f"{label} was soft-deleted")
                self.assertIsNone(obj.deleted_at)

    def test_another_users_records_never_appear_in_list_views(self):
        for name in ("log-glucose", "log-insulin", "log-meal", "glucoread-dashboard"):
            with self.subTest(view=name):
                body = self.client.get(reverse(name)).content.decode()
                self.assertNotIn("owner glucose", body)

    def test_intruder_sees_empty_aggregates_not_the_owners_totals(self):
        response = self.client.get(reverse("glucoread-dashboard"))
        self.assertIsNone(response.context["avg_glucose"])
        self.assertIsNone(response.context["total_insulin"])
        self.assertIsNone(response.context["carbs_consumed"])
        self.assertEqual(response.context["glucose_count_today"], 0)


class SoftDeleteExclusionTest(TestCase):
    """Soft-deleted medical records must disappear from reads AND from totals.

    Every query filters `is_deleted=False` by hand — there is no default
    manager enforcing it. The aggregate paths are the risk: a deleted reading
    silently included in an average or a daily carb total is wrong data
    presented as fact, and is far less visible than a row reappearing in a list.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="sd", email="sd@example.com", password="pw12345!"
        )
        self.client.login(email="sd@example.com", password="pw12345!")
        self.kept = GlucoseLog.objects.create(user=self.user, value=Decimal("6.0"))
        self.removed = GlucoseLog.objects.create(
            user=self.user, value=Decimal("12.0"), note="deleted reading"
        )
        InsulinLog.objects.create(user=self.user, units=Decimal("4.0"), insulin_type="bolus")
        self.removed_insulin = InsulinLog.objects.create(
            user=self.user, units=Decimal("10.0"), insulin_type="basal"
        )
        MealLog.objects.create(user=self.user, carbs=Decimal("30.0"), context="lunch")
        self.removed_meal = MealLog.objects.create(
            user=self.user, carbs=Decimal("70.0"), context="dinner"
        )
        for obj in (self.removed, self.removed_insulin, self.removed_meal):
            obj.is_deleted = True
            obj.deleted_at = timezone.now()
            obj.save()

    def test_deleted_reading_is_excluded_from_the_glucose_average(self):
        response = self.client.get(reverse("log-glucose"))
        # only the 6.0 remains; including 12.0 would average to 9.0
        self.assertEqual(float(response.context["avg_glucose"]), 6.0)
        self.assertEqual(response.context["reading_count"], 1)

    def test_deleted_dose_is_excluded_from_the_insulin_total(self):
        response = self.client.get(reverse("log-insulin"))
        self.assertEqual(float(response.context["total_units_today"]), 4.0)

    def test_deleted_meal_is_excluded_from_the_carb_total(self):
        response = self.client.get(reverse("log-meal"))
        self.assertEqual(float(response.context["carbs_today"]), 30.0)

    def test_dashboard_totals_exclude_deleted_records(self):
        response = self.client.get(reverse("glucoread-dashboard"))
        self.assertEqual(float(response.context["avg_glucose"]), 6.0)
        self.assertEqual(float(response.context["total_insulin"]), 4.0)
        self.assertEqual(float(response.context["carbs_consumed"]), 30.0)

    def test_deleted_record_does_not_render_in_a_list(self):
        body = self.client.get(reverse("log-glucose")).content.decode()
        self.assertNotIn("deleted reading", body)

    def test_deleted_record_is_not_reachable_by_url(self):
        self.assertEqual(
            self.client.get(
                reverse("edit-glucose", kwargs={"pk": self.removed.pk})
            ).status_code,
            404,
        )


class LogViewValidationTest(TestCase):
    """Regression tests for server-side validation in the add/edit views."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="test", email="test@example.com", password="test123"
        )
        self.client.login(email="test@example.com", password="test123")

    def test_edit_insulin_invalid_units_stays_in_edit_mode(self):
        from logs.models import InsulinLog
        from django.urls import reverse

        log = InsulinLog.objects.create(
            user=self.user, units=10, insulin_type="bolus", brand="Lantus"
        )
        response = self.client.post(
            reverse("edit-insulin", kwargs={"pk": log.pk}),
            {"units": "not-a-number", "insulin_type": "bolus", "brand": "NovoLog"},
        )
        # Re-render the edit form rather than redirecting to it: a redirect
        # rebuilds the fields from the database and throws away everything the
        # user typed. Still edit mode, and the stored record is untouched.
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_edit_mode"])
        self.assertEqual(response.context["insulin"].pk, log.pk)
        # the rejected submission is echoed back, not the stored values
        self.assertEqual(response.context["form"]["units"], "not-a-number")
        self.assertEqual(response.context["form"]["brand"], "NovoLog")
        log.refresh_from_db()
        self.assertEqual(log.units, 10)
        self.assertEqual(log.brand, "Lantus")

    def test_add_insulin_rejects_unknown_type(self):
        from logs.models import InsulinLog
        from django.urls import reverse

        self.client.post(
            reverse("add-insulin"), {"units": "5", "insulin_type": "banana"}
        )
        self.assertFalse(InsulinLog.objects.filter(user=self.user).exists())

    def test_add_meal_rejects_negative_macros(self):
        from logs.models import MealLog
        from django.urls import reverse

        self.client.post(
            reverse("add-meal"), {"carbs": "-50", "context": "lunch"}
        )
        self.assertFalse(MealLog.objects.filter(user=self.user).exists())

    def test_add_glucose_rejects_unknown_context(self):
        from django.urls import reverse

        self.client.post(
            reverse("add-glucose"), {"value": "6.0", "context": "banana"}
        )
        self.assertFalse(GlucoseLog.objects.filter(user=self.user).exists())

    def test_add_glucose_empty_context_defaults_to_other(self):
        from django.urls import reverse

        self.client.post(reverse("add-glucose"), {"value": "6.0", "context": ""})
        log = GlucoseLog.objects.get(user=self.user)
        self.assertEqual(log.context, "other")

    def test_add_glucose_rejects_non_finite_values(self):
        """NaN and Infinity parse as Decimal but must never reach the database.

        Decimal("NaN") constructs without raising, so it slips past the parse
        guard; any later comparison against it then raises InvalidOperation.
        """
        from django.urls import reverse

        for raw in ("NaN", "sNaN", "Infinity", "-Infinity"):
            with self.subTest(value=raw):
                response = self.client.post(
                    reverse("add-glucose"), {"value": raw, "context": "fasting"}
                )
                self.assertEqual(response.status_code, 200)
                self.assertFalse(GlucoseLog.objects.filter(user=self.user).exists())

    def test_add_meal_rejects_non_finite_macros(self):
        """Postgres numeric accepts NaN, so one bad macro would poison Sum() forever."""
        from logs.models import MealLog
        from django.urls import reverse

        for raw in ("NaN", "Infinity"):
            with self.subTest(value=raw):
                self.client.post(
                    reverse("add-meal"), {"carbs": raw, "context": "lunch"}
                )
                self.assertFalse(MealLog.objects.filter(user=self.user).exists())

    def test_daily_carb_total_survives_a_rejected_nan(self):
        """The regression that matters: totals must stay arithmetically sound."""
        from django.db.models import Sum
        from logs.models import MealLog
        from django.urls import reverse

        self.client.post(reverse("add-meal"), {"carbs": "30", "context": "lunch"})
        self.client.post(reverse("add-meal"), {"carbs": "NaN", "context": "dinner"})

        total = MealLog.objects.filter(user=self.user, is_deleted=False).aggregate(
            total=Sum("carbs")
        )["total"]
        self.assertEqual(total, 30)
        self.assertTrue(total.is_finite())


class WeeklyInsulinTotalTest(TestCase):
    """The weekly Total column used to be computed in the template with `add`.

    That filter coerces through int(), so it truncated half units, and it
    returned "" when either side was a NULL Sum — which `|default:"0"` then
    rendered as a total of 0. Both are wrong in an insulin log, so the total is
    now summed in the database.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="test", email="test@example.com", password="test123"
        )
        self.client.login(email="test@example.com", password="test123")

    def _weekly(self):
        response = self.client.get(reverse("log-insulin"))
        self.assertEqual(response.status_code, 200)
        return response.context["weekly_insulin"]

    def test_half_units_are_not_truncated(self):
        InsulinLog.objects.create(user=self.user, units=Decimal("5.5"), insulin_type="basal")
        InsulinLog.objects.create(user=self.user, units=Decimal("3.5"), insulin_type="bolus")

        rows = self._weekly()
        self.assertEqual(len(rows), 1)
        # the old template arithmetic rendered this as 8
        self.assertEqual(rows[0]["total_units"], Decimal("9.0"))

    def test_bolus_only_day_reports_its_real_total(self):
        """A day with no basal dose has a NULL basal Sum — it must not read 0."""
        InsulinLog.objects.create(user=self.user, units=Decimal("22"), insulin_type="bolus")

        rows = self._weekly()
        self.assertIsNone(rows[0]["basal_units"])
        self.assertEqual(rows[0]["total_units"], Decimal("22.0"))

    def test_todays_totals_use_database_aggregation(self):
        InsulinLog.objects.create(user=self.user, units=Decimal("5.5"), insulin_type="basal")
        InsulinLog.objects.create(user=self.user, units=Decimal("3.5"), insulin_type="bolus")

        response = self.client.get(reverse("log-insulin"))
        self.assertEqual(response.context["total_units_today"], Decimal("9.0"))
        self.assertEqual(response.context["basal_today"], Decimal("5.5"))
        self.assertEqual(response.context["bolus_today"], Decimal("3.5"))


class FreeTextLengthTest(TestCase):
    """max_length is a form-layer constraint; Model.save() does not truncate.

    These views hand-parse request.POST with no ModelForm, so an over-long
    string used to reach Postgres and raise DataError — an unhandled 500 on the
    most ordinary thing a user can do: paste a long description.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="test", email="test@example.com", password="test123"
        )
        self.client.login(email="test@example.com", password="test123")

    def test_over_long_insulin_brand_is_rejected_not_a_500(self):
        response = self.client.post(
            reverse("add-insulin"),
            {"units": "5", "insulin_type": "bolus", "brand": "x" * 60},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(InsulinLog.objects.filter(user=self.user).exists())

    def test_over_long_meal_description_is_rejected_not_a_500(self):
        response = self.client.post(
            reverse("add-meal"), {"note": "x" * 300, "context": "lunch"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MealLog.objects.filter(user=self.user).exists())

    def test_over_long_glucose_note_is_rejected_not_a_500(self):
        response = self.client.post(
            reverse("add-glucose"),
            {"value": "6.0", "context": "fasting", "note": "x" * 300},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(GlucoseLog.objects.filter(user=self.user).exists())

    def test_a_value_at_the_limit_is_accepted(self):
        response = self.client.post(
            reverse("add-insulin"),
            {"units": "5", "insulin_type": "bolus", "brand": "x" * 50},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(InsulinLog.objects.get(user=self.user).brand, "x" * 50)


class MealMacroNullPreservationTest(TestCase):
    """The macro fields are nullable on purpose: "not recorded" is not "zero".

    The edit form used |default:'0', which fires on None, so reopening a meal
    logged without macros pre-filled 0 in every box and saving wrote those
    zeroes over the NULLs.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="test", email="test@example.com", password="test123"
        )
        self.client.login(email="test@example.com", password="test123")

    def test_edit_form_does_not_prefill_null_macros_as_zero(self):
        meal = MealLog.objects.create(
            user=self.user, note="Toast", context="breakfast", calories=Decimal("500")
        )
        response = self.client.get(reverse("edit-meal", kwargs={"pk": meal.pk}))
        self.assertEqual(response.context["form"]["carbs"], "")
        self.assertEqual(response.context["form"]["protein"], "")
        self.assertEqual(response.context["form"]["fats"], "")

    def test_resaving_an_unchanged_meal_preserves_nulls_and_calories(self):
        meal = MealLog.objects.create(
            user=self.user, note="Toast", context="breakfast", calories=Decimal("500")
        )
        # exactly what the browser posts back from the untouched edit form
        self.client.post(
            reverse("edit-meal", kwargs={"pk": meal.pk}),
            {
                "note": "Toast",
                "carbs": "",
                "protein": "",
                "fats": "",
                "calories": "500",
                "context": "breakfast",
            },
        )
        meal.refresh_from_db()
        self.assertIsNone(meal.carbs)
        self.assertIsNone(meal.protein)
        self.assertIsNone(meal.fats)
        self.assertEqual(meal.calories, Decimal("500"))


class GlucoseUnitStoragePathTest(TestCase):
    """Display and storage must branch on the same test.

    They used to differ: display asked "is it mg/dL?" while storage asked "is it
    mmol?" and fell through to mg/dL. An unexpected preference value would then
    render as mmol/L but be divided by 18 on the way in.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="test", email="test@example.com", password="test123"
        )
        self.client.login(email="test@example.com", password="test123")

    def test_unknown_unit_stores_the_value_unchanged(self):
        prefs, _ = UserPreferences.objects.get_or_create(user=self.user)
        # bypass choices validation the way a bad migration or fixture would
        UserPreferences.objects.filter(pk=prefs.pk).update(glucose_unit="mmol/L")

        response = self.client.post(
            reverse("add-glucose"), {"value": "6.0", "context": "fasting"}
        )
        self.assertEqual(response.status_code, 302)
        # 6.0 stored as-is, not 6.0/18 == 0.333
        self.assertEqual(GlucoseLog.objects.get(user=self.user).value, Decimal("6.000"))

    def test_mgdl_preference_still_converts(self):
        UserPreferences.objects.update_or_create(
            user=self.user,
            defaults={"glucose_unit": UserPreferences.GLUCOSE_UNIT_MGDL},
        )
        self.client.post(reverse("add-glucose"), {"value": "108", "context": "fasting"})
        self.assertEqual(
            GlucoseLog.objects.get(user=self.user).value, mgdl_to_mmol(Decimal("108"))
        )


class RejectedSubmissionKeepsInputTest(TestCase):
    """A validation error must not throw away what the user typed."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="test", email="test@example.com", password="test123"
        )
        self.client.login(email="test@example.com", password="test123")

    def test_glucose_out_of_range_echoes_the_submission(self):
        response = self.client.post(
            reverse("add-glucose"),
            {"value": "400", "context": "bedtime", "note": "after pizza"},
        )
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form["value"], "400")
        self.assertEqual(form["context"], "bedtime")
        self.assertEqual(form["note"], "after pizza")

    def test_first_error_is_the_one_reported(self):
        """A later check used to overwrite an earlier error and mask it."""
        response = self.client.post(
            reverse("add-glucose"), {"value": "not-a-number", "context": "banana"}
        )
        self.assertEqual(response.context["error"], "Invalid reading context.")

    def test_meal_rejection_echoes_the_submission(self):
        response = self.client.post(
            reverse("add-meal"),
            {"note": "Pasta", "carbs": "-5", "context": "dinner"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"]["note"], "Pasta")
        self.assertEqual(response.context["form"]["carbs"], "-5")


class DashboardChartOrderingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="test", email="test@example.com", password="test123"
        )
        self.client.login(email="test@example.com", password="test123")

    def test_chart_points_are_time_ordered(self):
        from django.urls import reverse

        now = timezone.now()
        # insert out of chronological order on purpose
        GlucoseLog.objects.create(user=self.user, value=7.0, measured_at=now)
        GlucoseLog.objects.create(
            user=self.user, value=5.0, measured_at=now - timedelta(hours=3)
        )
        response = self.client.get(reverse("glucoread-dashboard"))
        self.assertEqual(response.context["glucose_values"], [5.0, 7.0])


class DisplayRoundingTest(TestCase):
    """mmol/L is stored at three decimals so the mg/dL round-trip is lossless.

    That precision is an implementation detail. Rounding used to be applied only
    on the mg/dL branch, so mmol/L readings rendered raw — "5.573 mmol/L" — and
    a mg/dL user who switched units saw the artefacts of their own quantisation.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="test", email="test@example.com", password="test123"
        )
        self.client.login(email="test@example.com", password="test123")
        # a value with more precision than anyone reads, as the seeder produces
        GlucoseLog.objects.create(user=self.user, value=Decimal("5.573"))

    def _set_unit(self, unit):
        UserPreferences.objects.update_or_create(
            user=self.user, defaults={"glucose_unit": unit}
        )

    def test_mmol_readings_render_at_one_decimal(self):
        self._set_unit(UserPreferences.GLUCOSE_UNIT_MMOL)
        response = self.client.get(reverse("log-glucose"))
        self.assertEqual(response.context["current_glucose_value"], 5.6)
        self.assertEqual(response.context["recent_activity"][0]["value"], 5.6)

    def test_dashboard_label_is_not_three_decimals(self):
        self._set_unit(UserPreferences.GLUCOSE_UNIT_MMOL)
        response = self.client.get(reverse("glucoread-dashboard"))
        self.assertEqual(
            response.context["recent_activity"][0]["label"],
            "Glucose reading (5.6 mmol/L)",
        )

    def test_mgdl_conversion_is_unaffected(self):
        self._set_unit(UserPreferences.GLUCOSE_UNIT_MGDL)
        response = self.client.get(reverse("log-glucose"))
        # 5.573 * 18 == 100.314 -> 100.3
        self.assertEqual(response.context["current_glucose_value"], 100.3)

    def test_none_stays_none(self):
        GlucoseLog.objects.all().delete()
        self._set_unit(UserPreferences.GLUCOSE_UNIT_MMOL)
        response = self.client.get(reverse("log-glucose"))
        self.assertIsNone(response.context["current_glucose_value"])
        self.assertIsNone(response.context["avg_glucose"])


class SeedDemoDataTest(TestCase):
    """The seeder is how screenshots get taken, so it has to survive a rerun.

    Identity is the email (it is the USERNAME_FIELD), but AbstractUser still
    carries a unique `username`. The demo address moved with the GlucoRead
    rename, so any install seeded before it already holds the obvious username
    under the old address — deriving one blindly turned a re-seed into an
    IntegrityError on exactly the machines that had used the command before.
    """

    def _seed(self, **kwargs):
        """Run the command as a developer would — under DEBUG.

        The test runner forces DEBUG=False, which the command correctly refuses
        to run under; test_refuses_to_run_outside_debug covers that path.
        """
        from io import StringIO

        from django.core.management import call_command

        # The command reports what it seeded on stdout regardless of verbosity;
        # capture it so it does not interleave with the test runner's output.
        with self.settings(DEBUG=True):
            call_command("seed_demo_data", stdout=StringIO(), **kwargs)

    def test_seeds_alongside_a_pre_rename_demo_account(self):
        User.objects.create_user(
            username="demo", email="demo@glucolog.app", password="x"
        )
        self._seed(email="demo@glucoread.app")

        user = User.objects.get(email="demo@glucoread.app")
        self.assertNotEqual(user.username, "demo")
        # the older account is left entirely alone
        self.assertTrue(User.objects.filter(email="demo@glucolog.app").exists())

    def test_rerun_reuses_the_same_account(self):
        self._seed(email="demo@glucoread.app")
        self._seed(email="demo@glucoread.app", reset=True)
        self.assertEqual(User.objects.filter(email="demo@glucoread.app").count(), 1)

    def test_refuses_to_run_outside_debug(self):
        """The only thing standing between --reset and a production database."""
        from io import StringIO

        from django.core.management import CommandError, call_command

        with self.settings(DEBUG=False):
            with self.assertRaises(CommandError):
                call_command(
                    "seed_demo_data",
                    stdout=StringIO(),
                    email="demo@glucoread.app",
                )


class BreadUnitConversionTest(TestCase):
    """Bread units are a reading of the stored grams, never a stored value."""

    def test_converts_at_the_supplied_unit_size(self):
        self.assertEqual(to_bread_units(Decimal("48"), Decimal("12")), 4.0)
        self.assertEqual(to_bread_units(Decimal("46"), Decimal("12")), 3.8)
        # the same meal in a 10 g unit is a different number of units
        self.assertEqual(to_bread_units(Decimal("46"), Decimal("10")), 4.6)
        self.assertEqual(to_bread_units(Decimal("45"), Decimal("15")), 3.0)

    def test_no_carbohydrate_recorded_is_not_zero_units(self):
        """The macro fields are nullable. Rendering 0.0 BU would claim a
        measurement that was never taken."""
        self.assertIsNone(to_bread_units(None, Decimal("12")))

    def test_zero_carbohydrate_is_zero_units(self):
        self.assertEqual(to_bread_units(Decimal("0"), Decimal("12")), 0.0)

    def test_a_non_positive_unit_size_does_not_raise(self):
        """The field forbids one, but a divisor reaching here must not be able
        to 500 the page it is rendering."""
        self.assertIsNone(to_bread_units(Decimal("48"), Decimal("0")))
        self.assertIsNone(to_bread_units(Decimal("48"), Decimal("-1")))

    def test_accepts_floats_and_ints_without_binary_drift(self):
        self.assertEqual(to_bread_units(48, 12), 4.0)
        self.assertEqual(to_bread_units(46.0, 12.0), 3.8)


class BreadUnitDisplayTest(TestCase):
    """Grams stay the stored truth; the unit size only changes the reading."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="bu", email="bu@example.com", password="pw12345!"
        )
        self.client.login(email="bu@example.com", password="pw12345!")
        MealLog.objects.create(
            user=self.user, note="Porridge", carbs=Decimal("48.0"),
            eaten_at=timezone.now(),
        )

    def test_defaults_to_the_central_european_be(self):
        self.assertEqual(
            self.user.preferences.bread_unit_grams, DEFAULT_BREAD_UNIT_GRAMS
        )

    def test_meal_rows_carry_their_bread_units(self):
        response = self.client.get(reverse("log-meal"))
        self.assertEqual(response.context["recent_meals"][0].bread_units, 4.0)
        self.assertEqual(response.context["carbs_today_bread_units"], 4.0)

    def test_changing_the_unit_size_changes_every_reading(self):
        prefs = self.user.preferences
        prefs.bread_unit_grams = Decimal("10.0")
        prefs.save()

        response = self.client.get(reverse("log-meal"))
        self.assertEqual(response.context["recent_meals"][0].bread_units, 4.8)
        self.assertEqual(response.context["carbs_today_bread_units"], 4.8)

        # and the stored grams are untouched by any of it
        self.assertEqual(
            MealLog.objects.get(user=self.user).carbs, Decimal("48.0")
        )

    def test_dashboard_states_the_days_bread_units(self):
        response = self.client.get(reverse("glucoread-dashboard"))
        self.assertEqual(response.context["carbs_bread_units"], 4.0)

    def test_a_meal_without_carbs_shows_no_unit_figure(self):
        MealLog.objects.all().delete()
        MealLog.objects.create(
            user=self.user, note="Coffee", eaten_at=timezone.now()
        )
        response = self.client.get(reverse("log-meal"))
        self.assertIsNone(response.context["recent_meals"][0].bread_units)


class InsulinWeeklySplitTest(TestCase):
    """Each day's basal/bolus share, computed in the view.

    The percentages drive a bar, so they must be whole and must always sum to
    100 — a rounded pair that sums to 99 leaves a visible gap in the track.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="ins", email="ins@example.com", password="pw12345!"
        )
        self.client.login(email="ins@example.com", password="pw12345!")
        self.now = timezone.now()

    def _dose(self, units, insulin_type, days_ago=0):
        InsulinLog.objects.create(
            user=self.user,
            units=Decimal(units),
            insulin_type=insulin_type,
            taken_at=self.now - timedelta(days=days_ago),
        )

    def _days(self):
        return self.client.get(reverse("log-insulin")).context["weekly_insulin"]

    def test_an_even_day_splits_in_half(self):
        self._dose("10.0", "basal")
        self._dose("10.0", "bolus")
        day = self._days()[0]
        self.assertEqual(day["basal_share"], 50)
        self.assertEqual(day["bolus_share"], 50)

    def test_shares_always_sum_to_one_hundred(self):
        """Rounding each side independently would leave a gap in the bar."""
        self._dose("10.0", "basal")
        self._dose("20.0", "bolus")
        day = self._days()[0]
        self.assertEqual(day["basal_share"] + day["bolus_share"], 100)
        self.assertEqual(day["basal_share"], 33)
        self.assertEqual(day["bolus_share"], 67)

    def test_a_basal_only_day_is_entirely_basal(self):
        self._dose("14.0", "basal")
        day = self._days()[0]
        self.assertEqual(day["basal_share"], 100)
        self.assertEqual(day["bolus_share"], 0)

    def test_a_bolus_only_day_is_entirely_bolus(self):
        self._dose("6.0", "bolus")
        day = self._days()[0]
        self.assertEqual(day["basal_share"], 0)
        self.assertEqual(day["bolus_share"], 100)

    def test_a_day_with_no_units_recorded_has_no_share(self):
        """Zero units must not divide by zero; the row shows an empty track."""
        self._dose("0.0", "basal")
        day = self._days()[0]
        self.assertIsNone(day["basal_share"])
        self.assertIsNone(day["bolus_share"])

    def test_each_day_is_scored_separately(self):
        self._dose("10.0", "basal", days_ago=0)
        self._dose("10.0", "bolus", days_ago=1)
        days = {d["date"]: d for d in self._days()}
        today = days[(self.now).date()]
        yesterday = days[(self.now - timedelta(days=1)).date()]
        self.assertEqual(today["basal_share"], 100)
        self.assertEqual(yesterday["bolus_share"], 100)


class GlucoseFormGuidanceTest(TestCase):
    """The add form states the band the user actually set, not the default."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="guide", email="guide@example.com", password="pw12345!"
        )
        self.client.login(email="guide@example.com", password="pw12345!")

    def test_states_the_users_own_band(self):
        prefs = self.user.preferences
        prefs.target_low = Decimal("4.4")
        prefs.target_high = Decimal("8.8")
        prefs.save()

        response = self.client.get(reverse("add-glucose"))
        self.assertEqual(response.context["range_low"], 4.4)
        self.assertEqual(response.context["range_high"], 8.8)
        self.assertContains(response, "4.4")
        self.assertContains(response, "8.8")

    def test_the_band_is_stated_in_the_users_display_unit(self):
        prefs = self.user.preferences
        prefs.glucose_unit = UserPreferences.GLUCOSE_UNIT_MGDL
        prefs.save()

        response = self.client.get(reverse("add-glucose"))
        # 3.9 and 10.0 mmol/L, converted for a mg/dL reader
        self.assertEqual(response.context["range_low"], 70.2)
        self.assertEqual(response.context["range_high"], 180.0)


class FormRerenderKeepsInputTest(TestCase):
    """A rejected submit must re-render with what was typed, never redirect.

    CLAUDE.md records this as a shipped bug: redirecting rebuilt the form from
    the database and silently discarded the user's entry. The restructured
    templates must not have reintroduced it.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="keep", email="keep@example.com", password="pw12345!"
        )
        self.client.login(email="keep@example.com", password="pw12345!")

    def test_glucose_keeps_the_rejected_value_and_note(self):
        response = self.client.post(
            reverse("add-glucose"),
            {"value": "999", "context": "fasting", "note": "after a run"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "999")
        self.assertContains(response, "after a run")

    def test_meal_keeps_every_macro_it_was_given(self):
        response = self.client.post(
            reverse("add-meal"),
            {
                "note": "Pasta",
                "carbs": "-5",
                "protein": "20",
                "fats": "11",
                "context": "dinner",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pasta")
        self.assertContains(response, "20")
        self.assertContains(response, "11")

    def test_insulin_keeps_the_rejected_entry(self):
        response = self.client.post(
            reverse("add-insulin"),
            {"units": "-4", "insulin_type": "bolus", "brand": "NovoRapid"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "NovoRapid")


class CsvExportTest(TestCase):
    """One file per log type, scoped to the signed-in user."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="exp", email="exp@example.com", password="pw12345!"
        )
        self.client.login(email="exp@example.com", password="pw12345!")
        self.now = timezone.now()
        GlucoseLog.objects.create(
            user=self.user, value=Decimal("5.5"), context="fasting",
            note="steady", measured_at=self.now - timedelta(days=1),
        )
        InsulinLog.objects.create(
            user=self.user, units=Decimal("6.0"), insulin_type="bolus",
            brand="NovoRapid", taken_at=self.now - timedelta(days=1),
        )
        MealLog.objects.create(
            user=self.user, note="Porridge", carbs=Decimal("48.0"),
            context="breakfast", eaten_at=self.now - timedelta(days=1),
        )

    def _rows(self, log_type, days=30):
        response = self.client.get(
            reverse("export-csv"), {"type": log_type, "days": str(days)}
        )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8-sig")
        return response, [r for r in csv.reader(io.StringIO(body)) if r]

    def test_glucose_export_carries_value_status_and_context(self):
        response, rows = self._rows("glucose")
        self.assertEqual(rows[0], ["Taken at", "Value (mmol/L)", "Status", "Context", "Note"])
        self.assertEqual(rows[1][1], "5.5")
        self.assertEqual(rows[1][2], "In range")
        self.assertEqual(rows[1][3], "Fasting")
        self.assertEqual(rows[1][4], "steady")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn("glucoread-glucose-last-30-days", response["Content-Disposition"])

    def test_glucose_exports_in_the_users_own_unit(self):
        prefs = self.user.preferences
        prefs.glucose_unit = UserPreferences.GLUCOSE_UNIT_MGDL
        prefs.save()

        _, rows = self._rows("glucose")
        self.assertEqual(rows[0][1], "Value (mg/dL)")
        self.assertEqual(rows[1][1], "99.0")

    def test_status_follows_the_users_own_targets(self):
        prefs = self.user.preferences
        prefs.target_high = Decimal("5.0")
        prefs.save()
        _, rows = self._rows("glucose")
        self.assertEqual(rows[1][2], "High")

    def test_meal_export_carries_bread_units_and_blanks_absent_macros(self):
        _, rows = self._rows("meals")
        self.assertEqual(rows[0][4], "Bread units (12 g each)")
        self.assertEqual(rows[1][3], "48.0")
        self.assertEqual(rows[1][4], "4.0")
        # protein/fats/calories were never recorded -- blank, never 0
        self.assertEqual(rows[1][5], "")
        self.assertEqual(rows[1][6], "")
        self.assertEqual(rows[1][7], "")

    def test_insulin_export_uses_readable_type_names(self):
        _, rows = self._rows("insulin")
        self.assertEqual(rows[1][2], "Bolus")
        self.assertEqual(rows[1][3], "NovoRapid")

    def test_timestamps_state_their_offset(self):
        _, rows = self._rows("glucose")
        # ISO 8601 with a UTC offset, so the file is unambiguous elsewhere
        self.assertRegex(rows[1][0], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")

    def test_soft_deleted_records_are_excluded(self):
        GlucoseLog.objects.update(is_deleted=True, deleted_at=timezone.now())
        _, rows = self._rows("glucose")
        self.assertEqual(len(rows), 1, "only the header should remain")

    def test_records_outside_the_window_are_excluded(self):
        GlucoseLog.objects.create(
            user=self.user, value=Decimal("7.0"),
            measured_at=self.now - timedelta(days=45),
        )
        _, in_thirty = self._rows("glucose", days=30)
        _, in_ninety = self._rows("glucose", days=90)
        self.assertEqual(len(in_thirty), 2)
        self.assertEqual(len(in_ninety), 3)

    def test_an_empty_range_still_returns_headers(self):
        GlucoseLog.objects.all().delete()
        _, rows = self._rows("glucose", days=7)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "Taken at")

    def test_another_users_records_never_appear(self):
        """This is PHI leaving the app; the queryset must be session-scoped."""
        other = User.objects.create_user(
            username="other", email="other@example.com", password="pw12345!"
        )
        GlucoseLog.objects.create(
            user=other, value=Decimal("9.9"), note="not mine",
            measured_at=self.now - timedelta(days=1),
        )
        _, rows = self._rows("glucose")
        self.assertEqual(len(rows), 2, "only the signed-in user's own reading")
        self.assertNotIn("not mine", "".join(str(r) for r in rows))

    def test_an_unknown_type_or_range_is_refused(self):
        for params in (
            {"type": "everything", "days": "30"},
            {"type": "glucose", "days": "3650"},
            {"type": "glucose"},
            {},
        ):
            response = self.client.get(reverse("export-csv"), params)
            self.assertRedirects(response, reverse("user-profile"))

    def test_export_requires_a_session(self):
        self.client.logout()
        response = self.client.get(
            reverse("export-csv"), {"type": "glucose", "days": "30"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response["Location"])
