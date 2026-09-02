"""Glucose unit conversion, in one place.

Glucose is stored in mmol/L and converted to mg/dL only at the edges, driven by
the user's `UserPreferences.glucose_unit`. Both `logs` and `dashboard` render
readings, so the factor lived in both and was additionally hard-coded at the one
site that mattered most. It lives here now.
"""

from decimal import Decimal

# Standard conversion factor between mmol/L and mg/dL. Deliberately an int: the
# display path multiplies floats by it, and the storage path wraps it in
# Decimal(). Making it a Decimal would break the former with a TypeError.
MMOL_TO_MGDL = 18

# The precision at which mmol/L is stored. Must match GlucoseLog.value's
# decimal_places — see the round-trip test in logs/tests.py, which fails if
# these drift apart.
#
# The two units share no exact grid, so every mg/dL entry is quantised on the
# way in and multiplied back out on the way to the page. Three decimal places is
# the point at which that becomes lossless: across the accepted 20-700 mg/dL
# range, every whole value redisplays as itself. At two places, 44% of them come
# back up to 0.1 mg/dL off (100 -> 100.1); at one place, 89% do, by as much as
# 0.8 (100 -> 100.8).
MMOL_QUANTUM = Decimal("0.001")


def mgdl_to_mmol(value):
    """Convert a mg/dL reading to the mmol/L value to store."""
    return (value / Decimal(MMOL_TO_MGDL)).quantize(MMOL_QUANTUM)


def to_display(value, is_mgdl):
    """Convert a stored mmol/L reading to the unit the user reads.

    Both units render at one decimal place. mmol/L is *stored* at three so the
    mg/dL round-trip stays lossless (see MMOL_QUANTUM), but that precision is an
    implementation detail — nobody reads a glucose reading as "5.573 mmol/L".
    Rounding used to be applied only on the mg/dL branch, so mmol/L users saw
    the raw stored value, and a mg/dL user who switched units saw the artefacts
    of their own quantisation (100 mg/dL -> "5.556 mmol/L").
    """
    if value is None:
        return None
    value = float(value)
    return round(value * MMOL_TO_MGDL if is_mgdl else value, 1)


# --------------------------------------------------------------------------
# Target range.
#
# The redesign surfaces range status in four places — the header chip, the
# rail's time-in-range meter, the dashboard's shaded chart band, and each row
# of the glucose log — so the thresholds and the labels live here, next to the
# unit conversion, rather than being restated at each of those call sites.
#
# 3.9-10.0 mmol/L is the standard adult target band, and is what the source
# design states as 70-180 mg/dL. Held in mmol/L because that is the storage
# unit: classifying on the stored value means a mg/dL user and an mmol/L user
# never disagree about whether the same reading was in range.
# --------------------------------------------------------------------------
RANGE_LOW_MMOL = 3.9
RANGE_HIGH_MMOL = 10.0


def reading_status(value_mmol):
    """Classify a stored reading, returning (tone class, human label)."""
    value = float(value_mmol)
    if value < RANGE_LOW_MMOL:
        return "t-danger", "Low"
    if value > RANGE_HIGH_MMOL:
        return "t-warn", "High"
    return "t-range", "In range"
