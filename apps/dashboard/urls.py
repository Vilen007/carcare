from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.overview, name="overview"),
    # Orders
    path("orders/", views.order_list, name="orders"),
    path("orders/export/", views.order_export_csv, name="orders_export"),
    path("orders/confirm/", views.order_bulk_confirm, name="orders_confirm"),
    path("orders/<str:number>/", views.order_detail, name="order_detail"),
    path("orders/<str:number>/status/", views.order_update_status, name="order_status"),
    path("orders/<str:number>/shipment/", views.order_update_shipment, name="order_shipment"),
    path("orders/<str:number>/tracking/", views.order_add_tracking, name="order_tracking"),
    # Catalog
    path("categories/", views.category_list, name="categories"),
    path("categories/new/", views.category_edit, name="category_new"),
    path("categories/<int:pk>/", views.category_edit, name="category_edit"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("products/", views.product_list, name="products"),
    path("products/new/", views.product_edit, name="product_new"),
    path("products/<int:pk>/", views.product_edit, name="product_edit"),
    path("products/<int:pk>/activate/", views.product_activate, name="product_activate"),
    path("products/<int:pk>/archive/", views.product_archive, name="product_archive"),
    path("products/<int:pk>/delete/", views.product_delete, name="product_delete"),
    # Inventory
    path("inventory/", views.inventory_home, name="inventory"),
    path("inventory/adjust/", views.inventory_adjust, name="inventory_adjust"),
    path("inventory/export/", views.inventory_export_csv, name="inventory_export"),
    # Bundles
    path("bundles/", views.bundle_list, name="bundles"),
    path("bundles/new/", views.bundle_edit, name="bundle_new"),
    path("bundles/<int:pk>/", views.bundle_edit, name="bundle_edit"),
    path("bundles/<int:pk>/delete/", views.bundle_delete, name="bundle_delete"),
    # Promotions
    path("promotions/", views.promotion_home, name="promotions"),
    path("promotions/sales/new/", views.sale_edit, name="sale_new"),
    path("promotions/sales/<int:pk>/", views.sale_edit, name="sale_edit"),
    path("promotions/sales/<int:pk>/delete/", views.sale_delete, name="sale_delete"),
    path("promotions/coupons/new/", views.coupon_edit, name="coupon_new"),
    path("promotions/coupons/<int:pk>/", views.coupon_edit, name="coupon_edit"),
    path("promotions/coupons/<int:pk>/delete/", views.coupon_delete, name="coupon_delete"),
    # Shipping
    path("shipping/", views.shipping_home, name="shipping"),
    path("shipping/provinces/new/", views.province_edit, name="province_new"),
    path("shipping/provinces/<int:pk>/", views.province_edit, name="province_edit"),
    path("shipping/provinces/<int:pk>/delete/", views.province_delete, name="province_delete"),
    path("shipping/cities/new/", views.city_edit, name="city_new"),
    path("shipping/cities/<int:pk>/", views.city_edit, name="city_edit"),
    path("shipping/cities/<int:pk>/delete/", views.city_delete, name="city_delete"),
    # Reviews
    path("reviews/", views.review_list, name="reviews"),
    path("reviews/<int:pk>/approve/", views.review_approve, name="review_approve"),
    path("reviews/<int:pk>/reject/", views.review_reject, name="review_reject"),
    # Customers
    path("customers/", views.customer_list, name="customers"),
    # Content
    path("content/", views.content_home, name="content"),
    path("content/settings/", views.site_settings_edit, name="site_settings"),
    path("content/heroes/new/", views.hero_edit, name="hero_new"),
    path("content/heroes/<int:pk>/", views.hero_edit, name="hero_edit"),
    path("content/heroes/<int:pk>/delete/", views.hero_delete, name="hero_delete"),
    path("content/pages/new/", views.page_edit, name="page_new"),
    path("content/pages/<int:pk>/", views.page_edit, name="page_edit"),
    path("content/pages/<int:pk>/delete/", views.page_delete, name="page_delete"),
    # Inbox
    path("inbox/", views.inbox_home, name="inbox"),
    path("inbox/contacts/<int:pk>/resolve/", views.contact_resolve, name="contact_resolve"),
    path("inbox/subscribers/<int:pk>/toggle/", views.subscriber_toggle, name="subscriber_toggle"),
    path("inbox/subscribers/export/", views.newsletter_export_csv, name="newsletter_export"),
]
