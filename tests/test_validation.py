"""Tests for xnatio.validation module."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import pytest

from xnatio.core import (
    # Validation functions
    validate_server_url,
    validate_port,
    validate_xnat_identifier,
    validate_project_id,
    validate_subject_id,
    validate_session_id,
    validate_scan_id,
    validate_resource_label,
    validate_ae_title,
    validate_path_exists,
    validate_path_writable,
    validate_timeout,
    validate_workers,
    validate_overwrite_mode,
    validate_scan_ids_input,
    validate_project_list,
    validate_regex_pattern,
    # Exceptions
    InvalidURLError,
    InvalidPortError,
    InvalidIdentifierError,
    InvalidConfigurationError,
    PathValidationError,
)


class TestValidateServerURL:
    """Tests for validate_server_url."""

    def test_valid_https_url(self):
        """Valid HTTPS URL should pass."""
        result = validate_server_url("https://xnat.example.org")
        assert result == "https://xnat.example.org"

    def test_valid_http_url(self):
        """Valid HTTP URL should pass (though not recommended)."""
        result = validate_server_url("http://localhost:8080")
        assert result == "http://localhost:8080"

    def test_strips_trailing_slash(self):
        """Trailing slashes should be removed."""
        result = validate_server_url("https://xnat.example.org/")
        assert result == "https://xnat.example.org"

    def test_strips_multiple_trailing_slashes(self):
        """Multiple trailing slashes should be removed."""
        result = validate_server_url("https://xnat.example.org///")
        assert result == "https://xnat.example.org"

    def test_empty_url_raises(self):
        """Empty URL should raise InvalidURLError."""
        with pytest.raises(InvalidURLError):
            validate_server_url("")

    def test_none_url_raises(self):
        """None URL should raise InvalidURLError."""
        with pytest.raises(InvalidURLError):
            validate_server_url(None)  # type: ignore

    def test_no_scheme_raises(self):
        """URL without scheme should raise InvalidURLError."""
        with pytest.raises(InvalidURLError) as exc_info:
            validate_server_url("xnat.example.org")
        assert "scheme" in str(exc_info.value).lower()

    def test_unsupported_scheme_raises(self):
        """Unsupported scheme should raise InvalidURLError."""
        with pytest.raises(InvalidURLError) as exc_info:
            validate_server_url("ftp://xnat.example.org")
        assert "ftp" in str(exc_info.value).lower()

    def test_no_hostname_raises(self):
        """URL without hostname should raise InvalidURLError."""
        with pytest.raises(InvalidURLError):
            validate_server_url("https://")


class TestValidatePort:
    """Tests for validate_port."""

    def test_valid_port_int(self):
        """Valid integer port should pass."""
        assert validate_port(8080) == 8080

    def test_valid_port_string(self):
        """Valid string port should be converted to int."""
        assert validate_port("8080") == 8080

    def test_min_port(self):
        """Port 1 should pass."""
        assert validate_port(1) == 1

    def test_max_port(self):
        """Port 65535 should pass."""
        assert validate_port(65535) == 65535

    def test_port_zero_raises(self):
        """Port 0 should raise InvalidPortError."""
        with pytest.raises(InvalidPortError):
            validate_port(0)

    def test_negative_port_raises(self):
        """Negative port should raise InvalidPortError."""
        with pytest.raises(InvalidPortError):
            validate_port(-1)

    def test_port_too_high_raises(self):
        """Port above 65535 should raise InvalidPortError."""
        with pytest.raises(InvalidPortError):
            validate_port(65536)

    def test_none_with_allow_none(self):
        """None should be allowed when allow_none=True."""
        assert validate_port(None, allow_none=True) is None

    def test_none_without_allow_none_raises(self):
        """None should raise when allow_none=False."""
        with pytest.raises(InvalidPortError):
            validate_port(None, allow_none=False)

    def test_invalid_string_raises(self):
        """Non-numeric string should raise InvalidPortError."""
        with pytest.raises(InvalidPortError):
            validate_port("abc")


class TestValidateXNATIdentifier:
    """Tests for validate_xnat_identifier and related functions."""

    def test_valid_identifier(self):
        """Valid alphanumeric identifier should pass."""
        assert validate_xnat_identifier("PROJ_001") == "PROJ_001"

    def test_valid_with_hyphen(self):
        """Identifier with hyphen should pass."""
        assert validate_xnat_identifier("my-project-123") == "my-project-123"

    def test_strips_whitespace(self):
        """Whitespace should be stripped."""
        assert validate_xnat_identifier("  PROJ001  ") == "PROJ001"

    def test_empty_raises(self):
        """Empty identifier should raise."""
        with pytest.raises(InvalidIdentifierError):
            validate_xnat_identifier("")

    def test_empty_with_allow_empty(self):
        """Empty identifier should pass when allow_empty=True."""
        assert validate_xnat_identifier("", allow_empty=True) == ""

    def test_too_long_raises(self):
        """Identifier exceeding max length should raise."""
        with pytest.raises(InvalidIdentifierError):
            validate_xnat_identifier("a" * 100, max_length=64)

    def test_invalid_characters_raises(self):
        """Identifier with invalid characters should raise."""
        with pytest.raises(InvalidIdentifierError):
            validate_xnat_identifier("project with spaces")

    def test_special_characters_raise(self):
        """Identifier with special characters should raise."""
        with pytest.raises(InvalidIdentifierError):
            validate_xnat_identifier("project@123")

    def test_project_id(self):
        """validate_project_id should work."""
        assert validate_project_id("MY_PROJECT") == "MY_PROJECT"

    def test_subject_id(self):
        """validate_subject_id should work."""
        assert validate_subject_id("SUBJ_001") == "SUBJ_001"

    def test_session_id(self):
        """validate_session_id should work."""
        assert validate_session_id("SESS_001") == "SESS_001"

    def test_scan_id(self):
        """validate_scan_id should work."""
        assert validate_scan_id("1") == "1"
        assert validate_scan_id("SCOUT") == "SCOUT"


class TestValidateResourceLabel:
    """Tests for validate_resource_label."""

    def test_valid_label(self):
        """Valid resource label should pass."""
        assert validate_resource_label("DICOM") == "DICOM"

    def test_label_with_spaces_allowed(self):
        """Resource labels with spaces should be allowed."""
        assert validate_resource_label("My Resource") == "My Resource"

    def test_path_separator_raises(self):
        """Labels with path separators should raise."""
        with pytest.raises(InvalidIdentifierError):
            validate_resource_label("path/to/resource")


class TestValidateAETitle:
    """Tests for validate_ae_title."""

    def test_valid_ae_title(self):
        """Valid AE Title should pass."""
        assert validate_ae_title("XNAT_AET") == "XNAT_AET"

    def test_max_length_16(self):
        """AE Title up to 16 chars should pass."""
        assert validate_ae_title("A" * 16) == "A" * 16

    def test_too_long_raises(self):
        """AE Title over 16 chars should raise."""
        with pytest.raises(InvalidIdentifierError):
            validate_ae_title("A" * 17)

    def test_backslash_raises(self):
        """AE Title with backslash should raise."""
        with pytest.raises(InvalidIdentifierError):
            validate_ae_title("AET\\BAD")


class TestValidatePath:
    """Tests for path validation functions."""

    def test_path_exists(self):
        """validate_path_exists should work for existing paths."""
        with tempfile.NamedTemporaryFile() as f:
            result = validate_path_exists(f.name)
            assert result.exists()

    def test_path_not_exists_raises(self):
        """Non-existent path should raise."""
        with pytest.raises(PathValidationError):
            validate_path_exists("/nonexistent/path/to/file")

    def test_must_be_file(self):
        """must_be_file should reject directories."""
        with tempfile.TemporaryDirectory() as d:
            with pytest.raises(PathValidationError) as exc_info:
                validate_path_exists(d, must_be_file=True)
            assert "must be a file" in str(exc_info.value)

    def test_must_be_dir(self):
        """must_be_dir should reject files."""
        with tempfile.NamedTemporaryFile() as f:
            with pytest.raises(PathValidationError) as exc_info:
                validate_path_exists(f.name, must_be_dir=True)
            assert "must be a directory" in str(exc_info.value)

    def test_path_writable(self):
        """validate_path_writable should work for writable locations."""
        with tempfile.TemporaryDirectory() as d:
            result = validate_path_writable(Path(d) / "new_file.txt")
            assert str(result).endswith("new_file.txt")


class TestValidateTimeout:
    """Tests for validate_timeout."""

    def test_valid_timeout(self):
        """Valid timeout should pass."""
        assert validate_timeout(60, "timeout") == 60

    def test_string_timeout(self):
        """String timeout should be converted."""
        assert validate_timeout("120", "timeout") == 120

    def test_none_uses_default(self):
        """None should return default value."""
        assert validate_timeout(None, "timeout", default=300) == 300

    def test_too_small_raises(self):
        """Timeout below minimum should raise."""
        with pytest.raises(InvalidConfigurationError):
            validate_timeout(0, "timeout", min_value=1)

    def test_too_large_raises(self):
        """Timeout above maximum should raise."""
        with pytest.raises(InvalidConfigurationError):
            validate_timeout(9999999, "timeout", max_value=86400)


class TestValidateWorkers:
    """Tests for validate_workers."""

    def test_valid_workers(self):
        """Valid worker count should pass."""
        assert validate_workers(4, "workers") == 4

    def test_none_uses_default(self):
        """None should return default value."""
        assert validate_workers(None, "workers", default=8) == 8

    def test_below_minimum_raises(self):
        """Worker count below minimum should raise."""
        with pytest.raises(InvalidConfigurationError):
            validate_workers(0, "workers", min_value=1)


class TestValidateOverwriteMode:
    """Tests for validate_overwrite_mode."""

    def test_valid_modes(self):
        """Valid overwrite modes should pass."""
        assert validate_overwrite_mode("none") == "none"
        assert validate_overwrite_mode("append") == "append"
        assert validate_overwrite_mode("delete") == "delete"

    def test_case_insensitive(self):
        """Mode comparison should be case-insensitive."""
        assert validate_overwrite_mode("DELETE") == "delete"
        assert validate_overwrite_mode("Append") == "append"

    def test_invalid_mode_raises(self):
        """Invalid mode should raise."""
        with pytest.raises(InvalidConfigurationError):
            validate_overwrite_mode("replace")


class TestValidateScanIDsInput:
    """Tests for validate_scan_ids_input."""

    def test_wildcard_returns_none(self):
        """'*' should return None (all scans)."""
        assert validate_scan_ids_input("*") is None

    def test_comma_separated(self):
        """Comma-separated IDs should be parsed."""
        result = validate_scan_ids_input("1,2,3")
        assert result == ["1", "2", "3"]

    def test_strips_whitespace(self):
        """Whitespace around IDs should be stripped."""
        result = validate_scan_ids_input("  1 , 2 , 3  ")
        assert result == ["1", "2", "3"]

    def test_single_id(self):
        """Single ID should work."""
        result = validate_scan_ids_input("42")
        assert result == ["42"]


class TestValidateProjectList:
    """Tests for validate_project_list."""

    def test_comma_separated(self):
        """Comma-separated projects should be parsed."""
        result = validate_project_list("PROJ1,PROJ2,PROJ3")
        assert result == ["PROJ1", "PROJ2", "PROJ3"]

    def test_strips_whitespace(self):
        """Whitespace should be stripped."""
        result = validate_project_list(" PROJ1 , PROJ2 ")
        assert result == ["PROJ1", "PROJ2"]


class TestValidateRegexPattern:
    """Tests for validate_regex_pattern."""

    def test_valid_pattern(self):
        """Valid regex should compile."""
        pattern = validate_regex_pattern(r"\d+")
        assert isinstance(pattern, re.Pattern)
        assert pattern.match("123")

    def test_pattern_with_groups(self):
        """Pattern with capture groups should work."""
        pattern = validate_regex_pattern(r"(\w+)_(\d+)")
        match = pattern.match("SUBJ_001")
        assert match is not None
        assert match.group(1) == "SUBJ"
        assert match.group(2) == "001"

    def test_invalid_pattern_raises(self):
        """Invalid regex should raise."""
        with pytest.raises(InvalidConfigurationError) as exc_info:
            validate_regex_pattern("[invalid")
        assert "invalid regex" in str(exc_info.value).lower()
