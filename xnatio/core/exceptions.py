"""Custom exception hierarchy for xnatio.

This module provides a structured exception hierarchy for XNAT operations,
enabling precise error handling and meaningful error messages for operators.
"""

from __future__ import annotations

from typing import Any, Optional


class XNATError(Exception):
    """Base exception for all xnatio errors.

    All xnatio-specific exceptions inherit from this class, allowing
    callers to catch all xnatio errors with a single except clause.

    Attributes:
        message: Human-readable error description.
        details: Optional dictionary with additional context.
        operation: The operation that was being performed when the error occurred.
    """

    def __init__(
        self,
        message: str,
        *,
        details: Optional[dict[str, Any]] = None,
        operation: Optional[str] = None,
    ) -> None:
        self.message = message
        self.details = details or {}
        self.operation = operation
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        parts = [self.message]
        if self.operation:
            parts.insert(0, f"[{self.operation}]")
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            parts.append(f"({detail_str})")
        return " ".join(parts)


# =============================================================================
# Configuration Errors
# =============================================================================


class ConfigurationError(XNATError):
    """Error in configuration or environment setup."""

    pass


class MissingCredentialsError(ConfigurationError):
    """Required credentials are missing."""

    def __init__(self, missing_vars: list[str]) -> None:
        self.missing_vars = missing_vars
        super().__init__(
            f"Missing required credentials: {', '.join(missing_vars)}",
            details={"missing": missing_vars},
            operation="configuration",
        )


class InvalidConfigurationError(ConfigurationError):
    """Configuration value is invalid."""

    def __init__(self, field: str, value: Any, reason: str) -> None:
        self.field = field
        self.value = value
        self.reason = reason
        super().__init__(
            f"Invalid configuration for '{field}': {reason}",
            details={"field": field, "value": str(value)[:100]},
            operation="configuration",
        )


# =============================================================================
# Connection Errors
# =============================================================================


class ConnectionError(XNATError):
    """Error establishing or maintaining connection to XNAT server."""

    pass


class AuthenticationError(ConnectionError):
    """Authentication failed."""

    def __init__(self, server: str, reason: str = "Invalid credentials") -> None:
        self.server = server
        super().__init__(
            f"Authentication failed: {reason}",
            details={"server": server},
            operation="authentication",
        )


class ServerUnreachableError(ConnectionError):
    """Cannot connect to XNAT server."""

    def __init__(self, server: str, cause: Optional[Exception] = None) -> None:
        self.server = server
        self.cause = cause
        msg = f"Cannot reach XNAT server at {server}"
        if cause:
            msg += f": {cause}"
        super().__init__(msg, details={"server": server}, operation="connection")


class SessionExpiredError(ConnectionError):
    """XNAT session has expired."""

    def __init__(self, server: str) -> None:
        self.server = server
        super().__init__(
            "Session expired, re-authentication required",
            details={"server": server},
            operation="session",
        )


# =============================================================================
# Validation Errors
# =============================================================================


class ValidationError(XNATError):
    """Input validation failed."""

    pass


class InvalidIdentifierError(ValidationError):
    """Project, subject, session, or scan identifier is invalid."""

    def __init__(self, identifier_type: str, value: str, reason: str) -> None:
        self.identifier_type = identifier_type
        self.value = value
        super().__init__(
            f"Invalid {identifier_type}: '{value}' - {reason}",
            details={"type": identifier_type, "value": value},
            operation="validation",
        )


class InvalidURLError(ValidationError):
    """URL format is invalid."""

    def __init__(self, url: str, reason: str) -> None:
        self.url = url
        super().__init__(
            f"Invalid URL '{url}': {reason}",
            details={"url": url[:200]},
            operation="validation",
        )


class InvalidPortError(ValidationError):
    """Port number is out of valid range."""

    def __init__(self, port: Any) -> None:
        self.port = port
        super().__init__(
            f"Invalid port number: {port} (must be 1-65535)",
            details={"port": str(port)},
            operation="validation",
        )


class PathValidationError(ValidationError):
    """File or directory path is invalid or inaccessible."""

    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        super().__init__(
            f"Path error for '{path}': {reason}",
            details={"path": path},
            operation="validation",
        )


# =============================================================================
# Resource Errors
# =============================================================================


class ResourceError(XNATError):
    """Error with XNAT resource (project, subject, session, scan)."""

    pass


class ResourceNotFoundError(ResourceError):
    """Requested resource does not exist."""

    def __init__(
        self,
        resource_type: str,
        identifier: str,
        project: Optional[str] = None,
    ) -> None:
        self.resource_type = resource_type
        self.identifier = identifier
        self.project = project
        details: dict[str, Any] = {"type": resource_type, "id": identifier}
        if project:
            details["project"] = project
        super().__init__(
            f"{resource_type.capitalize()} not found: {identifier}",
            details=details,
            operation="lookup",
        )


class ResourceExistsError(ResourceError):
    """Resource already exists when trying to create."""

    def __init__(self, resource_type: str, identifier: str) -> None:
        self.resource_type = resource_type
        self.identifier = identifier
        super().__init__(
            f"{resource_type.capitalize()} already exists: {identifier}",
            details={"type": resource_type, "id": identifier},
            operation="create",
        )


class ResourceAccessDeniedError(ResourceError):
    """Access to resource is denied."""

    def __init__(
        self,
        resource_type: str,
        identifier: str,
        action: str = "access",
    ) -> None:
        self.resource_type = resource_type
        self.identifier = identifier
        self.action = action
        super().__init__(
            f"Access denied: cannot {action} {resource_type} '{identifier}'",
            details={"type": resource_type, "id": identifier, "action": action},
            operation="authorization",
        )


