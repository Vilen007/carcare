import csv

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.content.models import ContactMessage, NewsletterSubscriber
from apps.dashboard.decorators import staff_required
from apps.dashboard.pagination import paginate


@staff_required
def inbox_home(request):
    contacts = ContactMessage.objects.all().order_by("-created_at")
    queue = request.GET.get("queue", "open")
    if queue == "open":
        contacts = contacts.filter(is_resolved=False)
    elif queue == "resolved":
        contacts = contacts.filter(is_resolved=True)
    page = paginate(contacts, request)
    subscribers = paginate(
        NewsletterSubscriber.objects.all().order_by("-created_at"),
        request,
        page_param="sub_page",
    )
    return render(request, "dashboard/inbox/home.html", {
        "page_obj": page,
        "queue": queue,
        "querystring": f"queue={queue}&",
        "subscribers": subscribers,
        "subscriber_count": NewsletterSubscriber.objects.count(),
    })


@staff_required
@require_POST
def contact_resolve(request, pk):
    contact = get_object_or_404(ContactMessage, pk=pk)
    contact.is_resolved = True
    contact.save(update_fields=["is_resolved", "updated_at"])
    messages.success(request, "Message marked resolved.")
    return redirect("dashboard:inbox")


@staff_required
@require_POST
def subscriber_toggle(request, pk):
    subscriber = get_object_or_404(NewsletterSubscriber, pk=pk)
    subscriber.is_active = not subscriber.is_active
    subscriber.save(update_fields=["is_active", "updated_at"])
    messages.success(request, f"{subscriber.email} is now {'active' if subscriber.is_active else 'inactive'}.")
    return redirect("dashboard:inbox")


@staff_required
def newsletter_export_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="carcare-newsletter.csv"'
    writer = csv.writer(response)
    writer.writerow(["Email", "Active", "Joined"])
    for row in NewsletterSubscriber.objects.all():
        writer.writerow([row.email, row.is_active, row.created_at])
    return response
