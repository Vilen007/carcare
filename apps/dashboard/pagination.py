from django.core.paginator import Paginator

# Default page size for all dashboard data tables.
TABLE_PAGE_SIZE = 100


def paginate(queryset, request, *, page_param="page", per_page=TABLE_PAGE_SIZE):
    return Paginator(queryset, per_page).get_page(request.GET.get(page_param))
