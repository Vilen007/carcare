from django.contrib.auth import login
from django.contrib.auth.views import LogoutView
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.dashboard.decorators import staff_required
from apps.dashboard.forms import StaffLoginForm


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("dashboard:overview")
    form = StaffLoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect(request.GET.get("next") or "dashboard:overview")
    return render(request, "dashboard/login.html", {"form": form})


class StaffLogoutView(LogoutView):
    next_page = "dashboard:login"


logout_view = StaffLogoutView.as_view()
