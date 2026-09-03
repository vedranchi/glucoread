from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum, Q, Avg, Count
from django.db.models.functions import TruncDate
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from logs.models import InsulinLog, GlucoseLog, MealLog
from users.models import UserPreferences
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from logs.conversions import (
    MGDL_ENTRY_MAX,
    MGDL_ENTRY_MIN,
    MMOL_ENTRY_MAX,
    MMOL_ENTRY_MIN,
    mgdl_to_mmol,
    reading_status,
    to_bread_units,
    to_display,
)


def clean_text(value, max_length, label):
    """Normalise an optional free-text POST field and enforce the column width.

    `max_length` on a model field is a *form-layer* constraint — `Model.save()`
    does not truncate, so an over-long string reaches Postgres and raises
    DataError, which surfaces as a 500. These views hand-parse `request.POST`
    with no ModelForm in between, so the check has to happen here.
    """
    text = (value or "").strip()
    if len(text) > max_length:
        raise ValueError(f"{label} must be {max_length} characters or fewer.")
    return text


@login_required
def log_insulin(request):
    today = timezone.now().date()
    insulin_today = InsulinLog.objects.filter(
        user=request.user, taken_at__date=today, is_deleted=False
    )

    # All three of today's figures in one query. Sum() returns None when nothing
    # matches: the card reads that as "no doses logged yet" for the total, but
    # the basal/bolus splits should show 0 rather than blank.
    totals = insulin_today.aggregate(
        total=Sum("units"),
        basal=Sum("units", filter=Q(insulin_type="basal")),
        bolus=Sum("units", filter=Q(insulin_type="bolus")),
    )
    total_insulin = round(totals["total"], 1) if totals["total"] is not None else None
    basal_units = round(totals["basal"] or 0, 1)
    bolus_units = round(totals["bolus"] or 0, 1)

    recent_activity = []
    for i in insulin_today:
        recent_activity.append(
            {
                "id": i.id,
                "units": i.units,
                "type": i.insulin_type,
                "brand": i.brand,
                "note": i.note,
                "when": i.taken_at,
            }
        )
    recent_activity = sorted(recent_activity, key=lambda a: a["when"], reverse=True)[:5]

    last_seven_days = timezone.now() - timedelta(days=7)

    # daily basal/bolus totals for the weekly chart
    weekly_insulin = list(
        InsulinLog.objects.filter(
            user=request.user, taken_at__gte=last_seven_days, is_deleted=False
        )
        .annotate(date=TruncDate("taken_at"))
        .values("date")
        .annotate(
            basal_units=Sum("units", filter=Q(insulin_type="basal")),
            bolus_units=Sum("units", filter=Q(insulin_type="bolus")),
            # Summed here rather than added in the template. Django's `add`
            # filter coerces through int() first, so it both truncated half
            # units (5.5 + 3.5 rendered as 8) and returned "" whenever one
            # side was a NULL Sum — which `|default:"0"` then displayed as a
            # total of 0 for any day that had only bolus doses.
            total_units=Sum("units"),
        )
        .order_by("-date")
    )

    # The card's point is the basal/bolus split, so each day carries its own
    # share as a percentage. Computed here, never in the template: `add`
    # coerces through int(), which is what shipped a wrong insulin total to
    # production once already. A day with no units recorded gets no bar rather
    # than a division by zero.
    for day in weekly_insulin:
        basal = day["basal_units"] or 0
        bolus = day["bolus_units"] or 0
        recorded = basal + bolus
        if recorded > 0:
            day["basal_share"] = round(basal / recorded * 100)
            day["bolus_share"] = 100 - day["basal_share"]
        else:
            day["basal_share"] = None
            day["bolus_share"] = None

    # doses the user marked as corrections (note="correction", case-insensitive)
    correction_logs = list(
        InsulinLog.objects.filter(
            user=request.user,
            taken_at__gte=last_seven_days,
            note__iexact="correction",
            is_deleted=False,
        )
        .values("units", "insulin_type", "brand", "note", "taken_at")
        .order_by("-taken_at")
    )

    context = {
        "total_units_today": total_insulin,
        "basal_today": basal_units,
        "bolus_today": bolus_units,
        "weekly_insulin": weekly_insulin,
        "weekly_corrections": correction_logs,
        "recent_insulin": recent_activity,
    }

    return render(request, "logs/log_insulin.html", context)


