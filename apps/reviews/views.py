from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from apps.catalog.models import Product
from apps.core.security import rate_limit
from apps.orders.models import Order

from .forms import ReviewForm


@require_POST
@rate_limit("reviews", limit=5, period=600)
def create(request, product_id):
    product = get_object_or_404(Product, pk=product_id, status=Product.Status.ACTIVE)
    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.product = product
        review.user = request.user if request.user.is_authenticated else None
        review.is_verified_purchase = Order.objects.filter(
            email__iexact=review.email, items__product=product, status=Order.Status.DELIVERED
        ).exists()
        try:
            review.save()
            messages.success(request, "Thank you. Your review will appear after moderation.")
        except Exception:
            messages.info(request, "A review from this email already exists for this product.")
    else:
        messages.error(request, "Please complete every review field correctly.")
    return redirect(product)
