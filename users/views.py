from django.conf import settings
from django.shortcuts import render, redirect, resolve_url
from django.contrib import messages

from logs.views.export import EXPORT_RANGES, EXPORT_TYPES
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit


def _redirect_target(request):
    """Where to send a user after they authenticate.

    Honours ?next= so @login_required sends them on to the page they actually
    asked for, but only when it points back at this site — an unchecked `next`
    is an open redirect.
    """
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(
        url=target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return target
    return resolve_url(settings.LOGIN_REDIRECT_URL)

from .services import (
    handle_preferences_form,
    handle_health_profile_form,
    handle_profile_form,
)
from .forms import CustomUserCreationForm


# Only POSTs are limited, so a rate-limited visitor can still load the form and
# read the error. Exceeding the limit raises Ratelimited (a PermissionDenied
# subclass), which Django renders with templates/403.html.
@ratelimit(key="ip", rate="10/h", method="POST", block=True)
def register_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get("username")
            login(request, user)
            messages.success(request, f"Account created for {username}")
            return redirect(_redirect_target(request))
    else:
        form = CustomUserCreationForm()
    return render(request, "users/register.html", {"form": form})


# Limited per IP and again per submitted credential, so a single account cannot
# be ground down from rotating addresses.
@ratelimit(key="ip", rate="10/5m", method="POST", block=True)
@ratelimit(key="post:username", rate="5/5m", method="POST", block=True)
def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request=request, data=request.POST)
        if form.is_valid():
            # AuthenticationForm has already authenticated and cached the user;
            # calling authenticate() again would run the password hash a second
            # time on the endpoint most exposed to brute force.
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect(_redirect_target(request))
        else:
            messages.error(request, "Invalid username or password")
    else:
        form = AuthenticationForm()
    return render(request, "users/login.html", {"form": form})


@login_required
def user_profile_view(request):
    profile_form = handle_profile_form(request)
    preferences_form = handle_preferences_form(request)
    health_profile_form = handle_health_profile_form(request)

    if request.method == "POST":
        forms = (profile_form, preferences_form, health_profile_form)
        # All three sections live in one <form>, so every submit posts all of
        # them together. Validate as a unit and save atomically — saving only
        # the sections that happened to validate silently drops the one that
        # didn't, with no error shown (the bug this replaced).
        if all([form.is_valid() for form in forms]):
            with transaction.atomic():
                for form in forms:
                    form.save()
            messages.success(request, "Profile updated")
            return redirect("user-profile")
        messages.error(request, "Please fix the errors below")

    context = {
        "preferences_form": preferences_form,
        "health_profile_form": health_profile_form,
        "update_profile_form": profile_form,
        # The export form is a plain GET to logs, deliberately outside the
        # combined POST above — downloading is not a settings change and must
        # not be able to fail because an unrelated section is invalid.
        "export_types": EXPORT_TYPES,
        "export_ranges": EXPORT_RANGES,
    }
    return render(request, "users/profile.html", context)


@require_POST
def logout_view(request):
    logout(request)
    # redirect to login
    return redirect("glucoread-home")
