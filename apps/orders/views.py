from collections import defaultdict
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from apps.cart.services import Cart
from apps.cart.models import Coupon
from apps.catalog.models import InventoryAdjustment, Product
from apps.core.security import rate_limit
from apps.customers.models import Address

from .forms import CheckoutForm, TrackingForm
from .models import City, Order, OrderItem, Province, TrackingEvent


def checkout(request):
    cart = Cart(request)
    lines = cart.lines()
    if not lines:
        messages.info(request, "Your cart is empty.")
        return redirect("catalog:list")
    applied_coupon = cart.coupon
    initial = {"coupon_code": applied_coupon.code if applied_coupon else ""}
    if request.user.is_authenticated:
        initial.update({"email": request.user.email, "full_name": request.user.get_full_name()})
        address = request.user.addresses.filter(is_default=True).first()
        if address:
            for field in ("full_name", "phone", "address_line_1", "address_line_2", "postal_code"):
                initial[field] = getattr(address, field)
            province = Province.objects.filter(name__iexact=address.province, is_active=True).first()
            city = City.objects.filter(name__iexact=address.city, province=province, is_active=True).first()
            initial.update({"delivery_province": province, "delivery_city": city})
    form = CheckoutForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                subtotal = cart.subtotal
                province = form.cleaned_data["delivery_province"]
                city = form.cleaned_data["delivery_city"]
                coupon_code = form.cleaned_data["coupon_code"]
                coupon = None
                discount = Decimal("0")
                if coupon_code:
                    coupon = Coupon.objects.select_for_update().filter(code__iexact=coupon_code).first()
                    if not coupon or not coupon.is_valid(subtotal):
                        raise ValidationError(
                            "That coupon is expired, unavailable, or requires a higher subtotal.",
                            code="invalid_coupon",
                        )
                    discount = (subtotal * coupon.discount_percent / Decimal("100")).quantize(Decimal("0.01"))
                shipping_fee, cod_fee = province.calculate(subtotal)
                order = form.save(commit=False)
                order.user = request.user if request.user.is_authenticated else None
                order.province = province.name
                order.city = city.name
                order.subtotal = subtotal
                order.discount = discount
                order.coupon = coupon
                order.coupon_code = coupon.code if coupon else ""
                order.shipping_fee = shipping_fee
                order.cod_fee = cod_fee
                order.total = subtotal - discount + shipping_fee + cod_fee
                order.save()
                stock_needed = defaultdict(int)
                for line in lines:
                    if line.item_type == "product":
                        stock_needed[line.item.id] += line.quantity
                    elif line.configuration:
                        for selected in line.configuration["products"]:
                            stock_needed[selected["id"]] += line.quantity
                    else:
                        for bundle_item in line.item.items.all():
                            stock_needed[bundle_item.product_id] += bundle_item.quantity * line.quantity
                for product_id, quantity in stock_needed.items():
                    product = Product.objects.select_for_update().get(pk=product_id)
                    if product.track_inventory and product.stock < quantity:
                        raise ValidationError(f"{product.name} has only {product.stock} remaining.")
                    if product.track_inventory:
                        Product.objects.filter(pk=product_id).update(stock=F("stock") - quantity)
                        InventoryAdjustment.objects.create(
                            product=product, quantity=-quantity, reason=InventoryAdjustment.Reason.ORDER, reference=order.number
                        )
                for line in lines:
                    OrderItem.objects.create(
                        order=order,
                        product=line.item if line.item_type == "product" else None,
                        bundle=line.item if line.item_type == "bundle" else None,
                        product_name=line.item.name,
                        sku=line.item.sku if line.item_type == "product" else f"BUNDLE-{line.item.id}",
                        unit_price=line.unit_price,
                        quantity=line.quantity,
                        line_total=line.total,
                        configuration=line.configuration,
                    )
                TrackingEvent.objects.create(
                    order=order, status=Order.Status.PENDING, title="Order received",
                    description="Your cash-on-delivery order is awaiting confirmation.",
                )
                if coupon:
                    coupon.times_used += 1
                    coupon.save(update_fields=["times_used"])
                if request.user.is_authenticated and form.cleaned_data.get("save_address"):
                    Address.objects.get_or_create(
                        user=request.user, address_line_1=order.address_line_1,
                        defaults={field: getattr(order, field) for field in (
                            "full_name", "phone", "address_line_2", "city", "province", "postal_code"
                        )},
                    )
                transaction.on_commit(lambda: send_mail(
                    f"Order {order.number} received",
                    f"Thank you for your order. Your total is Rs. {order.total:,.0f}. Pay cash on delivery.",
                    None, [order.email], fail_silently=True,
                ))
        except ValidationError as exc:
            form.add_error("coupon_code" if exc.code == "invalid_coupon" else None, exc.message)
        else:
            cart.clear()
            request.session["last_order"] = order.number
            messages.success(
                request,
                f"Order {order.number} placed successfully. Thank you—our team will confirm it shortly.",
            )
            return redirect("orders:confirmation", number=order.number)
    province_id = form["delivery_province"].value()
    selected_province = form.fields["delivery_province"].queryset.filter(pk=province_id).first() if province_id else None
    shipping_fee, cod_fee = selected_province.calculate(cart.subtotal) if selected_province else (Decimal("0"), Decimal("0"))
    coupon_code = form["coupon_code"].value() or ""
    estimated_coupon = Coupon.objects.filter(code__iexact=coupon_code).first() if coupon_code else None
    estimated_discount = (
        (cart.subtotal * estimated_coupon.discount_percent / Decimal("100")).quantize(Decimal("0.01"))
        if estimated_coupon and estimated_coupon.is_valid(cart.subtotal) else Decimal("0")
    )
    return render(request, "orders/checkout.html", {
        "form": form, "cart_lines": lines, "subtotal": cart.subtotal,
        "estimated_discount": estimated_discount,
        "estimated_total": cart.subtotal - estimated_discount + shipping_fee + cod_fee,
    })


