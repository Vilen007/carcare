from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import RegistrationForm


def register(request):
    form = RegistrationForm(request.POST or None)
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest"
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
        except IntegrityError:
            form.add_error("username", "That account was just registered. Try signing in instead.")
        else:
            login(request, user)
            messages.success(request, f"Welcome to Carcare, {user.first_name}! Your account is ready.")
            if is_ajax:
                return JsonResponse({"redirect": reverse("customers:account")})
            return redirect("customers:account")
    if request.method == "POST" and is_ajax:
        return JsonResponse({"errors": form.errors.get_json_data(escape_html=True)}, status=400)
    return render(request, "customers/register.html", {"form": form})


class CustomerLoginView(auth_views.LoginView):
    template_name = "customers/login.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Welcome back, {self.request.user.first_name or self.request.user.username}.")
        return response


class CustomerLogoutView(auth_views.LogoutView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.success(request, "You have been signed out safely.")
        return response


@login_required
def account(request):
    return render(request, "customers/account.html", {
        "orders": request.user.orders.prefetch_related("items")[:20],
        "addresses": request.user.addresses.all(),
    })
