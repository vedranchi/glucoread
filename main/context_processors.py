"""Context for the app shell.

The redesigned shell (main/base.html) carries three things the old one did not:
the latest reading as a header chip, a time-in-range meter in the navigation
rail, and an active-section highlight. All three appear on every authenticated
page, so they belong here rather than being copied into each view.

The source design hard-codes these ("118 mg/dL", "78% time in range", "Keep up
the great work!"). They are computed from the user's own logs instead — a
health app showing an invented glucose figure in its chrome is a real hazard,
not a cosmetic one.
"""

from django.db.models import Count, Q
from django.utils import timezone

from logs.models import GlucoseLog
from users.models import UserPreferences
from users.services import get_user_preferences
from logs.conversions import reading_status, to_display


# Rail section, keyed off the trailing word of the resolved URL name rather
# than a path prefix: every route in `logs` is named "<verb>-<type>"
# (log-glucose, add-glucose, edit-glucose, delete-glucose), so one entry covers
# a whole section and moving a path in urls.py cannot silently unhighlight it.
_SECTIONS = {
    "dashboard": "dashboard",
    "glucose": "glucose",
    "insulin": "insulin",
    "meal": "meals",
    "profile": "profile",
}


def shell(request):
    """Shell-wide context: active nav section, header chip, range meter."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}

    match = request.resolver_match
    nav_section = ""
    if match is not None and match.url_name:
        nav_section = _SECTIONS.get(match.url_name.rsplit("-", 1)[-1], "")

    preferences = get_user_preferences(user)
    is_mgdl = preferences.glucose_unit == UserPreferences.GLUCOSE_UNIT_MGDL
    unit_label = "mg/dL" if is_mgdl else "mmol/L"

    today = timezone.now().date()
    today_readings = GlucoseLog.objects.filter(
        user=user, measured_at__date=today, is_deleted=False
    )

    # One query for both counts rather than two round trips plus a Python loop.
    counts = today_readings.aggregate(
        total=Count("id"),
        in_range=Count(
            "id",
            filter=Q(
                value__gte=preferences.target_low,
                value__lte=preferences.target_high,
            ),
        ),
    )
    reading_count = counts["total"]

    time_in_range = None
    if reading_count:
        time_in_range = round(counts["in_range"] / reading_count * 100)

    latest_reading = None
    latest = today_readings.order_by("-measured_at").first()
    if latest is not None:
        tone, label = reading_status(
            latest.value, preferences.target_low, preferences.target_high
        )
        latest_reading = {
            "value": to_display(latest.value, is_mgdl),
            "unit": unit_label,
            "tone": tone,
            "label": label,
        }

    diabetes_type = ""
    health_profile = getattr(user, "health_profile", None)
    if health_profile is not None and health_profile.diabetes_type:
        diabetes_type = health_profile.get_diabetes_type_display()

    return {
        "nav_section": nav_section,
        "latest_reading": latest_reading,
        "time_in_range": time_in_range,
        "in_range_count": counts["in_range"],
        "reading_count": reading_count,
        "diabetes_type": diabetes_type,
        "unit_label": unit_label,
    }
