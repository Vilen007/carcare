from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.forms import inlineformset_factory
from django.utils.text import slugify

from apps.cart.models import Coupon, SaleCampaign
from apps.catalog.models import Bundle, BundleItem, Category, InventoryAdjustment, Product, ProductImage, ProductVariant
from apps.content.models import ContactMessage, HeroSlide, NewsletterSubscriber, Page, SiteSettings
from apps.customers.models import Address
from apps.orders.models import City, Order, Province, TrackingEvent


class StaffLoginForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise forms.ValidationError("Staff access is required for the operations dashboard.", code="no_staff")


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = (
            "name", "slug", "parent", "description", "image", "sort_order",
            "is_active", "show_in_navigation", "meta_title", "meta_description",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False

    def clean_slug(self):
        slug = self.cleaned_data.get("slug") or slugify(self.cleaned_data.get("name", ""))
        return slug


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            "category", "name", "slug", "sku", "short_description", "description", "usage",
            "price", "compare_at_price", "cost_price", "stock", "low_stock_threshold",
            "track_inventory", "status", "is_featured", "is_new", "weight_grams",
            "meta_title", "meta_description",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "usage": forms.Textarea(attrs={"rows": 3}),
            "short_description": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False

    def clean_slug(self):
        return self.cleaned_data.get("slug") or slugify(self.cleaned_data.get("name", ""))


ProductImageFormSet = inlineformset_factory(
    Product, ProductImage, fields=("image", "alt_text", "sort_order", "is_primary"), extra=1, can_delete=True
)
ProductVariantFormSet = inlineformset_factory(
    Product, ProductVariant, fields=("name", "sku", "price", "stock", "is_active"), extra=0, can_delete=True
)


class BundleForm(forms.ModelForm):
    class Meta:
        model = Bundle
        fields = (
            "name", "slug", "description", "image", "discount_percent", "is_active",
            "is_custom_builder", "minimum_items", "maximum_items", "eligible_categories",
        )
        widgets = {"description": forms.Textarea(attrs={"rows": 4}), "eligible_categories": forms.CheckboxSelectMultiple}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False

    def clean_slug(self):
        return self.cleaned_data.get("slug") or slugify(self.cleaned_data.get("name", ""))


BundleItemFormSet = inlineformset_factory(
    Bundle, BundleItem, fields=("product", "quantity"), extra=1, can_delete=True
)


class InventoryAdjustmentForm(forms.ModelForm):
    quantity = forms.IntegerField(
        min_value=1,
        label="Units",
        help_text="Always enter a positive number. Direction is set by the reason.",
    )
    reason = forms.ChoiceField(
        choices=(
            (InventoryAdjustment.Reason.PURCHASE, "Purchase from supplier — adds stock"),
            (InventoryAdjustment.Reason.RETURN, "Customer return — adds stock"),
            (InventoryAdjustment.Reason.DAMAGE, "Damage / write-off — removes stock"),
            (InventoryAdjustment.Reason.CORRECTION, "Count correction — choose add or remove below"),
        ),
        label="Reason",
    )
    direction = forms.ChoiceField(
        choices=(
            ("add", "Add stock"),
            ("remove", "Remove stock"),
        ),
        required=False,
        initial="add",
        label="Correction direction",
        help_text="Only used when reason is Count correction.",
    )

    class Meta:
        model = InventoryAdjustment
        fields = ("product", "quantity", "reason", "reference", "note")

    def clean(self):
        cleaned = super().clean()
        reason = cleaned.get("reason")
        quantity = cleaned.get("quantity") or 0
        direction = cleaned.get("direction") or self.data.get("direction") or "add"
        cleaned["direction"] = direction
        if reason == InventoryAdjustment.Reason.CORRECTION and direction not in ("add", "remove"):
            self.add_error("direction", "Choose whether this correction adds or removes stock.")
        cleaned["signed_quantity"] = self._signed_quantity(reason, quantity, direction)
        return cleaned

    @staticmethod
    def _signed_quantity(reason, quantity, direction="add"):
        units = abs(int(quantity))
        if reason in (InventoryAdjustment.Reason.PURCHASE, InventoryAdjustment.Reason.RETURN):
            return units
        if reason in (InventoryAdjustment.Reason.DAMAGE, InventoryAdjustment.Reason.ORDER):
            return -units
        if reason == InventoryAdjustment.Reason.CORRECTION:
            return units if direction == "add" else -units
        return units


class SaleCampaignForm(forms.ModelForm):
    class Meta:
        model = SaleCampaign
        fields = (
            "name", "discount_percent", "starts_at", "ends_at", "applies_to_all",
            "categories", "banner_text", "is_active",
        )
        widgets = {
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "categories": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["starts_at"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
        self.fields["ends_at"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]


class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = (
            "code", "discount_percent", "minimum_subtotal", "starts_at", "ends_at",
            "usage_limit", "is_active",
        )
        widgets = {
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["starts_at"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
        self.fields["ends_at"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]


class ProvinceForm(forms.ModelForm):
    class Meta:
        model = Province
        fields = ("name", "shipping_fee", "cod_fee", "free_shipping_threshold", "estimated_days", "is_active")


class CityForm(forms.ModelForm):
    class Meta:
        model = City
        fields = ("province", "name", "is_active")


class OrderStatusForm(forms.Form):
    status = forms.ChoiceField(choices=Order.Status.choices)
    admin_note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    payment_status = forms.CharField(required=False, max_length=20)


class ShipmentForm(forms.Form):
    courier = forms.CharField(required=False, max_length=100)
    tracking_number = forms.CharField(required=False, max_length=100)
    shipped_at = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"))
    delivered_at = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["shipped_at"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
        self.fields["delivered_at"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]


class TrackingEventForm(forms.ModelForm):
    class Meta:
        model = TrackingEvent
        fields = ("status", "title", "description", "location")


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = (
            "store_name", "announcement", "support_phone", "support_email",
            "whatsapp_number", "instagram_url", "facebook_url", "tiktok_url", "address",
        )


class HeroSlideForm(forms.ModelForm):
    class Meta:
        model = HeroSlide
        fields = ("eyebrow", "title", "subtitle", "image", "cta_label", "cta_url", "sort_order", "is_active")
        widgets = {"subtitle": forms.Textarea(attrs={"rows": 2})}


class PageForm(forms.ModelForm):
    class Meta:
        model = Page
        fields = ("title", "slug", "body", "meta_description", "is_published")
        widgets = {"body": forms.Textarea(attrs={"rows": 12})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False

    def clean_slug(self):
        return self.cleaned_data.get("slug") or slugify(self.cleaned_data.get("title", ""))
