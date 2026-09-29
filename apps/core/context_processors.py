from django.utils import timezone

from apps.cart.services import Cart
from apps.cart.models import SaleCampaign
from apps.catalog.models import Category
from apps.content.models import SiteSettings


def store_context(request):
    now = timezone.now()
    return {
        "nav_categories": Category.objects.filter(is_active=True, show_in_navigation=True, parent__isnull=True)[:8],
        "site_settings": SiteSettings.objects.first(),
        "cart_count": Cart(request).count,
        "active_sale": SaleCampaign.objects.filter(
            is_active=True, starts_at__lte=now, ends_at__gte=now
        ).order_by("-discount_percent").first(),
    }
