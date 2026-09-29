from django.contrib import admin

from .models import Review


@admin.action(description="Approve selected reviews")
def approve_reviews(modeladmin, request, queryset):
    queryset.update(is_approved=True)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "name", "rating", "is_verified_purchase", "is_approved", "created_at")
    list_filter = ("rating", "is_verified_purchase", "is_approved")
    search_fields = ("product__name", "name", "email", "title", "body")
    actions = (approve_reviews,)
