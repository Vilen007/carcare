from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.dashboard.decorators import staff_required
from apps.dashboard.pagination import paginate
from apps.reviews.models import Review


@staff_required
def review_list(request):
    reviews = Review.objects.select_related("product")
    queue = request.GET.get("queue", "pending")
    if queue == "pending":
        reviews = reviews.filter(is_approved=False)
    elif queue == "approved":
        reviews = reviews.filter(is_approved=True)
    page = paginate(reviews, request)
    querystring = f"queue={queue}&"
    return render(request, "dashboard/reviews/list.html", {
        "page_obj": page,
        "queue": queue,
        "querystring": querystring,
    })


@staff_required
@require_POST
def review_approve(request, pk):
    review = get_object_or_404(Review, pk=pk)
    review.is_approved = True
    review.save(update_fields=["is_approved", "updated_at"])
    messages.success(request, "Review approved.")
    return redirect(request.POST.get("next") or "dashboard:reviews")


@staff_required
@require_POST
def review_reject(request, pk):
    review = get_object_or_404(Review, pk=pk)
    review.delete()
    messages.success(request, "Review removed.")
    return redirect(request.POST.get("next") or "dashboard:reviews")
