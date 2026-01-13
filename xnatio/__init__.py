"""XNAT IO - Production-grade CLI for XNAT server administration.

This package provides a comprehensive toolkit for managing XNAT neuroimaging
data servers, focused on admin tasks like DICOM upload, session management,
and catalog maintenance.

Architecture:
    xnatio/
    ├── core/           # Foundation modules (exceptions, logging, validation)
    ├── services/       # Modular service classes (XNATConnection, ProjectService, etc.)
    ├── commands/       # CLI command parsers and handlers
    ├── uploaders/      # DICOM upload transports (REST, C-STORE)
    ├── client.py       # Backward-compatible facade (XNATClient)
    └── config.py       # Configuration loading

For backward compatibility, XNATClient is available as a unified facade
that combines all services. New code should prefer using services directly.
"""

__version__ = "0.2.0"
__author__ = "Ricky Wong"
__description__ = "Production-grade CLI for XNAT server administration"

# Core configuration
# Backward-compatible client (facade pattern)
from .client import XNATClient
from .config import XNATConfig, load_config

# Core modules: exceptions, logging, validation, utilities
from .core import (
    ConfigurationError,
    ConnectionError,
    DicomError,
    DownloadError,
    LogContext,
    NetworkError,
    OperationError,
    ResourceError,
    UploadError,
    ValidationError,
    # Exceptions
    XNATError,
    get_audit_logger,
    get_logger,
    # Logging
    setup_logging,
    validate_port,
    validate_project_id,
    # Validation
    validate_server_url,
    validate_session_id,
    validate_subject_id,
)

# Modular services (preferred for new code)
from .services import (
    AdminService,
    DownloadService,
    ProjectService,
    ScanService,
    UploadService,
    XNATConnection,
)

# Legacy uploaders (for backward compatibility)
from .uploaders import send_dicom_store, upload_dicom_parallel_rest

__all__ = [
    # Version info
    "__version__",
    "__author__",
    # Configuration
    "XNATConfig",
    "load_config",
    # Client (backward compatible)
    "XNATClient",
    # Services (modular architecture)
    "XNATConnection",
    "ProjectService",
    "ScanService",
    "UploadService",
    "DownloadService",
    "AdminService",
    # Exceptions
    "XNATError",
    "ConfigurationError",
    "ConnectionError",
    "ValidationError",
    "ResourceError",
    "UploadError",
    "DownloadError",
    "OperationError",
    "NetworkError",
    "DicomError",
    # Logging
    "setup_logging",
    "get_logger",
    "LogContext",
    "get_audit_logger",
    # Validation
    "validate_server_url",
    "validate_port",
    "validate_project_id",
    "validate_subject_id",
    "validate_session_id",
    # Legacy uploaders
    "upload_dicom_parallel_rest",
    "send_dicom_store",
]
