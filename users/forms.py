from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from .models import User

from django import forms
from logs.conversions import entry_bounds, mgdl_to_mmol, to_display

from .models import UserPreferences, HealthProfile


class CustomUserCreationForm(AdminUserCreationForm):
    usable_password = None
    # remove help text
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fieldname in ["username", "password1", "password2"]:
            self.fields[fieldname].help_text = None
        self.fields["password2"].label = "Confirm Password"

    class Meta:
        model = User
        fields = ("username", "email")


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ("username", "email")


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'image']

class PreferencesForm(forms.ModelForm):
    """Glucose unit plus the user's in-range band.

    The band is stored in mmol/L but typed in whichever unit the user reads,
    so the two target fields are declared here rather than taken from the
    model: they carry display values in and out, and convert at the edges the
    same way a logged reading does.

    Which unit "the user reads" is deliberately the *stored* one, not the one
    posted alongside. A ModelForm only writes posted values onto the instance
    in _post_clean(), which runs after clean(), so self.instance.glucose_unit
    here is still what the page was rendered with — and that is what the field
    labels said when the numbers were typed. Changing unit and targets in one
    submit therefore reads the targets in the old unit, which is what the user
    saw.
    """

    target_low = forms.DecimalField(
        label="Target low", max_digits=6, decimal_places=1, localize=False
    )
    target_high = forms.DecimalField(
        label="Target high", max_digits=6, decimal_places=1, localize=False
    )

    class Meta:
        model = UserPreferences
        fields = ["glucose_unit"]
        labels = {"glucose_unit": "Glucose Unit"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        unit = self._display_unit()
        suffix = "mg/dL" if unit else "mmol/L"
        self.fields["target_low"].label = f"Target low ({suffix})"
        self.fields["target_high"].label = f"Target high ({suffix})"

        low, high = entry_bounds(unit)
        for name in ("target_low", "target_high"):
            self.fields[name].widget.attrs.update(
                {"step": "0.1", "min": str(low), "max": str(high)}
            )

        # Show the stored mmol/L band in the unit the labels above announce.
        if self.instance is not None and self.instance.pk:
            self.initial.setdefault(
                "target_low", to_display(self.instance.target_low, unit)
            )
            self.initial.setdefault(
                "target_high", to_display(self.instance.target_high, unit)
            )

    def _display_unit(self):
        """True when the user reads mg/dL. See the note in the class docstring."""
        instance = getattr(self, "instance", None)
        unit = getattr(instance, "glucose_unit", None)
        return unit == UserPreferences.GLUCOSE_UNIT_MGDL

    def _to_storage(self, field, value):
        """Validate a typed target against its unit, and return it in mmol/L."""
        is_mgdl = self._display_unit()
        low, high = entry_bounds(is_mgdl)
        unit_label = "mg/dL" if is_mgdl else "mmol/L"

        # NaN and Infinity need no guard here: forms.DecimalField.validate()
        # already rejects a non-finite Decimal before clean() runs, which is
        # not true of the log entry views that hand-parse request.POST.
        if value < low or value > high:
            raise forms.ValidationError(
                {field: f"Enter a value between {low} and {high} {unit_label}."}
            )
        return mgdl_to_mmol(value) if is_mgdl else value

    def clean(self):
        cleaned = super().clean()
        low = cleaned.get("target_low")
        high = cleaned.get("target_high")
        if low is None or high is None:
            return cleaned

        try:
            low = self._to_storage("target_low", low)
            high = self._to_storage("target_high", high)
        except forms.ValidationError as error:
            self.add_error(None, error)
            return cleaned

        if low >= high:
            self.add_error(
                "target_high", "The upper target must be above the lower target."
            )
            return cleaned

        cleaned["target_low"] = low
        cleaned["target_high"] = high
        return cleaned

    def save(self, commit=True):
        preferences = super().save(commit=False)
        # These are not Meta fields, so ModelForm will not have written them.
        preferences.target_low = self.cleaned_data["target_low"]
        preferences.target_high = self.cleaned_data["target_high"]
        if commit:
            preferences.save()
        return preferences


class HealthProfileForm(forms.ModelForm):
    class Meta:
        model = HealthProfile
        fields = ["diabetes_type"]
        labels = {"diabetes_type": "Diabetes Type"}