# =============================================================================
# Upload Errors
# =============================================================================


class UploadError(XNATError):
    """Error during file upload."""

    pass


class DicomUploadError(UploadError):
    """Error uploading DICOM data."""

    def __init__(
        self,
        message: str,
        *,
        session: Optional[str] = None,
        files_processed: int = 0,
        files_failed: int = 0,
    ) -> None:
        self.session = session
        self.files_processed = files_processed
        self.files_failed = files_failed
        details = {"processed": files_processed, "failed": files_failed}
        if session:
            details["session"] = session
        super().__init__(message, details=details, operation="dicom_upload")


class ArchiveUploadError(UploadError):
    """Error uploading archive file."""

    def __init__(self, archive_path: str, reason: str) -> None:
        self.archive_path = archive_path
        super().__init__(
            f"Failed to upload archive: {reason}",
            details={"archive": archive_path},
            operation="archive_upload",
        )


class ResourceUploadError(UploadError):
    """Error uploading resource file."""

    def __init__(
        self,
        resource_label: str,
        file_path: str,
        reason: str,
    ) -> None:
        self.resource_label = resource_label
        self.file_path = file_path
        super().__init__(
            f"Failed to upload to resource '{resource_label}': {reason}",
            details={"resource": resource_label, "file": file_path},
            operation="resource_upload",
        )


# =============================================================================
# Download Errors
# =============================================================================


class DownloadError(XNATError):
    """Error during file download."""

    pass


class SessionDownloadError(DownloadError):
    """Error downloading session data."""

    def __init__(self, session: str, reason: str) -> None:
        self.session = session
        super().__init__(
            f"Failed to download session '{session}': {reason}",
            details={"session": session},
            operation="session_download",
        )


# =============================================================================
# Operation Errors
# =============================================================================


class OperationError(XNATError):
    """Error during XNAT operation."""

    pass


class BatchOperationError(OperationError):
    """Error during batch operation with partial success."""

    def __init__(
        self,
        operation: str,
        succeeded: int,
        failed: int,
        errors: list[str],
    ) -> None:
        self.succeeded = succeeded
        self.failed = failed
        self.errors = errors
        super().__init__(
            f"Batch {operation} partially failed: {succeeded} succeeded, {failed} failed",
            details={"succeeded": succeeded, "failed": failed, "error_count": len(errors)},
            operation=operation,
        )


class CatalogRefreshError(OperationError):
    """Error refreshing catalog XML."""

    def __init__(self, experiment_id: str, reason: str) -> None:
        self.experiment_id = experiment_id
        super().__init__(
            f"Failed to refresh catalog for experiment '{experiment_id}': {reason}",
            details={"experiment": experiment_id},
            operation="catalog_refresh",
        )


class RenameError(OperationError):
    """Error renaming subject or experiment."""

    def __init__(
        self,
        resource_type: str,
        old_name: str,
        new_name: str,
        reason: str,
    ) -> None:
        self.resource_type = resource_type
        self.old_name = old_name
        self.new_name = new_name
        super().__init__(
            f"Failed to rename {resource_type} '{old_name}' to '{new_name}': {reason}",
            details={"type": resource_type, "from": old_name, "to": new_name},
            operation="rename",
        )


class DeleteError(OperationError):
    """Error deleting resource."""

    def __init__(self, resource_type: str, identifier: str, reason: str) -> None:
        self.resource_type = resource_type
        self.identifier = identifier
        super().__init__(
            f"Failed to delete {resource_type} '{identifier}': {reason}",
            details={"type": resource_type, "id": identifier},
            operation="delete",
        )


# =============================================================================
# Network Errors
# =============================================================================


class NetworkError(XNATError):
    """Network-related error during XNAT operation."""

    pass


class TimeoutError(NetworkError):
    """Operation timed out."""

    def __init__(self, operation: str, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Operation timed out after {timeout_seconds}s",
            details={"timeout_seconds": timeout_seconds},
            operation=operation,
        )


class RetryExhaustedError(NetworkError):
    """All retry attempts failed."""

    def __init__(
        self,
        operation: str,
        attempts: int,
        last_error: Optional[Exception] = None,
    ) -> None:
        self.attempts = attempts
        self.last_error = last_error
        msg = f"Failed after {attempts} attempts"
        if last_error:
            msg += f": {last_error}"
        super().__init__(
            msg,
            details={"attempts": attempts, "last_error": str(last_error) if last_error else None},
            operation=operation,
        )


# =============================================================================
# DICOM-specific Errors
# =============================================================================


class DicomError(XNATError):
    """DICOM-specific error."""

    pass


class DicomParseError(DicomError):
    """Error parsing DICOM file."""

    def __init__(self, file_path: str, reason: str) -> None:
        self.file_path = file_path
        super().__init__(
            f"Failed to parse DICOM file: {reason}",
            details={"file": file_path},
            operation="dicom_parse",
        )


class DicomStoreError(DicomError):
    """Error during DICOM C-STORE operation."""

    def __init__(
        self,
        host: str,
        port: int,
        reason: str,
        files_sent: int = 0,
        files_failed: int = 0,
    ) -> None:
        self.host = host
        self.port = port
        self.files_sent = files_sent
        self.files_failed = files_failed
        super().__init__(
            f"DICOM C-STORE failed: {reason}",
            details={
                "host": host,
                "port": port,
                "sent": files_sent,
                "failed": files_failed,
            },
            operation="dicom_store",
        )
