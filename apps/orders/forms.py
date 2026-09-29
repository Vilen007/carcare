from django import forms

from .models import City, Order, Province


class CheckoutForm(forms.ModelForm):
    coupon_code = forms.CharField(required=False, max_length=30, label="Coupon code")
    delivery_province = forms.ModelChoiceField(
        label="Province",
        queryset=Province.objects.filter(is_active=True),
        empty_label="Select province",
    )
    delivery_city = forms.ModelChoiceField(
        label="City",
        queryset=City.objects.none(),
        empty_label="Select city",
    )
    save_address = forms.BooleanField(required=False, initial=True)

    class Meta:
        model = Order
        fields = (
            "email", "phone", "full_name", "address_line_1", "address_line_2",
            "delivery_province", "delivery_city", "postal_code", "coupon_code", "customer_note",
        )
        widgets = {"customer_note": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        province_id = self.data.get("delivery_province") or self.initial.get("delivery_province")
        if isinstance(province_id, Province):
            province_id = province_id.pk
        if self.is_bound:
            self.fields["delivery_city"].queryset = City.objects.filter(is_active=True, province__is_active=True)
        elif province_id:
            self.fields["delivery_city"].queryset = City.objects.filter(
                province_id=province_id, is_active=True, province__is_active=True
            )

    def clean(self):
        cleaned = super().clean()
        province = cleaned.get("delivery_province")
        city = cleaned.get("delivery_city")
        if province and city and city.province_id != province.id:
            self.add_error("delivery_city", "Select a city within the chosen province.")
        return cleaned

    def clean_coupon_code(self):
        return self.cleaned_data.get("coupon_code", "").strip().upper()


class TrackingForm(forms.Form):
    order_number = forms.CharField(max_length=20)
    contact = forms.CharField(max_length=254, help_text="Email address or phone used at checkout")

    def clean_order_number(self):
        return self.cleaned_data["order_number"].strip().upper()
