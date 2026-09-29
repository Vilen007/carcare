import csv

from django.contrib import admin
from django.core.mail import send_mail
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import City, Order, OrderItem, Province, Shipment, TrackingEvent


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product_name", "sku", "unit_price", "quantity", "line_total", "configuration")
    can_delete = False


class TrackingEventInline(admin.TabularInline):
    model = TrackingEvent
    extra = 1


class ShipmentInline(admin.StackedInline):
    model = Shipment
    extra = 0
    max_num = 1


@admin.action(description="Export selected orders to CSV")
def export_orders(modeladmin, request, queryset):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="carcare-orders.csv"'
    writer = csv.writer(response)
    writer.writerow(["Order", "Date", "Customer", "Phone", "City", "Status", "Total"])
    for order in queryset:
        writer.writerow([order.number, order.created_at, order.full_name, order.phone, order.city, order.status, order.total])
    return response


@admin.action(description="Mark selected orders confirmed")
def confirm_orders(modeladmin, request, queryset):
    queryset.filter(status=Order.Status.PENDING).update(status=Order.Status.CONFIRMED, confirmed_at=timezone.now())


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("number", "full_name", "city", "status", "payment_status", "total", "created_at")
    list_filter = ("status", "payment_status", "province", "created_at")
    search_fields = ("number", "full_name", "email", "phone")
    readonly_fields = ("number", "subtotal", "discount", "coupon", "coupon_code", "shipping_fee", "cod_fee", "total", "created_at", "updated_at", "document_links")
    inlines = (OrderItemInline, ShipmentInline, TrackingEventInline)
    actions = (confirm_orders, export_orders)
    date_hierarchy = "created_at"

    def save_model(self, request, obj, form, change):
        previous_status = Order.objects.filter(pk=obj.pk).values_list("status", flat=True).first() if change else None
        if obj.status == Order.Status.CONFIRMED and not obj.confirmed_at:
            obj.confirmed_at = timezone.now()
        super().save_model(request, obj, form, change)
        if previous_status and previous_status != obj.status:
            TrackingEvent.objects.create(
                order=obj,
                status=obj.status,
                title=obj.get_status_display(),
                description="Order status updated by the Carcare team.",
            )
            send_mail(
                f"Order {obj.number}: {obj.get_status_display()}",
                f"Your Carcare order is now {obj.get_status_display().lower()}. Track it using {obj.number}.",
                None,
                [obj.email],
                fail_silently=True,
            )

    @admin.display(description="Documents")
    def document_links(self, obj):
        if not obj.pk:
            return "Save the order to create documents."
        return format_html(
            '<a href="{}" target="_blank">Invoice</a> &nbsp; <a href="{}" target="_blank">Packing slip</a>',
            reverse("orders:invoice", args=[obj.number]),
            reverse("orders:packing_slip", args=[obj.number]),
        )


class CityInline(admin.TabularInline):
    model = City
    extra = 1


@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ("name", "shipping_fee", "cod_fee", "free_shipping_threshold", "is_active")
    list_editable = ("shipping_fee", "cod_fee", "free_shipping_threshold", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    inlines = (CityInline,)


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "province", "is_active")
    list_editable = ("is_active",)
    list_filter = ("province", "is_active")
    search_fields = ("name", "province__name")


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ("order", "courier", "tracking_number", "shipped_at", "delivered_at")
    search_fields = ("order__number", "tracking_number")
