from datetime import timedelta

import factory
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from app.apps.documents.models.document import Document, DocumentStatus
from app.apps.documents.models.document_request import (
    DocumentRequest,
    DocumentRequestStatus,
)
from app.apps.documents.models.document_type import DocumentType


class DocumentTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DocumentType

    name = factory.Sequence(lambda n: f"Type {n}")
    description = "Test document type"


class DocumentRequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DocumentRequest

    requester = factory.SubFactory("apps.accounts.tests.factories.UserFactory")
    recipient_email = factory.Sequence(lambda n: f"user{n}@test.com")
    document_type = factory.SubFactory(DocumentTypeFactory)

    status = DocumentRequestStatus.PENDING

    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=30))

    last_sent_at = None


class DocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Document

    name = factory.Sequence(lambda n: f"Document {n}")
    user = factory.SubFactory("apps.accounts.tests.factories.UserFactory")
    document_type = factory.SubFactory(DocumentTypeFactory)
    expiration_date = factory.LazyFunction(
        lambda: timezone.now().date() + timedelta(days=365)
    )
    status = DocumentStatus.ACTIVE

    file = factory.LazyFunction(
        lambda: SimpleUploadedFile(
            "test.pdf",
            b"file-content",
            content_type="application/pdf",
        )
    )
