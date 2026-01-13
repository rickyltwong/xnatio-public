"""Tests for xnatio.exceptions module."""

from __future__ import annotations

import pytest

from xnatio.core import (
    XNATError,
    ConfigurationError,
    MissingCredentialsError,
    InvalidConfigurationError,
    ConnectionError,
    AuthenticationError,
    ServerUnreachableError,
    ValidationError,
    InvalidIdentifierError,
    InvalidURLError,
    InvalidPortError,
    PathValidationError,
    ResourceError,
    ResourceNotFoundError,
    ResourceExistsError,
    UploadError,
    DicomUploadError,
    ArchiveUploadError,
    DownloadError,
    OperationError,
    BatchOperationError,
    NetworkError,
    RetryExhaustedError,
    DicomError,
)


class TestXNATError:
    """Tests for base XNATError."""

    def test_basic_error(self):
        """Test basic error creation."""
        err = XNATError("Something went wrong")
        assert str(err) == "Something went wrong"
        assert err.message == "Something went wrong"
        assert err.details == {}
        assert err.operation is None

    def test_error_with_details(self):
        """Test error with details and operation."""
        err = XNATError(
            "Upload failed",
            details={"file": "test.zip", "size": 1024},
            operation="upload",
        )
        assert "Upload failed" in str(err)
        assert "[upload]" in str(err)
        assert err.details == {"file": "test.zip", "size": 1024}
        assert err.operation == "upload"


class TestConfigurationErrors:
    """Tests for configuration-related errors."""

    def test_missing_credentials(self):
        """Test MissingCredentialsError."""
        err = MissingCredentialsError(["XNAT_USERNAME", "XNAT_PASSWORD"])
        assert "XNAT_USERNAME" in str(err)
        assert "XNAT_PASSWORD" in str(err)
        assert err.missing_vars == ["XNAT_USERNAME", "XNAT_PASSWORD"]

    def test_invalid_configuration(self):
        """Test InvalidConfigurationError."""
        err = InvalidConfigurationError("timeout", -5, "must be positive")
        assert "timeout" in str(err)
        assert "must be positive" in str(err)
        assert err.field == "timeout"
        assert err.value == -5


class TestConnectionErrors:
    """Tests for connection-related errors."""

    def test_authentication_error(self):
        """Test AuthenticationError."""
        err = AuthenticationError("https://xnat.example.org")
        assert "Authentication failed" in str(err)
        assert err.server == "https://xnat.example.org"

    def test_server_unreachable(self):
        """Test ServerUnreachableError."""
        cause = Exception("Connection refused")
        err = ServerUnreachableError("https://xnat.example.org", cause)
        assert "Cannot reach" in str(err)
        assert err.server == "https://xnat.example.org"
        assert err.cause == cause


class TestValidationErrors:
    """Tests for validation-related errors."""

    def test_invalid_identifier(self):
        """Test InvalidIdentifierError."""
        err = InvalidIdentifierError("project", "my project!", "contains invalid characters")
        assert "project" in str(err)
        assert "my project!" in str(err)
        assert err.identifier_type == "project"
        assert err.value == "my project!"

    def test_invalid_url(self):
        """Test InvalidURLError."""
        err = InvalidURLError("not-a-url", "must include scheme")
        assert "not-a-url" in str(err)
        assert err.url == "not-a-url"

    def test_invalid_port(self):
        """Test InvalidPortError."""
        err = InvalidPortError(99999)
        assert "99999" in str(err)
        assert "1-65535" in str(err)
        assert err.port == 99999

    def test_path_validation_error(self):
        """Test PathValidationError."""
        err = PathValidationError("/nonexistent/path", "does not exist")
        assert "/nonexistent/path" in str(err)
        assert err.path == "/nonexistent/path"


class TestResourceErrors:
    """Tests for resource-related errors."""

    def test_resource_not_found(self):
        """Test ResourceNotFoundError."""
        err = ResourceNotFoundError("session", "SESS001", project="PROJ001")
        assert "session" in str(err).lower()
        assert "SESS001" in str(err)
        assert err.resource_type == "session"
        assert err.identifier == "SESS001"
        assert err.project == "PROJ001"

    def test_resource_exists(self):
        """Test ResourceExistsError."""
        err = ResourceExistsError("subject", "SUBJ001")
        assert "already exists" in str(err).lower()
        assert "SUBJ001" in str(err)


class TestUploadErrors:
    """Tests for upload-related errors."""

    def test_dicom_upload_error(self):
        """Test DicomUploadError."""
        err = DicomUploadError(
            "Upload timeout",
            session="SESS001",
            files_processed=100,
            files_failed=5,
        )
        assert "Upload timeout" in str(err)
        assert err.session == "SESS001"
        assert err.files_processed == 100
        assert err.files_failed == 5

    def test_archive_upload_error(self):
        """Test ArchiveUploadError."""
        err = ArchiveUploadError("/path/to/archive.zip", "Server rejected")
        assert "archive.zip" in str(err)
        assert err.archive_path == "/path/to/archive.zip"


class TestOperationErrors:
    """Tests for operation-related errors."""

    def test_batch_operation_error(self):
        """Test BatchOperationError."""
        err = BatchOperationError(
            "delete_scans",
            succeeded=8,
            failed=2,
            errors=["Scan 5 locked", "Scan 7 not found"],
        )
        assert "8 succeeded" in str(err)
        assert "2 failed" in str(err)
        assert err.succeeded == 8
        assert err.failed == 2
        assert len(err.errors) == 2


class TestNetworkErrors:
    """Tests for network-related errors."""

    def test_retry_exhausted_error(self):
        """Test RetryExhaustedError."""
        cause = TimeoutError("Connection timed out")
        err = RetryExhaustedError("upload", attempts=3, last_error=cause)
        assert "3 attempts" in str(err)
        assert err.attempts == 3
        assert err.last_error == cause


class TestInheritance:
    """Test exception inheritance hierarchy."""

    def test_all_errors_inherit_from_xnat_error(self):
        """All xnatio exceptions should inherit from XNATError."""
        errors = [
            ConfigurationError("test"),
            MissingCredentialsError([]),
            ConnectionError("test"),
            ValidationError("test"),
            ResourceError("test"),
            UploadError("test"),
            DownloadError("test"),
            OperationError("test"),
            NetworkError("test"),
            DicomError("test"),
        ]
        for err in errors:
            assert isinstance(err, XNATError)

    def test_catch_all_xnat_errors(self):
        """Can catch all xnatio errors with XNATError."""
        try:
            raise InvalidIdentifierError("test", "value", "reason")
        except XNATError as e:
            assert "test" in str(e)
