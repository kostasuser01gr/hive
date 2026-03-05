"""Tests for DNS Security Scanner tools (FastMCP)."""

from unittest.mock import MagicMock, patch

import pytest
from fastmcp import FastMCP

from aden_tools.tools.dns_security_scanner import register_tools


@pytest.fixture
def dns_tools(mcp: FastMCP):
    """Register DNS tools and return a dict of tool functions."""
    register_tools(mcp)
    tools = mcp._tool_manager._tools
    return {name: tools[name].fn for name in tools}


@pytest.fixture
def scan_fn(dns_tools):
    return dns_tools["dns_security_scan"]


class TestDNSSecurityScan:
    """Tests for dns_security_scan tool."""

    @patch("dns.resolver.Resolver")
    def test_dns_security_scan_basic(self, mock_resolver_class, scan_fn):
        """Test basic DNS security scan with mock records."""
        mock_resolver = mock_resolver_class.return_value

        # Mock responses for different record types
        def mock_resolve(qname, rdtype, **kwargs):
            mock_answer = MagicMock()
            if rdtype == "TXT":
                if str(qname).startswith("_dmarc"):
                    # DMARC record
                    mock_answer.to_text.return_value = '"v=DMARC1; p=reject;"'
                else:
                    # SPF record
                    mock_answer.to_text.return_value = (
                        '"v=spf1 include:_spf.google.com -all"'
                    )
            elif rdtype == "MX":
                mock_answer.preference = 10
                mock_answer.exchange = "mail.example.com"
            elif rdtype == "DNSKEY":
                mock_answer.to_text.return_value = "mock-dnskey"
            elif rdtype == "CAA":
                mock_answer.to_text.return_value = '0 issue "letsencrypt.org"'
            elif rdtype == "NS":
                mock_answer.target = "ns1.example.com"
            else:
                import dns.resolver

                raise dns.resolver.NoAnswer()

            return [mock_answer]

        mock_resolver.resolve.side_effect = mock_resolve

        # Mock zone transfer failure (safe default)
        with patch("dns.zone.from_xfr") as mock_from_xfr:
            mock_from_xfr.return_value = None

            result = scan_fn(domain="example.com")

        assert "domain" in result
        assert result["domain"] == "example.com"
        assert result["spf"]["present"] is True
        assert result["spf"]["policy"] == "hardfail"
        assert result["dmarc"]["present"] is True
        assert result["dmarc"]["policy"] == "reject"
        assert result["dnssec"]["enabled"] is True
        assert result["zone_transfer"]["vulnerable"] is False
        assert "grade_input" in result

    @patch("dns.resolver.Resolver")
    def test_dns_security_scan_missing_records(self, mock_resolver_class, scan_fn):
        """Test scan when no records are found."""
        import dns.resolver

        mock_resolver = mock_resolver_class.return_value
        mock_resolver.resolve.side_effect = dns.resolver.NoAnswer()

        with patch("dns.zone.from_xfr") as mock_from_xfr:
            mock_from_xfr.return_value = None

            result = scan_fn(domain="missing.com")

        assert result["spf"]["present"] is False
        assert result["dmarc"]["present"] is False
        assert result["dnssec"]["enabled"] is False
        assert result["mx_records"] == []
        assert result["caa_records"] == []

    @patch("dns.resolver.Resolver")
    def test_zone_transfer_vulnerability(self, mock_resolver_class, scan_fn):
        """Test detection of zone transfer vulnerability."""
        mock_resolver = mock_resolver_class.return_value

        # Mock NS record
        ns_answer = MagicMock()
        ns_answer.target = "ns1.vulnerable.com"

        # Mock resolve to return NS for the domain, and failure for others
        def mock_resolve(qname, rdtype, **kwargs):
            if rdtype == "NS":
                return [ns_answer]
            import dns.resolver

            raise dns.resolver.NoAnswer()

        mock_resolver.resolve.side_effect = mock_resolve

        # Mock successful AXFR
        mock_zone = MagicMock()
        mock_node = MagicMock()
        mock_zone.nodes = [mock_node, mock_node, mock_node]  # 3 records

        with patch("dns.zone.from_xfr") as mock_from_xfr:
            mock_from_xfr.return_value = mock_zone

            result = scan_fn(domain="vulnerable.com")

        assert result["zone_transfer"]["vulnerable"] is True
        assert result["zone_transfer"]["record_count"] == 3
        assert result["zone_transfer"]["severity"] == "critical"

    @patch("dns.resolver.Resolver")
    def test_domain_cleaning(self, mock_resolver_class, scan_fn):
        """Test that domain input is cleaned correctly."""
        mock_resolver = mock_resolver_class.return_value
        import dns.resolver

        mock_resolver.resolve.side_effect = dns.resolver.NoAnswer()

        with patch("dns.zone.from_xfr") as mock_from_xfr:
            mock_from_xfr.return_value = None

            result = scan_fn(domain="https://example.com/path?query=1")
            assert result["domain"] == "example.com"
