from django.shortcuts import render
from django.db.models import Avg, Count, Sum
from logs.models import GlucoseLog, InsulinLog, MealLog
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from datetime import datetime, timedelta

from users.models import UserPreferences
from users.services import get_user_preferences
from logs.conversions import to_bread_units, to_display


@login_required
def dashboard(request):
    profile = get_user_preferences(request.user)
    is_mgdl = profile.glucose_unit == UserPreferences.GLUCOSE_UNIT_MGDL
    unit_label = "mg/dL" if is_mgdl else "mmol/L"

    # localdate(), never now().date(): the __date lookups below resolve in
    # TIME_ZONE, so a UTC date empties the whole page for the first hours of
    # the local day.
    today = timezone.localdate()

    glucose_today = GlucoseLog.objects.filter(
        user=request.user, measured_at__date=today, is_deleted=False
    )
    insulin_today = InsulinLog.objects.filter(
        user=request.user, taken_at__date=today, is_deleted=False
    )
    meals_today = MealLog.objects.filter(
        user=request.user, eaten_at__date=today, is_deleted=False
    )

    latest_glucose = glucose_today.order_by("-measured_at").first()
    latest_insulin = insulin_today.order_by("-taken_at").first()
    latest_meal = meals_today.order_by("-eaten_at").first()

    latest_glucose_value = to_display(
        latest_glucose.value if latest_glucose else None, is_mgdl
    )

    glucose_stats = glucose_today.aggregate(avg_glucose=Avg("value"), count=Count("id"))
    avg_glucose = to_display(glucose_stats["avg_glucose"], is_mgdl)

    # The redesign's average-glucose card carries a "N% from yesterday" line.
    # The source design hard-codes "5%"; this derives it, and stays None when
    # either day has no readings so the card simply omits the line rather than
    # implying a comparison that was never made.
    yesterday_avg = (
        GlucoseLog.objects.filter(
            user=request.user,
            measured_at__date=today - timedelta(days=1),
            is_deleted=False,
        ).aggregate(avg=Avg("value"))["avg"]
    )
    avg_delta_pct = None
    avg_delta_direction = ""
    if glucose_stats["avg_glucose"] is not None and yesterday_avg:
        change = (glucose_stats["avg_glucose"] - yesterday_avg) / yesterday_avg * 100
        avg_delta_pct = abs(round(change))
        # A flat day is not a trend; only label a direction once it rounds to
        # at least one percent.
        if avg_delta_pct:
            avg_delta_direction = "up" if change > 0 else "down"

    insulin_stats = insulin_today.aggregate(total_units=Sum("units"), count=Count("id"))
    total_insulin = (
        round(insulin_stats["total_units"], 1) if insulin_stats["count"] else None
    )

    # SUM ignores NULLs, matching the previous `m.carbs or 0` per-row fallback
    meal_stats = meals_today.aggregate(total_carbs=Sum("carbs"), count=Count("id"))
    carbs_consumed = (
        round(meal_stats["total_carbs"] or 0, 1) if meal_stats["count"] else None
    )

    # build recent activity feed from all three log types, show last 5
    recent_activity = []
    for g in glucose_today:
        recent_activity.append(
            {
                "label": f"Glucose reading ({to_display(g.value, is_mgdl)} {unit_label})",
                "when": g.measured_at,
                "edit_url": reverse("edit-glucose", kwargs={"pk": g.id}),
                # Icon and tone travel with the row so the template does not
                # have to branch on the log type three times over.
                "icon": "droplet",
                "tone": "t-glucose",
            }
        )
    for i in insulin_today:
        recent_activity.append(
            {
                "label": f"Insulin dose ({i.units} U)",
                "when": i.taken_at,
                "edit_url": reverse("edit-insulin", kwargs={"pk": i.id}),
                "icon": "syringe",
                "tone": "t-insulin",
            }
        )
    for m in meals_today:
        recent_activity.append(
            {
                # note is nullable, and the seeder creates meals without one —
                # an f-string would render the literal text "Meal (None)".
                "label": f"Meal ({m.note})" if m.note else "Meal",
                "when": m.eaten_at,
                "edit_url": reverse("edit-meal", kwargs={"pk": m.id}),
                "icon": "utensils-crossed",
                "tone": "t-meal",
            }
        )
    recent_activity = sorted(recent_activity, key=lambda a: a["when"], reverse=True)[:5]

    # chart date navigation — defaults to today, clamped so next never exceeds today
    chart_date_param = request.GET.get("chart_date")
    chart_date = today
    if chart_date_param:
        try:
            chart_date = datetime.strptime(chart_date_param, "%Y-%m-%d").date()
        except ValueError:
            chart_date = today

    # explicit ordering — the chart draws points in list order, so an
    # unordered queryset would zigzag the line
    glucose_chart_day = GlucoseLog.objects.filter(
        user=request.user, measured_at__date=chart_date, is_deleted=False
    ).order_by("measured_at")

    glucose_labels = [g.measured_at.strftime("%H:%M") for g in glucose_chart_day]
    glucose_values = [to_display(g.value, is_mgdl) for g in glucose_chart_day]

    previous_chart_date = chart_date - timedelta(days=1)
    next_chart_date = chart_date + timedelta(days=1)
    if next_chart_date > today:
        next_chart_date = None

    context = {
        "avg_glucose": avg_glucose,
        "total_insulin": total_insulin,
        "carbs_consumed": carbs_consumed,
        "carbs_bread_units": to_bread_units(carbs_consumed, profile.bread_unit_grams),
        "recent_activity": recent_activity,
        "glucose_count_today": glucose_stats["count"],
        "insulin_count_today": insulin_stats["count"],
        "meal_count_today": meal_stats["count"],
        "latest_glucose": latest_glucose,
        "latest_glucose_value": latest_glucose_value,
        "latest_insulin": latest_insulin,
        "latest_meal": latest_meal,
        "chart_date": chart_date,
        "previous_chart_date": previous_chart_date,
        "next_chart_date": next_chart_date,
        "glucose_labels": glucose_labels,
        "glucose_values": glucose_values,
        "unit_label": unit_label,
        "avg_delta_pct": avg_delta_pct,
        "avg_delta_direction": avg_delta_direction,
        # The target band the chart shades and the range card names. Stored
        # in mmol/L on the user's preferences and converted here for display,
        # so no two surfaces can state different thresholds.
        "range_low": to_display(profile.target_low, is_mgdl),
        "range_high": to_display(profile.target_high, is_mgdl),
    }

    return render(request, "dashboard/dashboard.html", context)
