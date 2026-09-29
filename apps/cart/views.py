from django.contrib import messages
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.catalog.models import Bundle, Product

from .services import Cart


def detail(request):
    cart = Cart(request)
    return render(request, "cart/detail.html", {"cart": cart, "cart_lines": cart.lines()})


@require_POST
def add_product(request, product_id):
    product = get_object_or_404(Product, pk=product_id, status=Product.Status.ACTIVE)
    try:
        quantity = max(1, min(int(request.POST.get("quantity", 1)), 99))
    except (TypeError, ValueError):
        quantity = 1

    cart = Cart(request)
    if not product.in_stock:
        messages.error(request, f"{product.name} is out of stock.")
        return redirect(request.POST.get("next") or product.get_absolute_url())

    available = cart.available_to_add(product)
    if available <= 0:
        messages.error(
            request,
            f"You already have the maximum available stock of {product.name} in your cart "
            f"({product.stock} in stock).",
        )
        return redirect(request.POST.get("next") or "cart:detail")

    if quantity > available:
        messages.error(
            request,
            f"Only {available} more of {product.name} can be added "
            f"({product.stock} in stock"
            f"{', ' + str(cart.product_quantity(product.id)) + ' already in cart' if cart.product_quantity(product.id) else ''}).",
        )
        return redirect(request.POST.get("next") or product.get_absolute_url())

    cart.add_product(product.id, quantity)
    messages.success(request, f"{product.name} added to your cart.")
    return redirect(request.POST.get("next") or "cart:detail")


@require_POST
def add_bundle(request, bundle_id):
    bundle = get_object_or_404(Bundle, pk=bundle_id, is_active=True)
    product_ids = request.POST.getlist("products") if bundle.is_custom_builder else None
    if bundle.is_custom_builder:
        selected = Product.objects.filter(
            id__in=product_ids, status=Product.Status.ACTIVE, category__in=bundle.eligible_categories.all()
        )
        if selected.count() != len(set(product_ids)) or not bundle.minimum_items <= selected.count() <= bundle.maximum_items:
            return HttpResponseBadRequest("Choose a valid number of eligible products.")
        for product in selected:
            if product.track_inventory and product.stock < 1:
                messages.error(request, f"{product.name} is out of stock.")
                return redirect(bundle.get_absolute_url())
    else:
        for item in bundle.items.select_related("product"):
            product = item.product
            needed = item.quantity
            if product.track_inventory and product.stock < needed:
                messages.error(
                    request,
                    f"{product.name} needs {needed} for this kit but only {product.stock} remain.",
                )
                return redirect(bundle.get_absolute_url())
    Cart(request).add_bundle(bundle.id, product_ids=product_ids)
    messages.success(request, f"{bundle.name} added to your cart.")
    return redirect("cart:detail")


@require_POST
def update(request, key):
    cart = Cart(request)
    try:
        quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1

    raw = cart.data.get(key)
    if raw and raw.get("type") == "product" and quantity > 0:
        product = Product.objects.filter(pk=raw["id"], status=Product.Status.ACTIVE).first()
        if product and product.track_inventory and quantity > product.stock:
            messages.error(
                request,
                f"{product.name} has only {product.stock} in stock. Quantity was not updated.",
            )
            return redirect("cart:detail")

    cart.update(key, quantity)
    messages.success(request, "Cart updated.")
    return redirect("cart:detail")


@require_POST
def remove(request, key):
    Cart(request).remove(key)
    return redirect("cart:detail")


@require_POST
def apply_coupon(request):
    cart = Cart(request)
    applied, message = cart.apply_coupon(request.POST.get("code", ""))
    if applied:
        messages.success(request, message)
    else:
        messages.error(request, message)
    return redirect("cart:detail")


@require_POST
def remove_coupon(request):
    Cart(request).remove_coupon()
    messages.info(request, "Coupon removed from your cart.")
    return redirect("cart:detail")