@require_GET
def cities(request):
    province_id = request.GET.get("province")
    results = City.objects.filter(
        province_id=province_id, is_active=True, province__is_active=True
    ).values("id", "name").order_by("name") if province_id and province_id.isdigit() else []
    return JsonResponse({"cities": list(results)})


def confirmation(request, number):
    order = get_object_or_404(Order.objects.prefetch_related("items"), number=number)
    allowed = request.session.get("last_order") == number or request.user.is_authenticated and order.user_id == request.user.id
    if not allowed:
        return redirect("orders:track")
    return render(request, "orders/confirmation.html", {"order": order})


@rate_limit("tracking", limit=12, period=300)
def track(request):
    form = TrackingForm(request.POST or None)
    order = None
    if request.method == "POST" and form.is_valid():
        contact = form.cleaned_data["contact"].strip()
        order = (
            Order.objects.prefetch_related("tracking_events")
            .filter(number=form.cleaned_data["order_number"])
            .filter(Q(email__iexact=contact) | Q(phone=contact))
            .first()
        )
        if not order:
            form.add_error(None, "We could not match that order and contact detail.")
    return render(request, "orders/tracking.html", {"form": form, "order": order})


def invoice(request, number):
    order = get_object_or_404(Order.objects.prefetch_related("items"), number=number)
    allowed = request.user.is_staff or request.session.get("last_order") == number or order.user_id == getattr(request.user, "id", None)
    if not allowed:
        return redirect("orders:track")
    return render(request, "orders/invoice.html", {"order": order})


def packing_slip(request, number):
    order = get_object_or_404(Order.objects.prefetch_related("items"), number=number)
    if not request.user.is_staff:
        return redirect("orders:track")
    return render(request, "orders/invoice.html", {"order": order, "packing_slip": True})