@login_required
def add_insulin(request, pk=None):
    """Add a new insulin dose or edit an existing one when pk is provided."""
    insulin = (
        get_object_or_404(InsulinLog, user=request.user, is_deleted=False, pk=pk)
        if pk
        else None
    )

    # What the form should render. On GET that's the stored record; on a rejected
    # POST it's what the user actually typed, so an error doesn't discard their
    # input (and, when editing, doesn't silently revert the fields to the values
    # already in the database).
    form = {
        "units": insulin.units if insulin else "",
        "insulin_type": insulin.insulin_type if insulin else "",
        "brand": insulin.brand if insulin else "",
        "note": insulin.note if insulin else "",
    }

    if request.method == "POST":
        form = {
            "units": request.POST.get("units", ""),
            "insulin_type": request.POST.get("insulin_type", ""),
            "brand": request.POST.get("brand", ""),
            "note": request.POST.get("note", ""),
        }
        error = None

        try:
            units = Decimal(form["units"])
            if not units.is_finite() or units <= 0 or units >= 300:
                raise ValueError
        except (InvalidOperation, TypeError, ValueError):
            error = "Invalid units value."

        if not error and form["insulin_type"] not in dict(InsulinLog.INSULIN_TYPES):
            error = "Invalid insulin type."

        if not error:
            try:
                brand = clean_text(form["brand"], 50, "Brand")
                note = clean_text(form["note"], 255, "Note")
            except ValueError as exc:
                error = str(exc)

        if error:
            messages.error(request, error)
        else:
            if insulin:
                insulin.units = units
                insulin.insulin_type = form["insulin_type"]
                insulin.brand = brand
                insulin.note = note
                insulin.save()
            else:
                InsulinLog.objects.create(
                    user=request.user,
                    units=units,
                    insulin_type=form["insulin_type"],
                    brand=brand,
                    note=note,
                )
            return redirect("log-insulin")

    context = {"insulin": insulin, "is_edit_mode": bool(insulin), "form": form}
    return render(request, "logs/add_insulin.html", context)


@login_required
@require_POST
def delete_insulin_record(request, pk):
    insulin = get_object_or_404(InsulinLog, pk=pk, user=request.user, is_deleted=False)
    insulin.is_deleted = True
    insulin.deleted_at = timezone.now()
    insulin.save()
    return redirect("log-insulin")


