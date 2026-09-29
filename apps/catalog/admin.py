import csv

from django.contrib import admin
from django.db.models import F
from django.http import HttpResponse

from .models import Bundle, BundleItem, Category, InventoryAdjustment, Product, ProductImage, ProductVariant


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "is_active", "show_in_navigation", "sort_order")
    list_editable = ("is_active", "show_in_navigation", "sort_order")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.action(description="Mark selected products active")
def activate_products(modeladmin, request, queryset):
    queryset.update(status=Product.Status.ACTIVE)


@admin.action(description="Export selected inventory to CSV")
def export_inventory(modeladmin, request, queryset):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="carcare-inventory.csv"'
    writer = csv.writer(response)
    writer.writerow(["SKU", "Product", "Category", "Price", "Stock", "Low-stock threshold", "Status"])
    for product in queryset.select_related("category"):
        writer.writerow([product.sku, product.name, product.category.name, product.price, product.stock, product.low_stock_threshold, product.status])
    return response


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "category", "price", "stock", "status", "is_featured")
    list_filter = ("status", "category", "is_featured", "is_new")
    list_editable = ("price", "stock", "status", "is_featured")
    search_fields = ("name", "sku", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ProductImageInline, ProductVariantInline)
    actions = (activate_products, export_inventory)
    save_on_top = True


class BundleItemInline(admin.TabularInline):
    model = BundleItem
    extra = 1


@admin.register(Bundle)
class BundleAdmin(admin.ModelAdmin):
    list_display = ("name", "discount_percent", "is_custom_builder", "is_active")
    list_editable = ("discount_percent", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("eligible_categories",)
    inlines = (BundleItemInline,)


@admin.register(InventoryAdjustment)
class InventoryAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("product", "quantity", "reason", "reference", "created_by", "created_at")
    list_filter = ("reason", "created_at")
    search_fields = ("product__name", "product__sku", "reference")
    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        if not change:
            Product.objects.filter(pk=obj.product_id).update(stock=F("stock") + obj.quantity)
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
