"""Structured logging configuration for xnatio.

This module provides production-grade logging with:
- Correlation IDs for request tracing
- Structured JSON output option for log aggregation
- Context managers for operation tracking
- Audit logging for compliance

Usage:
    from xnatio.logging_config import setup_logging, get_logger, LogContext

    # Setup logging at application start
    setup_logging(level="INFO", json_output=True)

    # Get logger with context
    log = get_logger(__name__)

    # Use context manager for operations
    with LogContext(operation="upload_dicom", session="SESS001") as ctx:
        log.info("Starting upload")
        ctx.add_detail("files", 100)
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator, Optional, Union

# Context variable for correlation ID - thread-safe
_correlation_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)

# Context variable for operation details
_operation_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "operation_context", default={}
)


# =============================================================================
# Correlation ID Management
# =============================================================================


def get_correlation_id() -> str:
    """Get current correlation ID or generate a new one."""
    cid = _correlation_id.get()
    if cid is None:
        cid = generate_correlation_id()
        _correlation_id.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    """Set correlation ID for current context."""
    _correlation_id.set(cid)


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())[:8]


def clear_correlation_id() -> None:
    """Clear correlation ID from current context."""
    _correlation_id.set(None)


# =============================================================================
# Custom Log Record
# =============================================================================


class ContextFilter(logging.Filter):
    """Filter that adds context information to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()  # type: ignore[attr-defined]
        record.operation_context = _operation_context.get()  # type: ignore[attr-defined]
        return True


# =============================================================================
# Formatters
# =============================================================================


class StandardFormatter(logging.Formatter):
    """Human-readable formatter with correlation ID."""

    def __init__(self) -> None:
        fmt = "%(asctime)s %(levelname)-8s [%(correlation_id)s] %(name)s: %(message)s"
        super().__init__(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        # Ensure correlation_id exists
        if not hasattr(record, "correlation_id"):
            record.correlation_id = "-"  # type: ignore[attr-defined]
        return super().format(record)


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None),
        }

        # Add operation context
        op_ctx = getattr(record, "operation_context", {})
        if op_ctx:
            log_data["context"] = op_ctx

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields (excluding standard LogRecord attributes)
        standard_attrs = {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "exc_info",
            "exc_text",
            "thread",
            "threadName",
            "message",
            "correlation_id",
            "operation_context",
            "taskName",
        }
        extra = {k: v for k, v in record.__dict__.items() if k not in standard_attrs}
        if extra:
            log_data["extra"] = extra

        return json.dumps(log_data, default=str)


# =============================================================================
# Audit Logger
# =============================================================================


class AuditLogger:
    """Specialized logger for audit trail of operations.

    Audit logs capture:
    - Operation type and parameters
    - User/credential information (masked)
    - Timestamps and duration
    - Success/failure status
    - Affected resources

    Usage:
        audit = AuditLogger()
        audit.log_operation(
            operation="delete_scans",
            project="PROJ001",
            user="admin",
            details={"scans": ["1", "2", "3"]},
            success=True,
        )
    """

    def __init__(self, logger_name: str = "xnatio.audit") -> None:
        self.logger = logging.getLogger(logger_name)

    def log_operation(
        self,
        operation: str,
        *,
        user: Optional[str] = None,
        project: Optional[str] = None,
        subject: Optional[str] = None,
        session: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        success: bool = True,
        error: Optional[str] = None,
        duration_ms: Optional[float] = None,
    ) -> None:
        """Log an auditable operation."""
        audit_record = {
            "audit": True,
            "operation": operation,
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correlation_id": get_correlation_id(),
        }

        if user:
            audit_record["user"] = user
        if project:
            audit_record["project"] = project
        if subject:
            audit_record["subject"] = subject
        if session:
            audit_record["session"] = session
        if details:
            audit_record["details"] = details
        if error:
            audit_record["error"] = error
        if duration_ms is not None:
            audit_record["duration_ms"] = round(duration_ms, 2)

        level = logging.INFO if success else logging.WARNING
        self.logger.log(level, json.dumps(audit_record, default=str))


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


# =============================================================================
# Context Manager for Operations
# =============================================================================


