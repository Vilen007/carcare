from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.catalog.models import TimeStampedModel


class SaleCampaign(TimeStampedModel):
    name = models.CharField(max_length=120)
    discount_percent = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(90)]
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    applies_to_all = models.BooleanField(
        default=True,
        help_text="Apply to every active product. Otherwise select categories below.",
    )
    categories = models.ManyToManyField("catalog.Category", blank=True, related_name="sale_campaigns")
    banner_text = models.CharField(max_length=180, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-starts_at",)

    def __str__(self):
        return self.name

    @property
    def is_live(self):
        now = timezone.now()
        return self.is_active and self.starts_at <= now <= self.ends_at

    def clean(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "The sale must end after it starts."})


class Coupon(TimeStampedModel):
    code = models.CharField(max_length=30, unique=True)
    discount_percent = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(90)])
    minimum_subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    usage_limit = models.PositiveIntegerField(default=0, help_text="Zero means unlimited")
    times_used = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def is_valid(self, subtotal):
        now = timezone.now()
        under_limit = self.usage_limit == 0 or self.times_used < self.usage_limit
        return self.is_active and self.starts_at <= now <= self.ends_at and under_limit and subtotal >= self.minimum_subtotal

    def clean(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "The coupon must end after it starts."})