@login_required
def log_glucose(request):
    profile, _ = UserPreferences.objects.get_or_create(user=request.user)
    is_mgdl = profile.glucose_unit == UserPreferences.GLUCOSE_UNIT_MGDL
    unit_label = "mg/dL" if is_mgdl else "mmol/L"

    today = timezone.now().date()

    # most recent reading across all time, not just today
    current_glucose = (
        GlucoseLog.objects.filter(user=request.user, is_deleted=False)
        .order_by("-measured_at")
        .first()
    )

    glucose_stats = GlucoseLog.objects.filter(
        user=request.user, measured_at__date=today, is_deleted=False
    ).aggregate(avg_glucose=Avg("value"), count_glucose=Count("id"))

    avg_glucose = to_display(glucose_stats["avg_glucose"], is_mgdl)

    glucose_today = GlucoseLog.objects.filter(
        user=request.user, measured_at__date=today, is_deleted=False
    )

    # today's readings list, converted to display unit. The status pair comes
    # from the stored mmol/L value, never the converted one, so a mg/dL user
    # and an mmol/L user classify the same reading identically.
    recent_activity = []
    for g in glucose_today:
        tone, label = reading_status(g.value, profile.target_low, profile.target_high)
        recent_activity.append(
            {
                "id": g.id,
                "value": to_display(g.value, is_mgdl),
                "note": g.note,
                "context": g.context,
                "when": g.measured_at,
                "tone": tone,
                "status": label,
            }
        )
    recent_activity = sorted(recent_activity, key=lambda a: a["when"], reverse=True)[:10]

    current_value = to_display(
        current_glucose.value if current_glucose else None, is_mgdl
    )

    # daily averages for the weekly summary table
    last_seven_days = timezone.now().date() - timedelta(days=6)
    weekly_glucose = list(
        GlucoseLog.objects.filter(
            user=request.user, measured_at__date__gte=last_seven_days, is_deleted=False
        )
        .annotate(date=TruncDate("measured_at"))
        .values("date")
        .annotate(avg_glucose=Avg("value"), count=Count("id"))
        .order_by("-date")
    )

    # individual readings for the 7-day detail list (rolling window, not calendar days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    recent_7_days_qs = GlucoseLog.objects.filter(
        user=request.user, measured_at__gte=seven_days_ago, is_deleted=False
    ).order_by("-measured_at")

    recent_7_days = []
    for g in recent_7_days_qs:
        tone, label = reading_status(g.value, profile.target_low, profile.target_high)
        recent_7_days.append(
            {
                "value": to_display(g.value, is_mgdl),
                "measured_at": g.measured_at,
                "context": g.context,
                "note": g.note,
                "id": g.id,
                "tone": tone,
                "status": label,
            }
        )

    for entry in weekly_glucose:
        entry["avg_glucose"] = to_display(entry["avg_glucose"], is_mgdl)

    context = {
        "current_glucose_value": current_value,
        "current_glucose_time": (
            current_glucose.measured_at if current_glucose else None
        ),
        "avg_glucose": avg_glucose,
        "reading_count": glucose_stats["count_glucose"],
        "recent_activity": recent_activity,
        "unit_label": unit_label,
        "weekly_glucose": weekly_glucose,
        "recent_seven_days": recent_7_days,
    }

    return render(request, "logs/log_glucose.html", context)


