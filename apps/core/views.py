from urllib.parse import urlparse

from django.contrib import messages
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie

from apps.catalog.models import Bundle, Category, Product, with_sale_pricing
from apps.content.models import HeroSlide
from apps.reviews.models import Review


def home(request):
    products = with_sale_pricing(
        Product.objects.filter(status=Product.Status.ACTIVE, is_featured=True)
        .select_related("category")
        .prefetch_related("images")
        .annotate(avg_rating=Avg("reviews__rating", filter=Q(reviews__is_approved=True)))
        .annotate(review_count=Count("reviews", filter=Q(reviews__is_approved=True)))
    )[:8]
    return render(request, "core/home.html", {
        "products": products,
        "categories": Category.objects.filter(is_active=True, parent__isnull=True)[:6],
        "bundles": Bundle.objects.filter(is_active=True, is_custom_builder=False).prefetch_related("items__product")[:3],
        "hero": HeroSlide.objects.filter(is_active=True).first(),
        "reviews": Review.objects.filter(is_approved=True).select_related("product")[:10],
    })


@never_cache
@ensure_csrf_cookie
def csrf_token(request):
    return JsonResponse({"token": get_token(request)})


def csrf_failure(request, reason=""):
    messages.error(
        request,
        "Your secure session expired. Please try submitting the form again.",
    )
    referrer = urlparse(request.META.get("HTTP_REFERER", ""))
    if referrer.netloc == request.get_host() and referrer.path:
        return redirect(referrer.path)
    return redirect("core:home")
