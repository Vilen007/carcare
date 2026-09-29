from django.contrib import admin

from .models import Coupon, SaleCampaign


@admin.register(SaleCampaign)
class SaleCampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "discount_percent", "starts_at", "ends_at", "applies_to_all", "is_active")
    list_filter = ("is_active", "applies_to_all")
    search_fields = ("name", "banner_text")
    filter_horizontal = ("categories",)


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "discount_percent", "minimum_subtotal", "starts_at", "ends_at", "times_used", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code",)
