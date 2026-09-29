from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string

from .models import Bundle, Category, Product, with_sale_pricing


def product_queryset():
    return with_sale_pricing(
        Product.objects.filter(status=Product.Status.ACTIVE)
        .select_related("category")
        .prefetch_related("images")
        .annotate(avg_rating=Avg("reviews__rating", filter=Q(reviews__is_approved=True)))
        .annotate(review_count=Count("reviews", filter=Q(reviews__is_approved=True)))
    )


def product_list(request, category_slug=None):
    products = product_queryset()
    category = None
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug, is_active=True)
        products = products.filter(Q(category=category) | Q(category__parent=category))
    query = request.GET.get("q", "").strip()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(short_description__icontains=query) | Q(sku__icontains=query))
    if request.GET.get("stock") == "in":
        products = products.filter(Q(track_inventory=False) | Q(stock__gt=0))
    try:
        if request.GET.get("min_price"):
            products = products.filter(price__gte=Decimal(request.GET["min_price"]))
        if request.GET.get("max_price"):
            products = products.filter(price__lte=Decimal(request.GET["max_price"]))
    except InvalidOperation:
        pass
    sort = request.GET.get("sort", "featured")
    orderings = {
        "newest": "-created_at", "price-low": "price", "price-high": "-price",
        "name": "name", "featured": "-is_featured",
    }
    products = products.order_by(orderings.get(sort, "-is_featured"), "name")
    page = Paginator(products, 12).get_page(request.GET.get("page"))
    return render(request, "catalog/product_list.html", {
        "page_obj": page, "category": category, "query": query, "sort": sort,
        "categories": Category.objects.filter(is_active=True, parent__isnull=True),
    })


def product_detail(request, slug):
    product = get_object_or_404(product_queryset(), slug=slug)
    related = product_queryset().filter(category=product.category).exclude(pk=product.pk)[:4]
    reviews_page = Paginator(product.reviews.filter(is_approved=True), 6).get_page(1)
    from apps.cart.services import Cart

    cart = Cart(request)
    in_cart = cart.product_quantity(product.id)
    available = cart.available_to_add(product)
    return render(request, "catalog/product_detail.html", {
        "product": product,
        "related": related,
        "reviews": reviews_page.object_list,
        "reviews_page": reviews_page,
        "cart_qty": in_cart,
        "available_qty": available,
        "max_qty": max(1, available) if available else 0,
    })


def product_reviews(request, slug):
    product = get_object_or_404(Product, slug=slug, status=Product.Status.ACTIVE)
    page = Paginator(product.reviews.filter(is_approved=True), 6).get_page(request.GET.get("page", 1))
    return JsonResponse({
        "html": render_to_string("includes/review_cards.html", {"reviews": page.object_list}, request=request),
        "has_more": page.has_next(),
        "next_page": page.next_page_number() if page.has_next() else None,
    })


def quick_view(request, product_id):
    product = get_object_or_404(product_queryset(), pk=product_id)
    from apps.cart.services import Cart

    cart = Cart(request)
    available = cart.available_to_add(product)
    return render(request, "includes/quick_view.html", {
        "product": product,
        "cart_qty": cart.product_quantity(product.id),
        "available_qty": available,
        "max_qty": max(1, available) if available else 0,
    })


def search_suggestions(request):
    query = request.GET.get("q", "").strip()
    if len(query) < 2:
        return JsonResponse({"results": []})
    products = product_queryset().filter(name__icontains=query)[:6]
    return JsonResponse({"results": [{"name": p.name, "url": p.get_absolute_url(), "price": str(p.price)} for p in products]})


def bundle_list(request):
    bundles = Bundle.objects.filter(is_active=True).prefetch_related("items__product", "eligible_categories")
    return render(request, "catalog/bundle_list.html", {"bundles": bundles})


def bundle_detail(request, slug):
    bundle = get_object_or_404(Bundle.objects.prefetch_related("items__product", "eligible_categories"), slug=slug, is_active=True)
    eligible = with_sale_pricing(
        Product.objects.filter(status=Product.Status.ACTIVE, category__in=bundle.eligible_categories.all())
    )
    return render(request, "catalog/bundle_detail.html", {"bundle": bundle, "eligible_products": eligible})
