# app/apps/accounts/forms.py

from django import forms

from app.apps.billing.models import Plan


class ChangePlanActionForm(forms.Form):
    """Form used by the admin bulk 'change plan' action to pick the target plan."""

    plan = forms.ModelChoiceField(
        queryset=Plan.objects.filter(is_active=True).exclude(name=Plan.NAME.FREE),
        label="New plan",
    )
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
