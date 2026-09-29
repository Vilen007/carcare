from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("cities/", views.cities, name="cities"),
    path("confirmed/<str:number>/", views.confirmation, name="confirmation"),
    path("track/", views.track, name="track"),
    path("<str:number>/invoice/", views.invoice, name="invoice"),
    path("<str:number>/packing-slip/", views.packing_slip, name="packing_slip"),
]
