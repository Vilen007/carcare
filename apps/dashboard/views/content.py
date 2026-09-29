from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.content.models import HeroSlide, Page, SiteSettings
from apps.dashboard.decorators import staff_required
from apps.dashboard.forms import HeroSlideForm, PageForm, SiteSettingsForm


@staff_required
def content_home(request):
    settings_obj = SiteSettings.objects.first() or SiteSettings()
    return render(request, "dashboard/content/home.html", {
        "settings_obj": settings_obj,
        "heroes": HeroSlide.objects.all(),
        "pages": Page.objects.all(),
    })


@staff_required
def site_settings_edit(request):
    settings_obj = SiteSettings.objects.first() or SiteSettings()
    form = SiteSettingsForm(request.POST or None, instance=settings_obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Store settings saved.")
        return redirect("dashboard:content")
    return render(request, "dashboard/content/settings_form.html", {"form": form})


@staff_required
def hero_edit(request, pk=None):
    hero = get_object_or_404(HeroSlide, pk=pk) if pk else None
    form = HeroSlideForm(request.POST or None, request.FILES or None, instance=hero)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Hero slide saved.")
        return redirect("dashboard:content")
    return render(request, "dashboard/content/hero_form.html", {"form": form, "hero": hero})


@staff_required
@require_POST
def hero_delete(request, pk):
    get_object_or_404(HeroSlide, pk=pk).delete()
    messages.success(request, "Hero slide deleted.")
    return redirect("dashboard:content")


@staff_required
def page_edit(request, pk=None):
    page = get_object_or_404(Page, pk=pk) if pk else None
    form = PageForm(request.POST or None, instance=page)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Page saved.")
        return redirect("dashboard:content")
    return render(request, "dashboard/content/page_form.html", {"form": form, "page": page})


@staff_required
@require_POST
def page_delete(request, pk):
    get_object_or_404(Page, pk=pk).delete()
    messages.success(request, "Page deleted.")
    return redirect("dashboard:content")
