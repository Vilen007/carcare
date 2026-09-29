from django.urls import path

from . import views

app_name = "cart"

urlpatterns = [
    path("", views.detail, name="detail"),
    path("add/product/<int:product_id>/", views.add_product, name="add_product"),
    path("add/bundle/<int:bundle_id>/", views.add_bundle, name="add_bundle"),
    path("update/<path:key>/", views.update, name="update"),
    path("remove/<path:key>/", views.remove, name="remove"),
    path("coupon/apply/", views.apply_coupon, name="apply_coupon"),
    path("coupon/remove/", views.remove_coupon, name="remove_coupon"),
]
