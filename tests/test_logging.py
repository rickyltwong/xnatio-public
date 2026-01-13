"""Tests for xnatio.logging_config module."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from xnatio.core import (
    get_correlation_id,
    set_correlation_id,
    generate_correlation_id,
    clear_correlation_id,
    LogContext,
    AuditLogger,
    get_audit_logger,
    setup_logging,
    get_logger,
    mask_sensitive,
    sanitize_for_log,
    StandardFormatter,
    JSONFormatter,
)


class TestCorrelationID:
    """Tests for correlation ID management."""

    def setup_method(self):
        """Clear correlation ID before each test."""
        clear_correlation_id()

    def test_generate_correlation_id(self):
        """Generated IDs should be 8 characters."""
        cid = generate_correlation_id()
        assert len(cid) == 8
        assert cid.isalnum() or "-" in cid

    def test_get_generates_if_none(self):
        """get_correlation_id should generate if none exists."""
        clear_correlation_id()
        cid = get_correlation_id()
        assert cid is not None
        assert len(cid) == 8

    def test_get_returns_same(self):
        """get_correlation_id should return same ID on subsequent calls."""
        cid1 = get_correlation_id()
        cid2 = get_correlation_id()
        assert cid1 == cid2

    def test_set_correlation_id(self):
        """set_correlation_id should set a specific ID."""
        set_correlation_id("test1234")
        assert get_correlation_id() == "test1234"

    def test_clear_correlation_id(self):
        """clear_correlation_id should reset the ID."""
        set_correlation_id("test1234")
        clear_correlation_id()
        cid = get_correlation_id()
        assert cid != "test1234"


class TestLogContext:
    """Tests for LogContext context manager."""

    def setup_method(self):
        """Clear correlation ID before each test."""
        clear_correlation_id()

    def test_basic_context(self):
        """LogContext should work as context manager."""
        logger = logging.getLogger("test")
        with LogContext("test_operation", logger, log_entry_exit=False) as ctx:
            assert ctx.operation == "test_operation"

    def test_sets_correlation_id(self):
        """LogContext should set correlation ID."""
        logger = logging.getLogger("test")
        with LogContext("test_op", logger, correlation_id="ctx12345", log_entry_exit=False):
            assert get_correlation_id() == "ctx12345"

    def test_add_detail(self):
        """add_detail should add to context."""
        logger = logging.getLogger("test")
        with LogContext("test_op", logger, log_entry_exit=False) as ctx:
            ctx.add_detail("files", 100)
            assert ctx.context["files"] == 100

    def test_context_with_kwargs(self):
        """Additional kwargs should be stored in context."""
        logger = logging.getLogger("test")
        with LogContext("upload", logger, project="PROJ1", session="SESS1", log_entry_exit=False) as ctx:
            assert ctx.context["project"] == "PROJ1"
            assert ctx.context["session"] == "SESS1"


class TestAuditLogger:
    """Tests for AuditLogger."""

    def test_log_operation_success(self):
        """log_operation should log successful operations."""
        audit = AuditLogger("test.audit")

        with mock.patch.object(audit.logger, "log") as mock_log:
            audit.log_operation(
                "create_project",
                project="PROJ001",
                user="admin",
                success=True,
            )
            mock_log.assert_called_once()
            args, kwargs = mock_log.call_args
            assert args[0] == logging.INFO  # Success uses INFO level
            logged_data = json.loads(args[1])
            assert logged_data["audit"] is True
            assert logged_data["operation"] == "create_project"
            assert logged_data["success"] is True
            assert logged_data["project"] == "PROJ001"

    def test_log_operation_failure(self):
        """log_operation should log failed operations at WARNING level."""
        audit = AuditLogger("test.audit")

        with mock.patch.object(audit.logger, "log") as mock_log:
            audit.log_operation(
                "delete_scans",
                project="PROJ001",
                success=False,
                error="Permission denied",
            )
            mock_log.assert_called_once()
            args, kwargs = mock_log.call_args
            assert args[0] == logging.WARNING  # Failure uses WARNING level

    def test_get_audit_logger_singleton(self):
        """get_audit_logger should return same instance."""
        a1 = get_audit_logger()
        a2 = get_audit_logger()
        assert a1 is a2


class TestFormatters:
    """Tests for log formatters."""

    def test_standard_formatter(self):
        """StandardFormatter should produce readable output."""
        formatter = StandardFormatter()
        record = logging.LogRecord(
            name="xnatio.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "abc12345"
        output = formatter.format(record)
        assert "Test message" in output
        assert "abc12345" in output
        assert "INFO" in output

    def test_json_formatter(self):
        """JSONFormatter should produce valid JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="xnatio.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "abc12345"
        record.operation_context = {"project": "PROJ1"}
        output = formatter.format(record)
        data = json.loads(output)
        assert data["message"] == "Test message"
        assert data["correlation_id"] == "abc12345"
        assert data["level"] == "INFO"
        assert data["context"]["project"] == "PROJ1"


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_with_level_string(self):
        """setup_logging should accept string level."""
        setup_logging(level="DEBUG")
        logger = get_logger("test")
        assert logger.level == logging.DEBUG or logger.parent.level == logging.DEBUG

    def test_setup_with_json_output(self):
        """setup_logging should configure JSON formatter."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            log_file = f.name

        try:
            setup_logging(level="INFO", json_output=True, log_file=log_file)
            logger = get_logger("test_json")
            logger.info("Test JSON logging")

            # Verify file was written
            content = Path(log_file).read_text()
            # Should contain JSON-like structure
            assert "Test JSON logging" in content
        finally:
            Path(log_file).unlink(missing_ok=True)


class TestGetLogger:
    """Tests for get_logger function."""

    def test_adds_xnatio_prefix(self):
        """get_logger should add xnatio prefix if missing."""
        logger = get_logger("mymodule")
        assert logger.name == "xnatio.mymodule"

    def test_keeps_xnatio_prefix(self):
        """get_logger should keep existing xnatio prefix."""
        logger = get_logger("xnatio.mymodule")
        assert logger.name == "xnatio.mymodule"


class TestMaskSensitive:
    """Tests for mask_sensitive function."""

    def test_masks_value(self):
        """mask_sensitive should mask most of the value."""
        result = mask_sensitive("mysecretpassword")
        assert result.endswith("word")
        assert result.startswith("*")
        assert "secret" not in result

    def test_short_value_fully_masked(self):
        """Short values should be fully masked."""
        result = mask_sensitive("abc")
        assert result == "****"

    def test_custom_visible_chars(self):
        """visible_chars parameter should control visible portion."""
        result = mask_sensitive("mysecretpassword", visible_chars=6)
        assert result.endswith("ssword")

    def test_empty_value(self):
        """Empty values should return masked string."""
        result = mask_sensitive("")
        assert result == "****"


class TestSanitizeForLog:
    """Tests for sanitize_for_log function."""

    def test_masks_password(self):
        """password field should be masked."""
        data = {"username": "admin", "password": "secret123"}
        result = sanitize_for_log(data)
        assert result["username"] == "admin"
        assert "secret" not in result["password"]
        assert result["password"].startswith("*")

    def test_masks_token(self):
        """token field should be masked."""
        data = {"api_token": "abc123xyz789"}
        result = sanitize_for_log(data)
        assert "abc123" not in result["api_token"]

    def test_nested_dict(self):
        """Nested dicts should be sanitized."""
        data = {
            "config": {
                "server": "https://example.org",
                "credentials": {
                    "password": "secret123"
                }
            }
        }
        result = sanitize_for_log(data)
        assert result["config"]["server"] == "https://example.org"
        assert "secret" not in result["config"]["credentials"]["password"]

    def test_preserves_non_sensitive(self):
        """Non-sensitive fields should be preserved."""
        data = {"project": "PROJ001", "session": "SESS001", "count": 42}
        result = sanitize_for_log(data)
        assert result == data

    def test_custom_sensitive_keys(self):
        """Custom sensitive keys should be supported."""
        data = {"custom_secret": "value123"}
        result = sanitize_for_log(data, sensitive_keys={"custom_secret"})
        assert "value" not in result["custom_secret"]