@login_required
def add_glucose(request, pk=None):
    """Add a new glucose reading or edit an existing one when pk is provided."""
    glucose = (
        get_object_or_404(GlucoseLog, pk=pk, is_deleted=False, user=request.user)
        if pk
        else None
    )

    profile, _ = UserPreferences.objects.get_or_create(user=request.user)
    # One test drives both the display and the storage path. They used to differ
    # — display asked "is it mg/dL?" while storage asked "is it mmol?" and fell
    # through to mg/dL — so an unexpected preference value would render as
    # mmol/L but be divided by 18 on the way in, a factor-of-18 error in a
    # stored medical record. Now an unknown unit is treated as mmol/L
    # throughout, which stores the value unchanged.
    is_mgdl = profile.glucose_unit == UserPreferences.GLUCOSE_UNIT_MGDL
    unit_label = "mg/dL" if is_mgdl else "mmol/L"

    # stored mmol/L converted back to the user's display unit for the edit form
    prefill_value = to_display(glucose.value if glucose else None, is_mgdl)

    form = {
        "value": "" if prefill_value is None else prefill_value,
        "context": glucose.context if glucose else "",
        "note": glucose.note if glucose else "",
    }

    error = None
    if request.method == "POST":
        # Echo the submission back on failure rather than the stored record, so
        # a rejected reading doesn't leave the user staring at an empty box (or,
        # when editing, silently revert to what's already saved).
        form = {
            "value": request.POST.get("value", ""),
            "context": request.POST.get("context", ""),
            "note": request.POST.get("note", ""),
        }
        # empty selection falls back to the model default; anything else must be a real choice
        reading_context = form["context"] or "other"

        if reading_context not in dict(GlucoseLog.CONTEXT):
            error = "Invalid reading context."

        try:
            note = clean_text(form["note"], 255, "Note")
        except ValueError as exc:
            # `or` throughout so the first problem found is the one reported;
            # a later check used to overwrite an earlier error and mask it.
            error = error or str(exc)

        mmol_value = None
        try:
            value = Decimal(form["value"])
        except (TypeError, InvalidOperation):
            error = error or "Enter a valid number"
        else:
            # NaN and Infinity construct without raising, so they reach here;
            # the range comparisons below would then raise InvalidOperation
            # outside the try above and surface as a 500.
            if not value.is_finite():
                error = error or "Enter a valid number"
            elif is_mgdl:  # convert to mmol/L before storing
                if value < MGDL_ENTRY_MIN or value > MGDL_ENTRY_MAX:
                    error = error or (
                        "Too high/low for mg/dL. Check if unit preference is correct"
                    )
                else:
                    mmol_value = mgdl_to_mmol(value)
            else:
                if value < MMOL_ENTRY_MIN or value > MMOL_ENTRY_MAX:
                    error = error or (
                        "Too high/low for mmol/L. Check if unit preference is correct"
                    )
                else:
                    mmol_value = value

        if not error:
            if glucose:
                glucose.value = mmol_value
                glucose.note = note
                glucose.context = reading_context
                glucose.save()
            else:
                GlucoseLog.objects.create(
                    user=request.user,
                    value=mmol_value,
                    note=note,
                    context=reading_context,
                )
            return redirect("log-glucose")

    return render(
        request,
        "logs/add_glucose.html",
        {
            "glucose": glucose,
            "is_edit_mode": bool(glucose),
            "unit_label": unit_label,
            "error": error,
            "form": form,
            # The form asks for a number without saying what counts as in
            # range. The user's own band is already stored, so state it rather
            # than leaving them to remember it. Display units, like the field.
            "range_low": to_display(profile.target_low, is_mgdl),
            "range_high": to_display(profile.target_high, is_mgdl),
        },
    )


@login_required
@require_POST
def delete_glucose_reading(request, pk):
    glucose = get_object_or_404(GlucoseLog, pk=pk, user=request.user, is_deleted=False)
    glucose.is_deleted = True
    glucose.deleted_at = timezone.now()
    glucose.save()
    return redirect("log-glucose")


@login_required
def log_meal(request):
    today = timezone.now().date()
    preferences, _ = UserPreferences.objects.get_or_create(user=request.user)
    bread_unit_grams = preferences.bread_unit_grams

    totals = MealLog.objects.filter(
        user=request.user, eaten_at__date=today, is_deleted=False
    ).aggregate(
        carbs_today=Sum("carbs"),
        protein_today=Sum("protein"),
        fats_today=Sum("fats"),
        calories_today=Sum("calories"),
    )

    # aggregate returns None when no rows match; default to 0 for display
    carbs_today = totals["carbs_today"] or 0
    protein_today = totals["protein_today"] or 0
    fats_today = totals["fats_today"] or 0
    calories_today = totals["calories_today"] or 0

    recent_meals = list(
        MealLog.objects.filter(user=request.user, is_deleted=False).order_by(
            "-eaten_at"
        )[:5]
    )
    # Attached rather than annotated: the divisor is a Python Decimal on the
    # user's preferences, and five rows do not justify pushing it into SQL.
    for meal in recent_meals:
        meal.bread_units = to_bread_units(meal.carbs, bread_unit_grams)

    context = {
        "carbs_today": carbs_today,
        "carbs_today_bread_units": to_bread_units(carbs_today, bread_unit_grams),
        "bread_unit_grams": bread_unit_grams,
        "protein_today": protein_today,
        "fats_today": fats_today,
        "calories_today": calories_today,
        "recent_meals": recent_meals,
    }
    return render(request, "logs/log_meal.html", context)