class LogContext:
    """Context manager for logging operation context.

    Automatically:
    - Generates/preserves correlation ID
    - Tracks operation duration
    - Logs start/end of operations
    - Handles exceptions with proper logging

    Usage:
        with LogContext(operation="upload_dicom", session="SESS001") as ctx:
            # Your operation code
            ctx.add_detail("files_processed", 100)
    """

    def __init__(
        self,
        operation: str,
        logger: Optional[logging.Logger] = None,
        *,
        correlation_id: Optional[str] = None,
        log_entry_exit: bool = True,
        **context: Any,
    ) -> None:
        self.operation = operation
        self.logger = logger or logging.getLogger("xnatio")
        self.log_entry_exit = log_entry_exit
        self.context = {"operation": operation, **context}
        self.start_time: Optional[float] = None
        self.correlation_id = correlation_id or get_correlation_id()
        self._token: Optional[contextvars.Token[dict[str, Any]]] = None
        self._cid_token: Optional[contextvars.Token[Optional[str]]] = None

    def __enter__(self) -> "LogContext":
        import time

        self.start_time = time.time()
        self._token = _operation_context.set(self.context)
        self._cid_token = _correlation_id.set(self.correlation_id)

        if self.log_entry_exit:
            self.logger.info("Starting %s", self.operation, extra=self.context)

        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Any,
    ) -> bool:
        import time

        duration_ms = (time.time() - (self.start_time or 0)) * 1000

        if exc_val is not None:
            self.logger.error(
                "%s failed after %.1fms: %s",
                self.operation,
                duration_ms,
                exc_val,
                exc_info=True,
                extra={**self.context, "duration_ms": duration_ms, "success": False},
            )
        elif self.log_entry_exit:
            self.logger.info(
                "Completed %s in %.1fms",
                self.operation,
                duration_ms,
                extra={**self.context, "duration_ms": duration_ms, "success": True},
            )

        # Restore previous context
        if self._token is not None:
            _operation_context.reset(self._token)
        if self._cid_token is not None:
            _correlation_id.reset(self._cid_token)

        return False  # Don't suppress exceptions

    def add_detail(self, key: str, value: Any) -> None:
        """Add a detail to the operation context."""
        self.context[key] = value


@contextmanager
def log_operation(
    operation: str,
    logger: Optional[logging.Logger] = None,
    **context: Any,
) -> Generator[LogContext, None, None]:
    """Context manager shorthand for LogContext.

    Usage:
        with log_operation("delete_scans", project="PROJ001") as ctx:
            # Your code
            ctx.add_detail("deleted", 5)
    """
    with LogContext(operation, logger, **context) as ctx:
        yield ctx


# =============================================================================
# Setup Functions
# =============================================================================


def setup_logging(
    level: Union[int, str] = logging.INFO,
    *,
    json_output: bool = False,
    log_file: Optional[str] = None,
    audit_file: Optional[str] = None,
) -> None:
    """Configure logging for the xnatio application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR).
        json_output: If True, use JSON formatter for structured output.
        log_file: Optional path to write logs to file.
        audit_file: Optional separate file for audit logs.
    """
    # Convert string level to int
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    # Get root xnatio logger
    root_logger = logging.getLogger("xnatio")
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Add context filter
    context_filter = ContextFilter()

    # Choose formatter
    formatter: logging.Formatter
    if json_output:
        formatter = JSONFormatter()
    else:
        formatter = StandardFormatter()

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(context_filter)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(context_filter)
        root_logger.addHandler(file_handler)

    # Audit logger setup
    audit_logger = logging.getLogger("xnatio.audit")
    audit_logger.setLevel(logging.INFO)
    audit_logger.handlers.clear()

    if audit_file:
        audit_handler = logging.FileHandler(audit_file)
        audit_handler.setFormatter(JSONFormatter())
        audit_handler.addFilter(context_filter)
        audit_logger.addHandler(audit_handler)
    else:
        # Audit logs go to same output as regular logs
        audit_logger.addHandler(console_handler)

    # Prevent propagation to root logger
    root_logger.propagate = False
    audit_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the xnatio namespace.

    Args:
        name: Logger name (usually __name__).

    Returns:
        Logger instance with xnatio prefix if not already present.
    """
    if not name.startswith("xnatio"):
        name = f"xnatio.{name}"
    return logging.getLogger(name)


# =============================================================================
# Convenience Functions
# =============================================================================


def mask_sensitive(value: str, visible_chars: int = 4) -> str:
    """Mask sensitive values for logging.

    Args:
        value: Value to mask.
        visible_chars: Number of characters to show at end.

    Returns:
        Masked string like "****abcd".
    """
    if not value or len(value) <= visible_chars:
        return "****"
    return "*" * (len(value) - visible_chars) + value[-visible_chars:]


def sanitize_for_log(data: dict[str, Any], sensitive_keys: Optional[set[str]] = None) -> dict[str, Any]:
    """Sanitize a dictionary for logging by masking sensitive values.

    Args:
        data: Dictionary to sanitize.
        sensitive_keys: Keys to mask (defaults to common sensitive keys).

    Returns:
        Copy of dictionary with sensitive values masked.
    """
    if sensitive_keys is None:
        sensitive_keys = {"password", "token", "secret", "api_key", "credential", "auth"}

    result = {}
    for key, value in data.items():
        if any(s in key.lower() for s in sensitive_keys):
            result[key] = mask_sensitive(str(value)) if value else None
        elif isinstance(value, dict):
            result[key] = sanitize_for_log(value, sensitive_keys)
        else:
            result[key] = value
    return result
