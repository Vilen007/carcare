import secrets
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.catalog.models import TimeStampedModel


class Province(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    cod_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    free_shipping_threshold = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    estimated_days = models.CharField(max_length=50, default="2–5 business days")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name

    def calculate(self, subtotal):
        shipping = Decimal("0") if self.free_shipping_threshold and subtotal >= self.free_shipping_threshold else self.shipping_fee
        return shipping, self.cod_fee


class City(TimeStampedModel):
    province = models.ForeignKey(Province, on_delete=models.CASCADE, related_name="cities")
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "cities"
        constraints = [
            models.UniqueConstraint(fields=["province", "name"], name="unique_city_per_province")
        ]

    def __str__(self):
        return f"{self.name}, {self.province.name}"


class Order(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending confirmation"
        CONFIRMED = "confirmed", "Confirmed"
        PACKING = "packing", "Packing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"
        RETURNED = "returned", "Returned"

    number = models.CharField(max_length=20, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL, related_name="orders")
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=30, db_index=True)
    full_name = models.CharField(max_length=160)
    address_line_1 = models.CharField(max_length=200)
    address_line_2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    province = models.CharField(max_length=100)
    delivery_city = models.ForeignKey(City, blank=True, null=True, on_delete=models.SET_NULL, related_name="orders")
    delivery_province = models.ForeignKey(Province, blank=True, null=True, on_delete=models.SET_NULL, related_name="orders")
    postal_code = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    payment_method = models.CharField(max_length=20, default="cod", editable=False)
    payment_status = models.CharField(max_length=20, default="unpaid")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    coupon = models.ForeignKey("cart.Coupon", blank=True, null=True, on_delete=models.SET_NULL, related_name="orders")
    coupon_code = models.CharField(max_length=30, blank=True)
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cod_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    customer_note = models.TextField(blank=True)
    admin_note = models.TextField(blank=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["number", "email"]), models.Index(fields=["status", "-created_at"])]

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = f"CC-{timezone.now():%y%m}-{secrets.token_hex(3).upper()}"
        super().save(*args, **kwargs)

    @property
    def amount_due(self):
        return self.total if self.payment_status != "paid" else Decimal("0")


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("catalog.Product", blank=True, null=True, on_delete=models.SET_NULL)
    bundle = models.ForeignKey("catalog.Bundle", blank=True, null=True, on_delete=models.SET_NULL)
    product_name = models.CharField(max_length=200)
    sku = models.CharField(max_length=64)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    configuration = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.quantity} × {self.product_name}"


class Shipment(TimeStampedModel):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="shipment")
    courier = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    shipped_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Shipment for {self.order.number}"


class TrackingEvent(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="tracking_events")
    status = models.CharField(max_length=20, choices=Order.Status.choices)
    title = models.CharField(max_length=120)
    description = models.CharField(max_length=300, blank=True)
    location = models.CharField(max_length=120, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-occurred_at",)

    def __str__(self):
        return f"{self.order.number}: {self.title}"
