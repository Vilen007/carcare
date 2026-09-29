from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("_security/csrf/", views.csrf_token, name="csrf_token"),
]
