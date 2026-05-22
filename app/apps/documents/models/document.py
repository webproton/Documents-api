# documents/models/document.py
from django.conf import settings
from django.db import models


class DocumentStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    REPLACED = "REPLACED", "Replaced"


def document_upload_to(instance, filename):
    """generate path for S3"""
    ext = filename.split(".")[-1]
    return (
        f"documents/{instance.user_id}/{instance.document_type_id}/{instance.id}_{ext}"
    )


class Document(models.Model):
    name = models.CharField(max_length=200, verbose_name="Name")

    file = models.FileField(
        upload_to=document_upload_to,
        verbose_name="File",
    )

    document_type = models.ForeignKey(
        "documents.DocumentType",
        on_delete=models.PROTECT,
        verbose_name="Document type",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="User",
        related_name="documents",
    )

    expiration_date = models.DateField(verbose_name="Expiration date")

    status = models.CharField(
        max_length=10,
        choices=DocumentStatus.choices,
        default=DocumentStatus.ACTIVE,
        verbose_name="Status",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created at")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated at")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "document_type"]),
            models.Index(fields=["status"]),
        ]
        verbose_name = "Document"
        verbose_name_plural = "Documents"

    def __str__(self):
        return f"{self.name} ({self.document_type.name})"
