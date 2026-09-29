from django import forms

from .models import Review


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ("name", "email", "rating", "title", "body")
        widgets = {
            "rating": forms.Select(choices=[(value, f"{value} star{'s' if value != 1 else ''}") for value in range(5, 0, -1)]),
            "body": forms.Textarea(attrs={"rows": 4}),
        }
