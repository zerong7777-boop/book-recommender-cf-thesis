from django import forms


class RatingForm(forms.Form):
    score = forms.IntegerField(
        min_value=1,
        max_value=5,
        widget=forms.NumberInput(attrs={"min": 1, "max": 5, "step": 1}),
    )
