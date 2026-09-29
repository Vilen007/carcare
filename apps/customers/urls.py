from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "customers"

urlpatterns = [
    path("", views.account, name="account"),
    path("register/", views.register, name="register"),
    path("login/", views.CustomerLoginView.as_view(), name="login"),
    path("logout/", views.CustomerLogoutView.as_view(), name="logout"),
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="customers/password_reset.html",
        email_template_name="registration/password_reset_email.html",
        subject_template_name="registration/password_reset_subject.txt",
        success_url=reverse_lazy("customers:password_reset_done"),
    ), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(template_name="customers/password_reset_done.html"), name="password_reset_done"),
    path("password-reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="customers/password_reset_confirm.html",
        success_url=reverse_lazy("customers:password_reset_complete"),
    ), name="password_reset_confirm"),
    path("password-reset/complete/", auth_views.PasswordResetCompleteView.as_view(template_name="customers/password_reset_complete.html"), name="password_reset_complete"),
]
