from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

from django.core.validators import FileExtensionValidator, MinValueValidator

from logs.conversions import (
    DEFAULT_BREAD_UNIT_GRAMS,
    DEFAULT_TARGET_HIGH_MMOL,
    DEFAULT_TARGET_LOW_MMOL,
)
from PIL import Image


class User(AbstractUser):
    """Custom user model — email is the login credential, not username."""

    email = models.EmailField(unique=True)
    # The extension list is an attack-surface cut, not a format preference.
    # Django's ImageField validator accepts every extension Pillow registers --
    # 70 of them, including PSD, EPS, TGA, JPEG 2000, GD and FLI. Its own check
    # is only Image.verify(), which does not decode pixel data, but save()
    # below then calls thumbnail(), which does. That put user-supplied bytes
    # through every one of those C decoders; CVE-2026-25990 was an
    # out-of-bounds write in the PSD one. Four formats cover a profile picture.
    image = models.ImageField(
        default="default.jpg",
        upload_to="profile_pics",
        validators=[
            FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "webp"])
        ],
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.username or self.email

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # resize profile pictures on upload to keep storage and load times small
        if self.image and self.image.name != "default.jpg":
            try:
                img = Image.open(self.image.path)
                if img.height > 300 or img.width > 300:
                    img.thumbnail((300, 300))
                    img.save(self.image.path)
            # DecompressionBombError derives from Exception, not OSError, so it
            # was not caught here and reached the user as a 500. The form
            # rejects oversized pixel dimensions before this runs; this is the
            # backstop for anything that reaches save() by another route.
            except (FileNotFoundError, OSError, Image.DecompressionBombError):
                pass


class UserPreferences(models.Model):
    GLUCOSE_UNIT_MMOL = "mmol"
    GLUCOSE_UNIT_MGDL = "mg/dL"

    GLUCOSE_UNIT_CHOICES = [
        (GLUCOSE_UNIT_MMOL, "mmol/L"),
        (GLUCOSE_UNIT_MGDL, "mg/dL"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preferences"
    )
    glucose_unit = models.CharField(
        max_length=10, choices=GLUCOSE_UNIT_CHOICES, default=GLUCOSE_UNIT_MMOL
    )

    # The user's in-range band. Stored in mmol/L and at the same precision as
    # GlucoseLog.value, so a target entered in mg/dL survives the round trip
    # the same way a reading does (see logs.conversions.MMOL_QUANTUM). The
    # defaults are the standard adult band, so existing rows and new signups
    # behave exactly as the fixed thresholds did before.
    target_low = models.DecimalField(
        max_digits=6, decimal_places=3, default=DEFAULT_TARGET_LOW_MMOL
    )
    target_high = models.DecimalField(
        max_digits=6, decimal_places=3, default=DEFAULT_TARGET_HIGH_MMOL
    )

    # Grams of carbohydrate in one bread unit. Varies by country (12 g BE,
    # 10 g KE, 15 g US exchange), so it is the user's to set. The floor is a
    # correctness guard, not a product opinion: this value is a divisor.
    bread_unit_grams = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=DEFAULT_BREAD_UNIT_GRAMS,
        validators=[MinValueValidator(Decimal("0.1"))],
    )


class HealthProfile(models.Model):
    DIABETES_TYPE_1 = "type1"
    DIABETES_TYPE_2 = "type2"

    DIABETES_TYPE_CHOICES = [(DIABETES_TYPE_1, "Type 1"), (DIABETES_TYPE_2, "Type 2")]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="health_profile",
    )
    diabetes_type = models.CharField(
        max_length=10, choices=DIABETES_TYPE_CHOICES, default=DIABETES_TYPE_1
    )

    def __str__(self):
        return f"{self.user.username} profile"
