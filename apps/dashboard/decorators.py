from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect


def staff_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url="dashboard:login")
        if not request.user.is_staff:
            return redirect("core:home")
        return view(request, *args, **kwargs)

    return wrapped
