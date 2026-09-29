import csv

from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.dashboard.decorators import staff_required
from apps.dashboard.forms import OrderStatusForm, ShipmentForm, TrackingEventForm
from apps.dashboard.pagination import paginate
from apps.dashboard.services import confirm_orders, set_order_status, upsert_shipment
from apps.orders.models import Order


@staff_required
def order_list(request):
    orders = Order.objects.prefetch_related("items").all()
    status = request.GET.get("status", "")
    query = request.GET.get("q", "").strip()
    if status:
        orders = orders.filter(status=status)
    if query:
        orders = orders.filter(
            Q(number__icontains=query) | Q(full_name__icontains=query) | Q(email__icontains=query) | Q(phone__icontains=query)
        )
    page = paginate(orders, request)
    querystring = ""
    if status:
        querystring += f"status={status}&"
    if query:
        querystring += f"q={query}&"
    return render(request, "dashboard/orders/list.html", {
        "page_obj": page,
        "status": status,
        "query": query,
        "querystring": querystring,
        "status_choices": Order.Status.choices,
    })


@staff_required
def order_detail(request, number):
    order = get_object_or_404(
        Order.objects.prefetch_related("items", "tracking_events").select_related("delivery_province", "delivery_city"),
        number=number,
    )
    shipment = getattr(order, "shipment", None)
    status_form = OrderStatusForm(initial={"status": order.status, "admin_note": order.admin_note, "payment_status": order.payment_status})
    shipment_form = ShipmentForm(initial={
        "courier": shipment.courier if shipment else "",
        "tracking_number": shipment.tracking_number if shipment else "",
        "shipped_at": shipment.shipped_at.strftime("%Y-%m-%dT%H:%M") if shipment and shipment.shipped_at else "",
        "delivered_at": shipment.delivered_at.strftime("%Y-%m-%dT%H:%M") if shipment and shipment.delivered_at else "",
    })
    tracking_form = TrackingEventForm(initial={"status": order.status})
    pipeline = [
        (Order.Status.PENDING, "Pending"),
        (Order.Status.CONFIRMED, "Confirmed"),
        (Order.Status.PACKING, "Packing"),
        (Order.Status.SHIPPED, "Shipped"),
        (Order.Status.DELIVERED, "Delivered"),
    ]
    order_rank = {value: idx for idx, (value, _) in enumerate(pipeline)}
    current_rank = order_rank.get(order.status, -1)
    reached = {value for value, idx in order_rank.items() if idx < current_rank}
    return render(request, "dashboard/orders/detail.html", {
        "order": order,
        "shipment": shipment,
        "status_form": status_form,
        "shipment_form": shipment_form,
        "tracking_form": tracking_form,
        "pipeline": pipeline,
        "reached": reached,
    })


@staff_required
@require_POST
def order_update_status(request, number):
    order = get_object_or_404(Order, number=number)
    form = OrderStatusForm(request.POST)
    if form.is_valid():
        note = form.cleaned_data["admin_note"]
        payment = form.cleaned_data["payment_status"] or order.payment_status
        new_status = form.cleaned_data["status"]
        if note != order.admin_note or payment != order.payment_status:
            order.admin_note = note
            order.payment_status = payment
            order.save(update_fields=["admin_note", "payment_status", "updated_at"])
        if new_status != order.status:
            set_order_status(order, new_status)
            messages.success(request, f"Order {order.number} is now {order.get_status_display()}.")
        else:
            messages.success(request, f"Order {order.number} saved.")
    else:
        messages.error(request, "Could not update order status.")
    return redirect("dashboard:order_detail", number=number)


@staff_required
@require_POST
def order_update_shipment(request, number):
    order = get_object_or_404(Order, number=number)
    form = ShipmentForm(request.POST)
    if form.is_valid():
        upsert_shipment(order, **form.cleaned_data)
        messages.success(request, "Shipment details saved.")
    else:
        messages.error(request, "Check shipment fields and try again.")
    return redirect("dashboard:order_detail", number=number)


@staff_required
@require_POST
def order_add_tracking(request, number):
    order = get_object_or_404(Order, number=number)
    form = TrackingEventForm(request.POST)
    if form.is_valid():
        event = form.save(commit=False)
        event.order = order
        event.save()
        messages.success(request, "Tracking event added.")
    else:
        messages.error(request, "Tracking event is incomplete.")
    return redirect("dashboard:order_detail", number=number)


@staff_required
@require_POST
def order_bulk_confirm(request):
    ids = request.POST.getlist("order_ids")
    count = confirm_orders(Order.objects.filter(pk__in=ids))
    messages.success(request, f"Confirmed {count} order{'s' if count != 1 else ''}.")
    return redirect("dashboard:orders")


@staff_required
def order_export_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="carcare-orders.csv"'
    writer = csv.writer(response)
    writer.writerow(["Order", "Date", "Customer", "Phone", "City", "Status", "Total"])
    for order in Order.objects.all():
        writer.writerow([order.number, order.created_at, order.full_name, order.phone, order.city, order.status, order.total])
    return response
