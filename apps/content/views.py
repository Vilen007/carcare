from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ContactForm, NewsletterForm
from .models import NewsletterSubscriber, Page


def page(request, slug):
    return render(request, "content/page.html", {"page": get_object_or_404(Page, slug=slug, is_published=True)})


def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Message received. Our team will get back to you shortly.")
        return redirect("content:contact")
    return render(request, "content/contact.html", {"form": form})


@require_POST
def newsletter(request):
    email = request.POST.get("email", "").strip().lower()
    form = NewsletterForm({"email": email})
    if email and NewsletterSubscriber.objects.filter(email__iexact=email).exists():
        messages.info(request, "You are already subscribed to Carcare updates.")
    elif form.is_valid():
        try:
            with transaction.atomic():
                form.save()
        except IntegrityError:
            messages.info(request, "You are already subscribed to Carcare updates.")
        else:
            messages.success(request, "Thanks for subscribing! Premium care tips and offers are now headed your way.")
    else:
        messages.error(request, "Please enter a valid email address to subscribe.")
    return redirect(request.POST.get("next") or "core:home")
