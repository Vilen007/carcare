from .auth import login_view, logout_view
from .bundles import bundle_delete, bundle_edit, bundle_list
from .catalog import (
    category_delete,
    category_edit,
    category_list,
    product_activate,
    product_archive,
    product_delete,
    product_edit,
    product_list,
)
from .content import (
    content_home,
    hero_delete,
    hero_edit,
    page_delete,
    page_edit,
    site_settings_edit,
)
from .customers import customer_list
from .inbox import (
    contact_resolve,
    inbox_home,
    newsletter_export_csv,
    subscriber_toggle,
)
from .inventory import inventory_adjust, inventory_export_csv, inventory_home
from .orders import (
    order_add_tracking,
    order_bulk_confirm,
    order_detail,
    order_export_csv,
    order_list,
    order_update_shipment,
    order_update_status,
)
from .overview import overview
from .promotions import (
    coupon_delete,
    coupon_edit,
    promotion_home,
    sale_delete,
    sale_edit,
)
from .reviews import review_approve, review_list, review_reject
from .shipping import (
    city_delete,
    city_edit,
    province_delete,
    province_edit,
    shipping_home,
)
