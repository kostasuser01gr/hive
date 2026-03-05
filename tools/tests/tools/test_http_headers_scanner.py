"""Tests for HTTP Headers Scanner tools (FastMCP)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastmcp import FastMCP

from aden_tools.tools.http_headers_scanner import register_tools


@pytest.fixture
def headers_tools(mcp: FastMCP):
    """Register HTTP headers tools and return a dict of tool functions."""
    register_tools(mcp)
    tools = mcp._tool_manager._tools
    return {name: tools[name].fn for name in tools}


@pytest.fixture
def scan_fn(headers_tools):
    return headers_tools["http_headers_scan"]


class TestHTTPHeadersScan:
    """Tests for http_headers_scan tool."""

    @pytest.mark.asyncio
    async def test_http_headers_scan_basic(self, scan_fn):
        """Test basic HTTP headers scan with mock response."""
        mock_headers = {
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'",
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "geolocation=()",
            "X-XSS-Protection": "1; mode=block",
        }

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.headers = httpx.Headers(mock_headers)
        mock_response.status_code = 200
        mock_response.url = httpx.URL("https://example.com")

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await scan_fn(url="example.com")

        assert result["status_code"] == 200
        assert "Strict-Transport-Security" in result["headers_present"]
        assert "Content-Security-Policy" in result["headers_present"]
        assert len(result["headers_missing"]) == 0
        assert result["grade_input"]["hsts"] is True
        assert result["grade_input"]["csp"] is True

    @pytest.mark.asyncio
    async def test_http_headers_scan_missing_headers(self, scan_fn):
        """Test scan when security headers are missing."""
        mock_headers = {"Server": "Apache/2.4.41 (Ubuntu)", "X-Powered-By": "PHP/7.4.3"}

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.headers = httpx.Headers(mock_headers)
        mock_response.status_code = 200
        mock_response.url = httpx.URL("https://insecure.com")

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await scan_fn(url="insecure.com")

        assert len(result["headers_present"]) == 0
        assert len(result["headers_missing"]) > 0
        assert len(result["leaky_headers"]) == 2
        assert result["grade_input"]["hsts"] is False
        assert result["grade_input"]["no_leaky_headers"] is False

    @pytest.mark.asyncio
    async def test_http_headers_scan_connection_error(self, scan_fn):
        """Test scan when connection fails."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")

            result = await scan_fn(url="offline.com")

        assert "error" in result
        assert "Connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_url_prefixing(self, scan_fn):
        """Test that URL is auto-prefixed with https:// if missing."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.headers = httpx.Headers({})
        mock_response.status_code = 200
        mock_response.url = httpx.URL("https://example.com")

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            await scan_fn(url="example.com")
            mock_get.assert_called_once()
            args, _ = mock_get.call_args
            assert args[0] == "https://example.com"
