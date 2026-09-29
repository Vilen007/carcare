from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.text import slugify


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStampedModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    parent = models.ForeignKey("self", blank=True, null=True, on_delete=models.SET_NULL, related_name="children")
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="categories/", blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    show_in_navigation = models.BooleanField(default=True)
    meta_title = models.CharField(max_length=160, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ("sort_order", "name")
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:category", args=[self.slug])


class Product(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True)
    sku = models.CharField(max_length=64, unique=True)
    short_description = models.CharField(max_length=280)
    description = models.TextField()
    usage = models.TextField(blank=True)
    specifications = models.JSONField(default=dict, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    compare_at_price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    stock = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    track_inventory = models.BooleanField(default=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    is_featured = models.BooleanField(default=False)
    is_new = models.BooleanField(default=False)
    weight_grams = models.PositiveIntegerField(default=0)
    meta_title = models.CharField(max_length=160, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ("-is_featured", "-created_at")
        indexes = [
            models.Index(fields=["status", "category"]),
            models.Index(fields=["price"]),
            models.Index(fields=["sku"]),
        ]

    def __str__(self):
        return self.name

    @property
    def in_stock(self):
        return not self.track_inventory or self.stock > 0

    @property
    def discount_percent(self):
        compare_price = self.display_compare_price
        if compare_price and compare_price > self.current_price:
            return int((compare_price - self.current_price) * 100 / compare_price)
        return 0

    @cached_property
    def active_sale_discount(self):
        if hasattr(self, "_active_sale_discount"):
            return self._active_sale_discount or 0
        from apps.cart.models import SaleCampaign

        now = timezone.now()
        return (
            SaleCampaign.objects.filter(is_active=True, starts_at__lte=now, ends_at__gte=now)
            .filter(models.Q(applies_to_all=True) | models.Q(categories=self.category))
            .order_by("-discount_percent")
            .values_list("discount_percent", flat=True)
            .first()
            or 0
        )

    @property
    def current_price(self):
        if self.active_sale_discount:
            multiplier = (Decimal("100") - self.active_sale_discount) / Decimal("100")
            return (self.price * multiplier).quantize(Decimal("0.01"))
        return self.price

    @property
    def display_compare_price(self):
        if self.active_sale_discount:
            return self.compare_at_price if self.compare_at_price and self.compare_at_price > self.price else self.price
        return self.compare_at_price

    @property
    def primary_image(self):
        images = list(self.images.all())
        return next((image for image in images if image.is_primary), images[0] if images else None)

    def get_absolute_url(self):
        return reverse("catalog:product", args=[self.slug])

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/")
    alt_text = models.CharField(max_length=180, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ("sort_order", "id")

    def __str__(self):
        return f"{self.product} image"


class ProductVariant(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField(max_length=100)
    sku = models.CharField(max_length=64, unique=True)
    attributes = models.JSONField(default=dict, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("product", "name")

    def __str__(self):
        return f"{self.product.name} — {self.name}"


class InventoryAdjustment(TimeStampedModel):
    class Reason(models.TextChoices):
        PURCHASE = "purchase", "Purchase"
        ORDER = "order", "Order"
        RETURN = "return", "Return"
        DAMAGE = "damage", "Damage"
        CORRECTION = "correction", "Correction"

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="stock_movements")
    quantity = models.IntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    reference = models.CharField(max_length=100, blank=True)
    note = models.CharField(max_length=250, blank=True)
    created_by = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.product.sku}: {self.quantity:+d}"


class Bundle(TimeStampedModel):
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField()
    image = models.ImageField(upload_to="bundles/", blank=True)
    discount_percent = models.PositiveSmallIntegerField(default=5)
    is_active = models.BooleanField(default=True)
    is_custom_builder = models.BooleanField(default=False)
    minimum_items = models.PositiveSmallIntegerField(default=2)
    maximum_items = models.PositiveSmallIntegerField(default=8)
    eligible_categories = models.ManyToManyField(Category, blank=True, related_name="bundle_rules")

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name

    @property
    def original_price(self):
        return sum((item.product.current_price * item.quantity for item in self.items.all()), Decimal("0"))

    @property
    def price(self):
        return (self.original_price * (Decimal("100") - self.discount_percent) / Decimal("100")).quantize(Decimal("0.01"))

    def get_absolute_url(self):
        return reverse("catalog:bundle_detail", args=[self.slug])


class BundleItem(models.Model):
    bundle = models.ForeignKey(Bundle, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="bundle_items")
    quantity = models.PositiveSmallIntegerField(default=1)

    class Meta:
        unique_together = ("bundle", "product")

    def __str__(self):
        return f"{self.quantity} × {self.product.name}"


def with_sale_pricing(queryset):
    """Annotate products with their best live campaign to avoid storefront N+1 queries."""
    from apps.cart.models import SaleCampaign

    now = timezone.now()
    sale = (
        SaleCampaign.objects.filter(is_active=True, starts_at__lte=now, ends_at__gte=now)
        .filter(models.Q(applies_to_all=True) | models.Q(categories__pk=models.OuterRef("category_id")))
        .order_by("-discount_percent")
        .values("discount_percent")[:1]
    )
    return queryset.annotate(_active_sale_discount=models.Subquery(sale))
