"""
Composio Tools - Third-party integrations via Composio.

Provides LinkedIn and Gmail tools powered by Composio.
Requires COMPOSIO_API_KEY environment variable.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from fastmcp import FastMCP

from .linkedin_tools import register_tools as register_linkedin_tools
from .gmail_tools import register_tools as register_gmail_tools

if TYPE_CHECKING:
    from aden_tools.credentials import CredentialManager


def register_tools(
    mcp: FastMCP,
    credentials: Optional["CredentialManager"] = None,
) -> List[str]:
    """
    Register all Composio tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        credentials: Optional CredentialManager for credential access

    Returns:
        List of registered tool names
    """
    register_linkedin_tools(mcp, credentials=credentials)
    register_gmail_tools(mcp, credentials=credentials)

    return [
        # LinkedIn tools
        "linkedin_create_post",
        "linkedin_get_profile",
        "linkedin_search_people",
        "linkedin_send_message",
        # Gmail tools
        "gmail_send_email",
        "gmail_read_emails",
        "gmail_search_emails",
        "gmail_create_draft",
    ]


__all__ = ["register_tools"]
