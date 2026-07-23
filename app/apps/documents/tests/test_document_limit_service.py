# app/apps/documents/tests/test_document_limit_service.py
import pytest

from app.apps.billing.models import Plan, Subscription
from app.apps.billing.tests.factories.plan import PlanFactory
from app.apps.documents.models import Document
from app.apps.documents.services import check_document_limit
from app.apps.documents.services.document_limit import get_active_document_count
from app.apps.documents.tests.factories import DocumentFactory, DocumentTypeFactory


def _set_plan(user, plan):
    Subscription.objects.filter(user=user).update(plan=plan)
    user.refresh_from_db()
    return user.subscription


@pytest.mark.django_db
class TestGetActiveDocumentCount:
    def test_counts_only_active_documents(self, user):
        doc_type = DocumentTypeFactory()
        DocumentFactory(
            user=user, document_type=doc_type, status=Document.STATUS.ACTIVE
        )
        DocumentFactory(
            user=user, document_type=doc_type, status=Document.STATUS.REPLACED
        )
        DocumentFactory(
            user=user, document_type=doc_type, status=Document.STATUS.REPLACED
        )

        assert get_active_document_count(user) == 1

    def test_zero_when_no_documents(self, user):
        assert get_active_document_count(user) == 0

    def test_counts_across_multiple_folders(self, user):
        DocumentFactory(
            user=user,
            document_type=DocumentTypeFactory(),
            status=Document.STATUS.ACTIVE,
        )
        DocumentFactory(
            user=user,
            document_type=DocumentTypeFactory(),
            status=Document.STATUS.ACTIVE,
        )

        assert get_active_document_count(user) == 2


@pytest.mark.django_db
class TestCheckDocumentLimit:
    def test_unlimited_plan_never_raises(self, user):
        business_plan = PlanFactory(name=Plan.NAME.BUSINESS)
        business_plan.document_limit = None
        business_plan.save(update_fields=["document_limit"])
        _set_plan(user, business_plan)

        for _ in range(10):
            DocumentFactory(
                user=user,
                document_type=DocumentTypeFactory(),
                status=Document.STATUS.ACTIVE,
            )

        # should not quit
        check_document_limit(user, DocumentTypeFactory())

    def test_raises_when_limit_reached_for_new_folder(self, user):
        limited_plan = PlanFactory(name=Plan.NAME.PRO)
        limited_plan.document_limit = 2
        limited_plan.save(update_fields=["document_limit"])
        _set_plan(user, limited_plan)

        DocumentFactory(
            user=user,
            document_type=DocumentTypeFactory(),
            status=Document.STATUS.ACTIVE,
        )
        DocumentFactory(
            user=user,
            document_type=DocumentTypeFactory(),
            status=Document.STATUS.ACTIVE,
        )

        new_type = DocumentTypeFactory()

        with pytest.raises(Exception) as exc_info:
            check_document_limit(user, new_type)

        assert "document_type" in exc_info.value.detail

    def test_does_not_raise_below_limit(self, user):
        limited_plan = PlanFactory(name=Plan.NAME.PRO)
        limited_plan.document_limit = 2
        limited_plan.save(update_fields=["document_limit"])
        _set_plan(user, limited_plan)

        DocumentFactory(
            user=user,
            document_type=DocumentTypeFactory(),
            status=Document.STATUS.ACTIVE,
        )

        check_document_limit(user, DocumentTypeFactory())  # 1 < 2, не должно упасть

    def test_replacing_existing_folder_does_not_raise_even_at_limit(self, user):
        """
        Replacing a version in an existing
        folder should not be considered a new document
        """
        limited_plan = PlanFactory(name=Plan.NAME.PRO)
        limited_plan.document_limit = 1
        limited_plan.save(update_fields=["document_limit"])
        _set_plan(user, limited_plan)

        existing_type = DocumentTypeFactory()
        DocumentFactory(
            user=user, document_type=existing_type, status=Document.STATUS.ACTIVE
        )

        # The limit has already been reached (1 document at limit=1),
        # but this is an upload to the same type
        check_document_limit(user, existing_type)  # must not fall

    def test_fail_open_when_plan_is_none(self, user):
        Subscription.objects.filter(user=user).update(plan=None)
        user.refresh_from_db()

        for _ in range(20):
            DocumentFactory(
                user=user,
                document_type=DocumentTypeFactory(),
                status=Document.STATUS.ACTIVE,
            )

        # Plan Not Set – Fail Open
        check_document_limit(user, DocumentTypeFactory())
