from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.dashboard.decorators import staff_required
from apps.dashboard.forms import CityForm, ProvinceForm
from apps.dashboard.pagination import paginate
from apps.orders.models import City, Province


@staff_required
def shipping_home(request):
    provinces = paginate(Province.objects.prefetch_related("cities"), request, page_param="prov_page")
    cities = paginate(City.objects.select_related("province"), request, page_param="city_page")
    return render(request, "dashboard/shipping/home.html", {
        "provinces": provinces,
        "cities": cities,
    })


@staff_required
def province_edit(request, pk=None):
    province = get_object_or_404(Province, pk=pk) if pk else None
    form = ProvinceForm(request.POST or None, instance=province)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Province saved.")
        return redirect("dashboard:shipping")
    return render(request, "dashboard/shipping/province_form.html", {"form": form, "province": province})


@staff_required
@require_POST
def province_delete(request, pk):
    get_object_or_404(Province, pk=pk).delete()
    messages.success(request, "Province deleted.")
    return redirect("dashboard:shipping")


@staff_required
def city_edit(request, pk=None):
    city = get_object_or_404(City, pk=pk) if pk else None
    form = CityForm(request.POST or None, instance=city)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "City saved.")
        return redirect("dashboard:shipping")
    return render(request, "dashboard/shipping/city_form.html", {"form": form, "city": city})


@staff_required
@require_POST
def city_delete(request, pk):
    get_object_or_404(City, pk=pk).delete()
    messages.success(request, "City deleted.")
    return redirect("dashboard:shipping")
