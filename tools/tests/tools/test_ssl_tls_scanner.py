"""Tests for SSL/TLS Scanner tools (FastMCP)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastmcp import FastMCP

from aden_tools.tools.ssl_tls_scanner import register_tools


@pytest.fixture
def ssl_tools(mcp: FastMCP):
    """Register SSL tools and return a dict of tool functions."""
    register_tools(mcp)
    tools = mcp._tool_manager._tools
    return {name: tools[name].fn for name in tools}


@pytest.fixture
def scan_fn(ssl_tools):
    return ssl_tools["ssl_tls_scan"]


class TestSSLTLSScan:
    """Tests for ssl_tls_scan tool."""

    @patch("ssl.create_default_context")
    @patch("socket.socket")
    def test_ssl_tls_scan_basic(self, mock_socket, mock_create_context, scan_fn):
        """Test basic SSL/TLS scan with mock certificate."""
        mock_context = mock_create_context.return_value
        mock_sslsock = mock_context.wrap_socket.return_value

        # Mock TLS info
        mock_sslsock.version.return_value = "TLSv1.3"
        mock_sslsock.cipher.return_value = ("TLS_AES_256_GCM_SHA384", "TLSv1.3", 256)

        # Mock certificate
        expiry_date = datetime.now(UTC) + timedelta(days=90)
        not_after_str = expiry_date.strftime("%b %d %H:%M:%S %Y GMT")
        not_before_str = (datetime.now(UTC) - timedelta(days=10)).strftime(
            "%b %d %H:%M:%S %Y GMT"
        )

        mock_cert = {
            "subject": ((("commonName", "example.com"),),),
            "issuer": ((("commonName", "DigiCert Global Root CA"),),),
            "notBefore": not_before_str,
            "notAfter": not_after_str,
            "subjectAltName": (("DNS", "example.com"), ("DNS", "www.example.com")),
        }
        mock_sslsock.getpeercert.side_effect = [b"binary-cert-data", mock_cert]

        result = scan_fn(hostname="example.com")

        assert result["hostname"] == "example.com"
        assert result["tls_version"] == "TLSv1.3"
        assert result["cipher"] == "TLS_AES_256_GCM_SHA384"
        assert result["certificate"]["subject"] == "commonName=example.com"
        assert result["certificate"]["days_until_expiry"] >= 89
        assert result["grade_input"]["tls_version_ok"] is True
        assert result["grade_input"]["cert_valid"] is True

    @patch("ssl.create_default_context")
    @patch("socket.socket")
    def test_ssl_tls_scan_expired_cert(self, mock_socket, mock_create_context, scan_fn):
        """Test scan with an expired certificate."""
        mock_context = mock_create_context.return_value
        mock_sslsock = mock_context.wrap_socket.return_value

        mock_sslsock.version.return_value = "TLSv1.2"
        mock_sslsock.cipher.return_value = (
            "ECDHE-RSA-AES128-GCM-SHA256",
            "TLSv1.2",
            128,
        )

        expired_date = datetime.now(UTC) - timedelta(days=1)
        not_after_str = expired_date.strftime("%b %d %H:%M:%S %Y GMT")

        mock_cert = {
            "subject": ((("commonName", "expired.com"),),),
            "issuer": ((("commonName", "DigiCert"),),),
            "notAfter": not_after_str,
        }
        mock_sslsock.getpeercert.side_effect = [b"data", mock_cert]

        result = scan_fn(hostname="expired.com")

        assert result["grade_input"]["cert_valid"] is False
        assert any(
            issue["finding"] == "SSL certificate has expired"
            for issue in result["issues"]
        )

    @patch("ssl.create_default_context")
    @patch("socket.socket")
    def test_ssl_tls_scan_insecure_version(
        self, mock_socket, mock_create_context, scan_fn
    ):
        """Test scan with insecure TLS version."""
        mock_context = mock_create_context.return_value
        mock_sslsock = mock_context.wrap_socket.return_value

        mock_sslsock.version.return_value = "TLSv1.1"
        mock_sslsock.cipher.return_value = ("AES128-SHA", "TLSv1.1", 128)
        mock_sslsock.getpeercert.side_effect = [b"data", {}]

        result = scan_fn(hostname="insecure.com")

        assert result["grade_input"]["tls_version_ok"] is False
        assert any(
            "Insecure TLS version" in issue["finding"] for issue in result["issues"]
        )

    @patch("ssl.create_default_context")
    @patch("socket.socket")
    def test_ssl_tls_scan_connection_timeout(
        self, mock_socket, mock_create_context, scan_fn
    ):
        """Test scan when connection times out."""
        mock_socket.return_value.connect.side_effect = TimeoutError()

        # We need to mock the wrap_socket call chain
        mock_create_context.return_value.wrap_socket.return_value.connect.side_effect = (
            TimeoutError()
        )

        result = scan_fn(hostname="timeout.com")
        assert "error" in result
        assert "timed out" in result["error"]
