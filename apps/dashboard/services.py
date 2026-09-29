from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import InventoryAdjustment, Product
from apps.orders.models import Order, Shipment, TrackingEvent


@transaction.atomic
def set_order_status(order, status, *, notify=True, description=""):
    previous = order.status
    if previous == status:
        return order
    order.status = status
    if status == Order.Status.CONFIRMED and not order.confirmed_at:
        order.confirmed_at = timezone.now()
    order.save(update_fields=["status", "confirmed_at", "updated_at"])
    TrackingEvent.objects.create(
        order=order,
        status=status,
        title=order.get_status_display(),
        description=description or "Order status updated by the Carcare team.",
    )
    if notify:
        send_mail(
            f"Order {order.number}: {order.get_status_display()}",
            f"Your Carcare order is now {order.get_status_display().lower()}. Track it using {order.number}.",
            None,
            [order.email],
            fail_silently=True,
        )
    return order


@transaction.atomic
def confirm_orders(queryset):
    confirmed = 0
    for order in queryset.filter(status=Order.Status.PENDING).select_for_update():
        set_order_status(order, Order.Status.CONFIRMED, description="Order confirmed by Carcare operations.")
        confirmed += 1
    return confirmed


@transaction.atomic
def upsert_shipment(order, courier="", tracking_number="", shipped_at=None, delivered_at=None):
    shipment, _ = Shipment.objects.get_or_create(order=order)
    shipment.courier = courier
    shipment.tracking_number = tracking_number
    shipment.shipped_at = shipped_at or shipment.shipped_at
    shipment.delivered_at = delivered_at or shipment.delivered_at
    shipment.save()
    return shipment


@transaction.atomic
def apply_inventory_adjustment(*, product, quantity, reason, reference="", note="", user=None):
    """Apply a signed stock delta and write a ledger row.

    Callers should pass a signed quantity (positive = stock in, negative = stock out).
    """
    delta = int(quantity)
    product_locked = Product.objects.select_for_update().get(pk=product.pk)
    new_stock = product_locked.stock + delta
    if new_stock < 0:
        raise ValueError(f"Stock cannot go below zero (would be {new_stock}).")
    Product.objects.filter(pk=product.pk).update(stock=new_stock)
    return InventoryAdjustment.objects.create(
        product=product,
        quantity=delta,
        reason=reason,
        reference=reference,
        note=note,
        created_by=user,
    )
