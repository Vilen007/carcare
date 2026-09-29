from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.catalog.models import Category, Product
from apps.dashboard.decorators import staff_required
from apps.dashboard.forms import CategoryForm, ProductForm, ProductImageFormSet, ProductVariantFormSet
from apps.dashboard.pagination import paginate


@staff_required
def category_list(request):
    page = paginate(Category.objects.select_related("parent").all(), request)
    return render(request, "dashboard/catalog/categories.html", {
        "page_obj": page,
        "querystring": "",
    })


@staff_required
def category_edit(request, pk=None):
    category = get_object_or_404(Category, pk=pk) if pk else None
    form = CategoryForm(request.POST or None, request.FILES or None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Category saved.")
        return redirect("dashboard:categories")
    return render(request, "dashboard/catalog/category_form.html", {"form": form, "category": category})


@staff_required
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if category.products.exists():
        messages.error(request, "Move or delete products in this category first.")
    else:
        category.delete()
        messages.success(request, "Category deleted.")
    return redirect("dashboard:categories")


@staff_required
def product_list(request):
    products = Product.objects.select_related("category").all()
    status = request.GET.get("status", "")
    query = request.GET.get("q", "").strip()
    if status:
        products = products.filter(status=status)
    if query:
        products = products.filter(Q(name__icontains=query) | Q(sku__icontains=query))
    page = paginate(products, request)
    querystring = ""
    if status:
        querystring += f"status={status}&"
    if query:
        querystring += f"q={query}&"
    return render(request, "dashboard/catalog/products.html", {
        "page_obj": page, "status": status, "query": query, "querystring": querystring,
        "status_choices": Product.Status.choices,
    })


@staff_required
def product_edit(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    form = ProductForm(request.POST or None, instance=product)
    image_formset = ProductImageFormSet(request.POST or None, request.FILES or None, instance=product)
    variant_formset = ProductVariantFormSet(request.POST or None, instance=product)
    if request.method == "POST" and form.is_valid() and image_formset.is_valid() and variant_formset.is_valid():
        product = form.save()
        image_formset.instance = product
        variant_formset.instance = product
        image_formset.save()
        variant_formset.save()
        messages.success(request, f"{product.name} saved.")
        return redirect("dashboard:product_edit", pk=product.pk)
    return render(request, "dashboard/catalog/product_form.html", {
        "form": form, "product": product, "image_formset": image_formset, "variant_formset": variant_formset,
    })


@staff_required
@require_POST
def product_activate(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.status = Product.Status.ACTIVE
    product.save(update_fields=["status", "updated_at"])
    messages.success(request, f"{product.name} is now active.")
    return redirect("dashboard:products")


@staff_required
@require_POST
def product_archive(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.status = Product.Status.ARCHIVED
    product.save(update_fields=["status", "updated_at"])
    messages.success(request, f"{product.name} archived.")
    return redirect("dashboard:products")


@staff_required
@require_POST
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if product.bundle_items.exists():
        messages.error(request, "Remove this product from all bundles before deleting.")
        return redirect("dashboard:product_edit", pk=pk)
    name = product.name
    product.delete()
    messages.success(request, f"{name} deleted.")
    return redirect("dashboard:products")
