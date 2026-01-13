"""Base XNAT client with connection management and HTTP utilities.

This module provides the foundational XNATConnection class that handles:
- Authentication and session management
- HTTP request/response handling with proper error handling
- Retry logic for transient failures
- Connection health monitoring
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional, Tuple, TypeVar

import requests
from pyxnat import Interface

from ..config import XNATConfig
from ..core import (
    # Exceptions
    AuthenticationError,
    LogContext,
    RetryExhaustedError,
    ServerUnreachableError,
    get_audit_logger,
    get_logger,
    # Validation
    validate_server_url,
    validate_timeout,
)

T = TypeVar("T")

# Default timeout values
DEFAULT_CONNECT_TIMEOUT = 120  # 2 minutes
DEFAULT_READ_TIMEOUT = 604800  # 7 days for large uploads


class XNATConnection:
    """Core XNAT connection and HTTP management.

    This class wraps pyxnat.Interface and provides:
    - Connection lifecycle management
    - Authenticated HTTP requests with proper error handling
    - Retry logic for transient network failures
    - Connection health checks

    Usage:
        conn = XNATConnection.from_config(cfg)
        version = conn.test_connection()

        # Use interface for pyxnat operations
        project = conn.interface.select.project("MYPROJECT")

        # Use HTTP methods for direct API access
        response = conn.get("/data/projects")
    """

    def __init__(
        self,
        server: str,
        username: str,
        password: str,
        *,
        verify_tls: bool = True,
        connect_timeout: int = DEFAULT_CONNECT_TIMEOUT,
        read_timeout: int = DEFAULT_READ_TIMEOUT,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """Initialize XNAT connection.

        Args:
            server: XNAT server URL (e.g., https://xnat.example.org).
            username: XNAT username.
            password: XNAT password.
            verify_tls: Whether to verify TLS certificates.
            connect_timeout: HTTP connection timeout in seconds.
            read_timeout: HTTP read timeout in seconds.
            logger: Optional logger instance.

        Raises:
            InvalidURLError: If server URL is invalid.
        """
        self.server = validate_server_url(server)
        self.username = username
        self._password = password  # Prefixed to discourage direct access
        self.verify_tls = verify_tls
        self.connect_timeout = validate_timeout(connect_timeout, "connect_timeout")
        self.read_timeout = validate_timeout(read_timeout, "read_timeout", max_value=86400 * 30)
        self.log = logger or get_logger(__name__)
        self._audit = get_audit_logger()

        # HTTP timeouts as tuple for requests
        self.http_timeouts: Tuple[int, int] = (self.connect_timeout, self.read_timeout)

        # pyxnat Interface for object API
        self._interface: Optional[Interface] = None

    @property
    def interface(self) -> Interface:
        """Get or create the pyxnat Interface.

        Lazy initialization to defer connection until first use.
        """
        if self._interface is None:
            self._interface = Interface(
                server=self.server,
                user=self.username,
                password=self._password,
                verify=self.verify_tls,
            )
        return self._interface

    @classmethod
    def from_config(cls, cfg: XNATConfig) -> "XNATConnection":
        """Create connection from configuration dictionary.

        Args:
            cfg: Configuration dictionary from load_config().

        Returns:
            Configured XNATConnection instance.
        """
        return cls(
            server=cfg["server"],
            username=cfg["user"],
            password=cfg["password"],
            verify_tls=cfg.get("verify_tls", True),
            connect_timeout=cfg.get("http_connect_timeout", DEFAULT_CONNECT_TIMEOUT),
            read_timeout=cfg.get("http_read_timeout", DEFAULT_READ_TIMEOUT),
        )

    def test_connection(self) -> str:
        """Test connection and return XNAT version.

        Returns:
            XNAT version string.

        Raises:
            ServerUnreachableError: If server cannot be reached.
            AuthenticationError: If credentials are invalid.
        """
        with LogContext("test_connection", self.log, server=self.server):
            try:
                response = self.get(
                    "/xapi/siteConfig/buildInfo",
                    timeout=(30, 30),  # Short timeout for health check
                )
                data = response.json() or {}
                version = data.get("version", "unknown")
                self.log.info("Connected to XNAT %s at %s", version, self.server)
                return str(version)

            except requests.exceptions.ConnectionError as e:
                raise ServerUnreachableError(self.server, e) from e
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code in (401, 403):
                    raise AuthenticationError(self.server) from e
                raise ServerUnreachableError(self.server, e) from e

    # =========================================================================
    # HTTP Methods
    # =========================================================================

    def get(
        self,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        timeout: Optional[Tuple[int, int]] = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> requests.Response:
        """Perform authenticated GET request.

        Args:
            path: API path (e.g., /data/projects).
            params: Query parameters.
            timeout: Optional override for (connect, read) timeout.
            stream: If True, stream response content.
            **kwargs: Additional arguments for requests.

        Returns:
            Response object.

        Raises:
            Various HTTP and network errors.
        """
        return self.interface.get(
            path,
            params=params,
            timeout=timeout or self.http_timeouts,
            stream=stream,
            **kwargs,
        )

    def post(
        self,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        data: Any = None,
        json: Any = None,
        files: Optional[dict[str, Any]] = None,
        timeout: Optional[Tuple[int, int]] = None,
        headers: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Perform authenticated POST request.

        Args:
            path: API path.
            params: Query parameters.
            data: Request body data.
            json: JSON body (alternative to data).
            files: Files to upload.
            timeout: Optional timeout override.
            headers: Additional headers.
            **kwargs: Additional arguments for requests.

        Returns:
            Response object.
        """
        return self.interface.post(
            path,
            params=params,
            data=data,
            json=json,
            files=files,
            timeout=timeout or self.http_timeouts,
            headers=headers,
            **kwargs,
        )

    def put(
        self,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        data: Any = None,
        json: Any = None,
        timeout: Optional[Tuple[int, int]] = None,
        headers: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Perform authenticated PUT request.

        Args:
            path: API path.
            params: Query parameters.
            data: Request body data.
            json: JSON body.
            timeout: Optional timeout override.
            headers: Additional headers.
            **kwargs: Additional arguments for requests.

        Returns:
            Response object.
        """
        return self.interface.put(
            path,
            params=params,
            data=data,
            json=json,
            timeout=timeout or self.http_timeouts,
            headers=headers,
            **kwargs,
        )

    def delete(
        self,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        timeout: Optional[Tuple[int, int]] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Perform authenticated DELETE request.

        Args:
            path: API path.
            params: Query parameters.
            timeout: Optional timeout override.
            **kwargs: Additional arguments for requests.

        Returns:
            Response object.
        """
        return self.interface.delete(
            path,
            params=params,
            timeout=timeout or self.http_timeouts,
            **kwargs,
        )

    # =========================================================================
    # Retry Logic
    # =========================================================================

    def retry_on_network_error(
        self,
        fn: Callable[[], T],
        *,
        max_retries: int = 4,
        backoff_base: float = 2.0,
        operation: str = "operation",
    ) -> T:
        """Execute function with retry logic for transient network failures.

        Retries with exponential backoff (2s, 4s, 8s, 16s by default) when
        network-related exceptions occur.

        Args:
            fn: Function to execute.
            max_retries: Maximum retry attempts.
            backoff_base: Base for exponential backoff in seconds.
            operation: Operation name for logging.

        Returns:
            Return value of fn if successful.

        Raises:
            RetryExhaustedError: If all retries fail.
        """
        last_exc: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                return fn()
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError,
                ConnectionResetError,
                BrokenPipeError,
                OSError,
            ) as e:
                last_exc = e
                if attempt < max_retries:
                    wait_time = backoff_base ** (attempt + 1)
                    self.log.warning(
                        "Network error during %s (attempt %d/%d): %s. Retrying in %.1fs",
                        operation,
                        attempt + 1,
                        max_retries + 1,
                        e,
                        wait_time,
                    )
                    time.sleep(wait_time)
                else:
                    self.log.error(
                        "Network error during %s after %d attempts: %s",
                        operation,
                        max_retries + 1,
                        e,
                    )

        raise RetryExhaustedError(operation, max_retries + 1, last_exc)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def close(self) -> None:
        """Close the connection and release resources."""
        if self._interface is not None:
            try:
                self._interface.disconnect()
            except Exception:
                pass  # Best effort cleanup
            self._interface = None

    def __enter__(self) -> "XNATConnection":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    @property
    def is_connected(self) -> bool:
        """Check if connection is established."""
        return self._interface is not None
