from dataclasses import dataclass
from decimal import Decimal
from functools import cached_property

from django.db.models import Prefetch

from apps.catalog.models import Bundle, Product, with_sale_pricing

from .models import Coupon


@dataclass
class CartLine:
    key: str
    item_type: str
    item: object
    quantity: int
    unit_price: Decimal
    configuration: dict

    @property
    def total(self):
        return self.unit_price * self.quantity


class Cart:
    SESSION_KEY = "cart"
    COUPON_SESSION_KEY = "coupon_code"

    def __init__(self, request):
        self.session = request.session
        self.data = self.session.get(self.SESSION_KEY, {})

    def add_product(self, product_id, quantity=1, replace=False):
        key = f"product:{product_id}"
        current = self.data.get(key, {"quantity": 0})
        current["quantity"] = quantity if replace else current["quantity"] + quantity
        self.data[key] = {"type": "product", "id": int(product_id), "quantity": max(1, int(current["quantity"]))}
        self.save()

    def product_quantity(self, product_id):
        """Units of this product already in the cart (direct product lines only)."""
        key = f"product:{product_id}"
        raw = self.data.get(key)
        return int(raw["quantity"]) if raw and raw.get("type") == "product" else 0

    def available_to_add(self, product, *, ignore_cart=False):
        """How many more units of this product can be added given live stock."""
        if not product.track_inventory:
            return 99
        already = 0 if ignore_cart else self.product_quantity(product.id)
        return max(0, int(product.stock) - already)

    def add_bundle(self, bundle_id, quantity=1, product_ids=None):
        suffix = "-" + "-".join(map(str, sorted(product_ids or []))) if product_ids else ""
        key = f"bundle:{bundle_id}{suffix}"
        self.data[key] = {
            "type": "bundle",
            "id": int(bundle_id),
            "quantity": max(1, int(quantity)),
            "product_ids": [int(value) for value in (product_ids or [])],
        }
        self.save()

    def update(self, key, quantity):
        if key in self.data:
            if int(quantity) <= 0:
                self.data.pop(key)
            else:
                self.data[key]["quantity"] = min(int(quantity), 99)
            self.save()

    def remove(self, key):
        self.data.pop(key, None)
        self.save()

    def clear(self):
        self.data = {}
        self.session.pop(self.COUPON_SESSION_KEY, None)
        self.save()

    def save(self):
        self.session[self.SESSION_KEY] = self.data
        self.session.modified = True

    def lines(self):
        if hasattr(self, "_lines_cache"):
            return self._lines_cache
        product_ids = [line["id"] for line in self.data.values() if line["type"] == "product"]
        bundle_ids = [line["id"] for line in self.data.values() if line["type"] == "bundle"]
        products = with_sale_pricing(
            Product.objects.filter(id__in=product_ids, status=Product.Status.ACTIVE)
        ).in_bulk()
        bundles = Bundle.objects.filter(id__in=bundle_ids, is_active=True).prefetch_related(
            Prefetch("items__product", queryset=with_sale_pricing(Product.objects.all()))
        ).in_bulk()
        lines = []
        for key, raw in self.data.items():
            item = products.get(raw["id"]) if raw["type"] == "product" else bundles.get(raw["id"])
            if not item:
                continue
            unit_price = item.current_price if raw["type"] == "product" else item.price
            configuration = {}
            if raw["type"] == "bundle" and raw.get("product_ids"):
                selected = list(with_sale_pricing(
                    Product.objects.filter(id__in=raw["product_ids"], status=Product.Status.ACTIVE)
                ))
                if not (item.minimum_items <= len(selected) <= item.maximum_items):
                    continue
                original = sum((product.current_price for product in selected), Decimal("0"))
                unit_price = (original * (Decimal("100") - item.discount_percent) / Decimal("100")).quantize(Decimal("0.01"))
                configuration = {"products": [{"id": p.id, "name": p.name, "sku": p.sku} for p in selected]}
            lines.append(CartLine(key, raw["type"], item, raw["quantity"], unit_price, configuration))
        self._lines_cache = lines
        return lines

    @cached_property
    def subtotal(self):
        return sum((line.total for line in self.lines()), Decimal("0"))

    @cached_property
    def count(self):
        return sum(line.quantity for line in self.lines())

    def apply_coupon(self, code):
        coupon = Coupon.objects.filter(code__iexact=code.strip()).first()
        if not coupon:
            return False, "That coupon code does not exist."
        if not coupon.is_valid(self.subtotal):
            return False, "That coupon is expired, unavailable, or requires a higher subtotal."
        self.session[self.COUPON_SESSION_KEY] = coupon.code
        self.session.modified = True
        return True, f"Coupon {coupon.code} applied successfully."

    def remove_coupon(self):
        self.session.pop(self.COUPON_SESSION_KEY, None)
        self.session.modified = True

    @cached_property
    def coupon(self):
        code = self.session.get(self.COUPON_SESSION_KEY)
        if not code:
            return None
        coupon = Coupon.objects.filter(code__iexact=code).first()
        return coupon if coupon and coupon.is_valid(self.subtotal) else None

    @cached_property
    def discount(self):
        coupon = self.coupon
        if not coupon:
            return Decimal("0")
        return (self.subtotal * coupon.discount_percent / Decimal("100")).quantize(Decimal("0.01"))

    @cached_property
    def total(self):
        return self.subtotal - self.discount
