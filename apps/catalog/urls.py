from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.product_list, name="list"),
    path("search/suggestions/", views.search_suggestions, name="search_suggestions"),
    path("category/<slug:category_slug>/", views.product_list, name="category"),
    path("product/<slug:slug>/", views.product_detail, name="product"),
    path("product/<slug:slug>/reviews/", views.product_reviews, name="product_reviews"),
    path("quick-view/<int:product_id>/", views.quick_view, name="quick_view"),
    path("bundles/", views.bundle_list, name="bundles"),
    path("bundles/<slug:slug>/", views.bundle_detail, name="bundle_detail"),
]