def parse_macro(value):
    """Convert a POST string to a Decimal nutrition amount.

    Blank means "not provided" and maps to None (the fields are nullable).
    Garbage, negative, or out-of-range input raises ValueError so the view
    can reject the submission instead of silently dropping data.
    """
    if not value:
        return None
    try:
        parsed = Decimal(value)
    except (InvalidOperation, TypeError):
        raise ValueError("not a number")
    # NaN and Infinity construct without raising, but every comparison against
    # them raises InvalidOperation — and Postgres numeric accepts NaN, so one
    # stored value would poison this user's Sum() totals permanently. Reject
    # them before the range check below can touch them.
    if not parsed.is_finite():
        raise ValueError("not a number")
    # nutrition can't be negative; the model fields cap out at 9999.9
    if parsed < 0 or parsed >= Decimal("10000"):
        raise ValueError("out of range")
    return parsed


@login_required
def add_meal(request, pk=None):
    """Add a new meal log or edit an existing one when pk is provided."""
    meal = (
        get_object_or_404(MealLog, pk=pk, is_deleted=False, user=request.user)
        if pk
        else None
    )

    # The macro fields are nullable on purpose — a meal can be logged without
    # full nutrition data. Blank stays blank here rather than becoming "0", so
    # reopening and saving an edit can't turn "not recorded" into "recorded as
    # zero".
    def macro(value):
        return "" if value is None else value

    form = {
        "note": meal.note if meal else "",
        "carbs": macro(meal.carbs) if meal else "",
        "protein": macro(meal.protein) if meal else "",
        "fats": macro(meal.fats) if meal else "",
        "calories": macro(meal.calories) if meal else "",
        "context": meal.context if meal else "",
    }

    if request.method == "POST":
        form = {
            "note": request.POST.get("note", ""),
            "carbs": request.POST.get("carbs", ""),
            "protein": request.POST.get("protein", ""),
            "fats": request.POST.get("fats", ""),
            "calories": request.POST.get("calories", ""),
            "context": request.POST.get("context", ""),
        }
        error = None

        try:
            carbs = parse_macro(form["carbs"])
            protein = parse_macro(form["protein"])
            fats = parse_macro(form["fats"])
            calories = parse_macro(form["calories"])
        except ValueError:
            error = "Nutrition values must be numbers between 0 and 9999.9."

        # empty selection falls back to the model default; anything else must be a real choice
        meal_context = form["context"] or "breakfast"
        if not error and meal_context not in dict(MealLog.CONTEXT):
            error = "Invalid meal type."

        if not error:
            try:
                note = clean_text(form["note"], 255, "Meal description")
            except ValueError as exc:
                error = str(exc)

        if error:
            messages.error(request, error)
        else:
            if meal:
                meal.carbs = carbs
                meal.protein = protein
                meal.fats = fats
                meal.calories = calories
                meal.context = meal_context
                meal.note = note
                meal.save()
            else:
                MealLog.objects.create(
                    user=request.user,
                    carbs=carbs,
                    protein=protein,
                    fats=fats,
                    calories=calories,
                    note=note,
                    context=meal_context,
                )
            return redirect("log-meal")

    # The form shows a live bread-unit reading beside the carbs field, so it
    # needs the user's unit size to divide by.
    preferences, _ = UserPreferences.objects.get_or_create(user=request.user)

    return render(
        request,
        "logs/add_meal.html",
        {
            "meal": meal,
            "is_edit_mode": bool(meal),
            "form": form,
            "bread_unit_grams": preferences.bread_unit_grams,
        },
    )


@login_required
@require_POST
def delete_meal_log(request, pk):
    meal = get_object_or_404(MealLog, user=request.user, pk=pk, is_deleted=False)
    meal.is_deleted = True
    meal.deleted_at = timezone.now()
    meal.save()
    return redirect("log-meal")
