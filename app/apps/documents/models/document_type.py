# documents/models/document_type.py

from django.db import models


class DocumentType(models.Model):
    name = models.CharField(max_length=100, verbose_name="Name")
    description = models.TextField(blank=True, verbose_name="Description")
    template = models.FileField(
        upload_to="document_templates/",
        null=True,
        blank=True,
        verbose_name="Template",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created at")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated at")

    class Meta:
        ordering = ["name"]
        verbose_name = "Document Type"
        verbose_name_plural = "Document Types"

    def __str__(self):
        return self.name
