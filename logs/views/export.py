"""CSV export of a user's own log data.

One file per log type. The three types share almost no columns — glucose is a
value with a context, a meal is a description with four macros — so a combined
sheet would be mostly empty cells and awkward to chart. Separate files each open
straight into a spreadsheet.

Everything here is presentation of data the app already holds: no aggregation,
no derived medical figures beyond the ones already shown on screen (range status
and bread units), both of which are stated in their own columns rather than
implied.

This is PHI leaving the app, so every queryset is scoped to request.user and
filters is_deleted=False. There is no "export another user" path by design —
the user is taken from the session, never from a parameter.
"""

import csv
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect
from django.utils import timezone

from logs.conversions import reading_status, to_bread_units, to_display
from logs.models import GlucoseLog, InsulinLog, MealLog
from users.models import UserPreferences

# Offered windows, in days. Deliberately a fixed set rather than free input:
# every value is validated against these keys, so no date parsing reaches the
# database.
EXPORT_RANGES = {
    "7": "Last 7 days",
    "14": "Last 14 days",
    "30": "Last 30 days",
    "90": "Last 90 days",
}

EXPORT_TYPES = {
    "glucose": "Glucose readings",
    "insulin": "Insulin doses",
    "meals": "Meals and macros",
}


def _trim(value):
    """Render a Decimal without its stored trailing zeros: 12.0 -> "12".

    Not Decimal.normalize(), which returns 1E+1 for Decimal("10.0") and would
    put scientific notation in a column header. The guard on "." keeps an
    integer like 100 from being stripped to 1.
    """
    text = f"{value:f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _stamp(value):
    """A timestamp a spreadsheet and a human can both read unambiguously.

    ISO 8601 in local time *with* the UTC offset. The app pins TIME_ZONE to
    Europe/Skopje for every user (a known limitation), so a naive local time
    would be silently misread by anyone opening the file elsewhere. The offset
    removes the guesswork without waiting for per-user timezones.
    """
    return timezone.localtime(value).isoformat(timespec="seconds")


def _glucose_rows(user, since, preferences):
    is_mgdl = preferences.glucose_unit == UserPreferences.GLUCOSE_UNIT_MGDL
    unit_label = "mg/dL" if is_mgdl else "mmol/L"

    yield ["Taken at", f"Value ({unit_label})", "Status", "Context", "Note"]
    rows = GlucoseLog.objects.filter(
        user=user, measured_at__gte=since, is_deleted=False
    ).order_by("measured_at")
    for entry in rows:
        _, status = reading_status(
            entry.value, preferences.target_low, preferences.target_high
        )
        yield [
            _stamp(entry.measured_at),
            to_display(entry.value, is_mgdl),
            status,
            entry.get_context_display(),
            entry.note or "",
        ]


def _insulin_rows(user, since, preferences):
    yield ["Taken at", "Units", "Type", "Brand", "Note"]
    rows = InsulinLog.objects.filter(
        user=user, taken_at__gte=since, is_deleted=False
    ).order_by("taken_at")
    for entry in rows:
        yield [
            _stamp(entry.taken_at),
            entry.units,
            entry.get_insulin_type_display(),
            entry.brand or "",
            entry.note or "",
        ]


def _meal_rows(user, since, preferences):
    grams = preferences.bread_unit_grams
    yield [
        "Eaten at",
        "Description",
        "Meal",
        "Carbs (g)",
        f"Bread units ({_trim(grams)} g each)",
        "Protein (g)",
        "Fats (g)",
        "Calories (kcal)",
    ]
    rows = MealLog.objects.filter(
        user=user, eaten_at__gte=since, is_deleted=False
    ).order_by("eaten_at")
    for entry in rows:
        bread_units = to_bread_units(entry.carbs, grams)
        yield [
            _stamp(entry.eaten_at),
            entry.note or "",
            entry.get_context_display(),
            # Blank, not 0: these fields are nullable and a zero would claim a
            # measurement that was never taken.
            "" if entry.carbs is None else entry.carbs,
            "" if bread_units is None else bread_units,
            "" if entry.protein is None else entry.protein,
            "" if entry.fats is None else entry.fats,
            "" if entry.calories is None else entry.calories,
        ]


_ROW_BUILDERS = {
    "glucose": _glucose_rows,
    "insulin": _insulin_rows,
    "meals": _meal_rows,
}


@login_required
def export_csv(request):
    """Stream one log type over one window as CSV, for the signed-in user."""
    log_type = request.GET.get("type", "")
    days = request.GET.get("days", "")

    # Strict: an unrecognised value means a hand-edited or broken request, and
    # quietly falling back to a default would hand back a file the user did not
    # ask for and might not notice was wrong.
    if log_type not in _ROW_BUILDERS or days not in EXPORT_RANGES:
        messages.error(request, "That export is not available. Pick a type and a range.")
        return redirect("user-profile")

    preferences, _ = UserPreferences.objects.get_or_create(user=request.user)
    since = timezone.now() - timedelta(days=int(days))

    today = timezone.localdate().isoformat()
    filename = f"glucoread-{log_type}-last-{days}-days-{today}.csv"

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    # Excel assumes the host codepage for a .csv unless a BOM says otherwise,
    # which mangles any non-ASCII note. Costs three bytes.
    response.write("﻿")

    writer = csv.writer(response)
    for row in _ROW_BUILDERS[log_type](request.user, since, preferences):
        writer.writerow(row)

    return response
