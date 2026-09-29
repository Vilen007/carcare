import csv

from django.contrib import messages
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.catalog.models import InventoryAdjustment, Product
from apps.dashboard.decorators import staff_required
from apps.dashboard.forms import InventoryAdjustmentForm
from apps.dashboard.pagination import paginate
from apps.dashboard.services import apply_inventory_adjustment


@staff_required
def inventory_home(request):
    low_stock_qs = Product.objects.filter(
        track_inventory=True, stock__lte=F("low_stock_threshold")
    ).exclude(status=Product.Status.ARCHIVED).select_related("category")
    history_qs = InventoryAdjustment.objects.select_related("product", "created_by")
    low_stock = paginate(low_stock_qs, request, page_param="low_page")
    history = paginate(history_qs, request, page_param="hist_page")
    initial = {}
    product_id = request.GET.get("product")
    if product_id:
        initial["product"] = product_id
        initial["quantity"] = 10
        initial["reason"] = InventoryAdjustment.Reason.PURCHASE
    form = InventoryAdjustmentForm(initial=initial)
    return render(request, "dashboard/inventory/home.html", {
        "low_stock": low_stock,
        "history": history,
        "form": form,
    })


@staff_required
@require_POST
def inventory_adjust(request):
    form = InventoryAdjustmentForm(request.POST)
    if form.is_valid():
        try:
            apply_inventory_adjustment(
                product=form.cleaned_data["product"],
                quantity=form.cleaned_data["signed_quantity"],
                reason=form.cleaned_data["reason"],
                reference=form.cleaned_data.get("reference", ""),
                note=form.cleaned_data.get("note", ""),
                user=request.user,
            )
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("dashboard:inventory")
        delta = form.cleaned_data["signed_quantity"]
        messages.success(
            request,
            f"Stock {'increased' if delta > 0 else 'decreased'} by {abs(delta)}.",
        )
    else:
        messages.error(request, "Could not adjust inventory. Check the form.")
    return redirect("dashboard:inventory")


@staff_required
def inventory_export_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="carcare-inventory.csv"'
    writer = csv.writer(response)
    writer.writerow(["SKU", "Product", "Category", "Price", "Stock", "Low-stock threshold", "Status"])
    for product in Product.objects.select_related("category"):
        writer.writerow([
            product.sku, product.name, product.category.name, product.price,
            product.stock, product.low_stock_threshold, product.status,
        ])
    return response
