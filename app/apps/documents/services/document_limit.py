# app/apps/documents/services/document_limit.py
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from app.apps.documents.models import Document


def get_active_document_count(user) -> int:
    """Number of ACTIVE documents (folders) owned by the user."""
    return Document.objects.filter(user=user, status=Document.STATUS.ACTIVE).count()


def check_document_limit(user, document_type) -> None:
    """
    Raise ValidationError if uploading a document of the given type would
    exceed the user's plan document limit.

    Replacing an existing ACTIVE document of the same type is always allowed
    (the ACTIVE count doesn't increase — old version becomes REPLACED).
    """
    try:
        plan = user.subscription.plan
    except ObjectDoesNotExist:
        plan = None

    limit = plan.document_limit if plan else None
    if limit is None:
        return  # unlimited or no plan configured

    has_existing_folder = Document.objects.filter(
        user=user, document_type=document_type, status=Document.STATUS.ACTIVE
    ).exists()
    if has_existing_folder:
        return

    if get_active_document_count(user) >= limit:
        raise serializers.ValidationError(
            {
                "document_type": [
                    f"Document limit reached ({limit}). "
                    "Upgrade your plan to upload more documents."
                ]
            }
        )
