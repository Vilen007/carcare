from django.urls import path

from . import views

app_name = "content"

urlpatterns = [
    path("contact/", views.contact, name="contact"),
    path("newsletter/", views.newsletter, name="newsletter"),
    path("<slug:slug>/", views.page, name="page"),
]
