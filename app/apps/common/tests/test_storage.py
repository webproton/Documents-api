"""Media files live in a private S3 bucket and are served via signed URLs."""

from config import settings as project_settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


def test_s3_storage_signs_urls_without_custom_domain():
    # Project config itself: django.conf.settings is patched by conftest
    options = project_settings.STORAGES["default"]["OPTIONS"]

    # A custom_domain would make django-storages return unsigned URLs
    assert "custom_domain" not in options
    assert options["querystring_auth"] is True
    assert options["querystring_expire"] > 0
    assert options["signature_version"] == "s3v4"


def test_tests_do_not_upload_to_s3():
    """conftest swaps the default storage for an in-memory one."""
    name = default_storage.save("probe.txt", ContentFile(b"x"))

    assert type(default_storage._wrapped).__name__ == "InMemoryStorage"
    assert default_storage.exists(name)
