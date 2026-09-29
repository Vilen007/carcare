from django.db.models import F, Q
from django.shortcuts import render

from apps.catalog.models import Product
from apps.content.models import ContactMessage
from apps.dashboard.decorators import staff_required
from apps.orders.models import Order
from apps.reviews.models import Review


@staff_required
def overview(request):
    low_stock = Product.objects.filter(track_inventory=True, stock__lte=F("low_stock_threshold")).exclude(status=Product.Status.ARCHIVED)
    return render(request, "dashboard/overview.html", {
        "pending_orders": Order.objects.filter(status=Order.Status.PENDING).count(),
        "recent_orders": Order.objects.prefetch_related("items")[:8],
        "low_stock_count": low_stock.count(),
        "low_stock_products": low_stock.select_related("category")[:8],
        "pending_reviews": Review.objects.filter(is_approved=False).count(),
        "unresolved_contacts": ContactMessage.objects.filter(is_resolved=False).count(),
        "confirmed_today": Order.objects.filter(status=Order.Status.CONFIRMED).count(),
    })
