"""Tests for xnatio.client module (XNATClient facade)."""

from __future__ import annotations

import logging
from unittest import mock

import pytest

from xnatio.client import XNATClient
from xnatio.config import XNATConfig


class TestXNATClientFromConfig:
    """Tests for XNATClient.from_config method."""

    def test_from_config_basic(self) -> None:
        """Test creating client from basic config."""
        cfg: XNATConfig = {
            "server": "https://xnat.example.com",
            "user": "testuser",
            "password": "testpass",
            "verify_tls": True,
            "http_connect_timeout": 120,
            "http_read_timeout": 604800,
        }

        with mock.patch("xnatio.services.base.Interface"):
            client = XNATClient.from_config(cfg)

        assert client.server == "https://xnat.example.com"
        assert client.username == "testuser"
        assert client.http_timeouts == (120, 604800)

    def test_from_config_custom_timeouts(self) -> None:
        """Test creating client with custom timeouts."""
        cfg: XNATConfig = {
            "server": "https://xnat.example.com",
            "user": "testuser",
            "password": "testpass",
            "verify_tls": False,
            "http_connect_timeout": 60,
            "http_read_timeout": 300,
        }

        with mock.patch("xnatio.services.base.Interface"):
            client = XNATClient.from_config(cfg)

        assert client.http_timeouts == (60, 300)


class TestXNATClientInit:
    """Tests for XNATClient initialization."""

    def test_init_creates_connection(self) -> None:
        """Test that __init__ creates an XNATConnection."""
        with mock.patch("xnatio.services.base.Interface") as mock_interface:
            client = XNATClient(
                server="https://xnat.example.com",
                username="testuser",
                password="testpass",
            )

            mock_interface.assert_called_once()
            assert client.server == "https://xnat.example.com"
            assert client.username == "testuser"

    def test_init_with_custom_logger(self) -> None:
        """Test that custom logger is used."""
        custom_logger = logging.getLogger("custom")

        with mock.patch("xnatio.services.base.Interface"):
            client = XNATClient(
                server="https://xnat.example.com",
                username="testuser",
                password="testpass",
                logger=custom_logger,
            )

        assert client.log is custom_logger


class TestXNATClientServices:
    """Tests for XNATClient service delegation."""

    def test_client_has_connection(self) -> None:
        """Test client exposes connection property."""
        with mock.patch("xnatio.services.base.Interface"):
            client = XNATClient(
                server="https://xnat.example.com",
                username="testuser",
                password="testpass",
            )

        assert client.connection is not None
        assert hasattr(client.connection, "interface")
