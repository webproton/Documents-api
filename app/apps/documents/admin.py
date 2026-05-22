from django.contrib import admin

from app.apps.documents.models.document import Document
from app.apps.documents.models.document_request import DocumentRequest
from app.apps.documents.models.document_type import DocumentType


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "description", "has_template", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]

    def has_template(self, obj):
        return bool(obj.template)

    has_template.boolean = True

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_staff or request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_staff or request.user.is_superuser


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "document_type", "status", "created_at"]
    list_filter = ["status", "document_type"]
    search_fields = ["name", "user__email"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(DocumentRequest)
class DocumentRequestAdmin(admin.ModelAdmin):
    list_display = ["recipient_email", "document_type", "status", "created_at"]
    list_filter = ["status", "document_type"]
    search_fields = ["recipient_email"]
    readonly_fields = ["token", "created_at"]
