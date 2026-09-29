from django.db import models

from apps.catalog.models import TimeStampedModel


class SiteSettings(TimeStampedModel):
    store_name = models.CharField(max_length=100, default="Carcare")
    announcement = models.CharField(max_length=220, default="Free nationwide delivery on qualifying orders")
    support_phone = models.CharField(max_length=30, blank=True)
    support_email = models.EmailField(default="hello@carcare.pk")
    whatsapp_number = models.CharField(max_length=30, blank=True)
    instagram_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    tiktok_url = models.URLField(blank=True)
    address = models.CharField(max_length=250, blank=True)

    class Meta:
        verbose_name_plural = "site settings"

    def __str__(self):
        return self.store_name


class HeroSlide(TimeStampedModel):
    eyebrow = models.CharField(max_length=80, blank=True)
    title = models.CharField(max_length=160)
    subtitle = models.CharField(max_length=260)
    image = models.ImageField(upload_to="content/heroes/", blank=True)
    cta_label = models.CharField(max_length=50, default="Shop collection")
    cta_url = models.CharField(max_length=200, default="/shop/")
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sort_order",)

    def __str__(self):
        return self.title


class Page(TimeStampedModel):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=160)
    body = models.TextField()
    meta_description = models.CharField(max_length=300, blank=True)
    is_published = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class NewsletterSubscriber(TimeStampedModel):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.email


class ContactMessage(TimeStampedModel):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    subject = models.CharField(max_length=160)
    message = models.TextField()
    is_resolved = models.BooleanField(default=False)

    def __str__(self):
        return self.subject
