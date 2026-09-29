from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.cart.models import Coupon, SaleCampaign
from apps.dashboard.decorators import staff_required
from apps.dashboard.forms import CouponForm, SaleCampaignForm


@staff_required
def promotion_home(request):
    return render(request, "dashboard/promotions/home.html", {
        "campaigns": SaleCampaign.objects.prefetch_related("categories"),
        "coupons": Coupon.objects.all(),
    })


@staff_required
def sale_edit(request, pk=None):
    campaign = get_object_or_404(SaleCampaign, pk=pk) if pk else None
    form = SaleCampaignForm(request.POST or None, instance=campaign)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Sale campaign saved.")
        return redirect("dashboard:promotions")
    return render(request, "dashboard/promotions/sale_form.html", {"form": form, "campaign": campaign})


@staff_required
@require_POST
def sale_delete(request, pk):
    get_object_or_404(SaleCampaign, pk=pk).delete()
    messages.success(request, "Sale campaign deleted.")
    return redirect("dashboard:promotions")


@staff_required
def coupon_edit(request, pk=None):
    coupon = get_object_or_404(Coupon, pk=pk) if pk else None
    form = CouponForm(request.POST or None, instance=coupon)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Coupon saved.")
        return redirect("dashboard:promotions")
    return render(request, "dashboard/promotions/coupon_form.html", {"form": form, "coupon": coupon})


@staff_required
@require_POST
def coupon_delete(request, pk):
    get_object_or_404(Coupon, pk=pk).delete()
    messages.success(request, "Coupon deleted.")
    return redirect("dashboard:promotions")
