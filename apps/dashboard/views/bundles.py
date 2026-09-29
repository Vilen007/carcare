from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.catalog.models import Bundle
from apps.dashboard.decorators import staff_required
from apps.dashboard.forms import BundleForm, BundleItemFormSet


@staff_required
def bundle_list(request):
    return render(request, "dashboard/bundles/list.html", {
        "bundles": Bundle.objects.prefetch_related("items__product", "eligible_categories"),
    })


@staff_required
def bundle_edit(request, pk=None):
    bundle = get_object_or_404(Bundle, pk=pk) if pk else None
    form = BundleForm(request.POST or None, request.FILES or None, instance=bundle)
    item_formset = BundleItemFormSet(request.POST or None, instance=bundle)
    if request.method == "POST" and form.is_valid() and item_formset.is_valid():
        bundle = form.save()
        item_formset.instance = bundle
        item_formset.save()
        messages.success(request, f"{bundle.name} saved.")
        return redirect("dashboard:bundle_edit", pk=bundle.pk)
    return render(request, "dashboard/bundles/form.html", {
        "form": form, "bundle": bundle, "item_formset": item_formset,
    })


@staff_required
@require_POST
def bundle_delete(request, pk):
    bundle = get_object_or_404(Bundle, pk=pk)
    bundle.delete()
    messages.success(request, "Bundle deleted.")
    return redirect("dashboard:bundles")
