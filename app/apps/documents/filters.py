# apps/documents/filters.py
from django_filters import rest_framework as django_filters

from app.apps.documents.models import Document


class DocumentFilter(django_filters.FilterSet):
    # Фильтр "с какой даты" (Greater than or equal)
    expiration_date_from = django_filters.DateFilter(
        field_name="expiration_date", lookup_expr="gte"
    )
    # Фильтр "по какую дату" (Less than or equal)
    expiration_date_to = django_filters.DateFilter(
        field_name="expiration_date", lookup_expr="lte"
    )

    class Meta:
        model = Document
        fields = ["expiration_date_from", "expiration_date_to"]
