from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [path("product/<int:product_id>/", views.create, name="create")]
