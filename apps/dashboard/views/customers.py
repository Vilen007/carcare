from django.db.models import Q
from django.shortcuts import render

from apps.customers.models import Address
from apps.dashboard.decorators import staff_required
from apps.dashboard.pagination import paginate


@staff_required
def customer_list(request):
    addresses = Address.objects.select_related("user")
    query = request.GET.get("q", "").strip()
    if query:
        addresses = addresses.filter(
            Q(full_name__icontains=query) | Q(phone__icontains=query) | Q(user__email__icontains=query) | Q(city__icontains=query)
        )
    page = paginate(addresses, request)
    querystring = f"q={query}&" if query else ""
    return render(request, "dashboard/customers/list.html", {
        "page_obj": page,
        "query": query,
        "querystring": querystring,
    })
