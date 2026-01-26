"""
Gmail Tools - Gmail integration via Composio.

Provides tools for Gmail operations like sending, reading, and searching emails.
Requires COMPOSIO_API_KEY environment variable.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Optional, Tuple

from fastmcp import FastMCP

if TYPE_CHECKING:
    from aden_tools.credentials import CredentialManager

# App name for Composio
GMAIL_APP_NAME = "GMAIL"


def _get_composio_client(credentials: Optional["CredentialManager"] = None):
    """Get Composio client with API key from credentials or environment."""
    try:
        from composio import ComposioToolSet
    except ImportError:
        return None, "Composio SDK not installed. Run: pip install composio-core"

    if credentials is not None:
        api_key = credentials.get("composio")
    else:
        api_key = os.getenv("COMPOSIO_API_KEY")

    if not api_key:
        return None, "COMPOSIO_API_KEY not set. Get one at https://app.composio.dev/settings"

    return ComposioToolSet(api_key=api_key), None


def _check_oauth_connection(
    client: Any,
    app_name: str = GMAIL_APP_NAME,
    entity_id: str = "default",
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Check if OAuth connection exists for the given app.

    Args:
        client: ComposioToolSet instance
        app_name: The app to check connection for (e.g., "GMAIL")
        entity_id: The entity ID (defaults to "default")

    Returns:
        Tuple of (is_connected, oauth_url, error_message)
        - If connected: (True, None, None)
        - If not connected: (False, oauth_url, None)
        - If error: (False, None, error_message)
    """
    try:
        # Get the entity
        entity = client.get_entity(id=entity_id)

        # Check for existing connection using correct API method
        try:
            # Use get_connection(app=...) - the correct Composio API
            connection = entity.get_connection(app=app_name)
            if connection:
                status = getattr(connection, "status", None)
                if status == "ACTIVE" or status is None:
                    return True, None, None
        except Exception:
            # No connection found, need to initiate OAuth
            pass

        # No active connection, initiate OAuth
        try:
            connection_request = entity.initiate_connection(
                app_name=app_name,
                redirect_url="https://app.composio.dev/connections",
            )
            oauth_url = getattr(connection_request, "redirectUrl", None)
            if oauth_url:
                return False, oauth_url, None
            else:
                # Fallback to Composio dashboard
                return False, f"https://app.composio.dev/app/{app_name.lower()}", None
        except Exception as e:
            # If initiate_connection fails, provide dashboard link
            return False, f"https://app.composio.dev/app/{app_name.lower()}", None

    except Exception as e:
        return False, None, f"Failed to check OAuth connection: {str(e)}"


def _ensure_oauth_connection(
    credentials: Optional["CredentialManager"] = None,
    app_name: str = GMAIL_APP_NAME,
) -> Tuple[Any, Optional[dict]]:
    """
    Ensure OAuth connection exists, return client or OAuth required response.

    Args:
        credentials: Optional CredentialManager
        app_name: The app to check connection for

    Returns:
        Tuple of (client, error_response)
        - If connected: (client, None)
        - If OAuth needed: (None, {"error": ..., "oauth_required": True, "oauth_url": ...})
        - If other error: (None, {"error": ...})
    """
    client, error = _get_composio_client(credentials)
    if error:
        return None, {"error": error}

    is_connected, oauth_url, check_error = _check_oauth_connection(client, app_name)

    if check_error:
        return None, {"error": check_error}

    if not is_connected:
        return None, {
            "error": f"{app_name} OAuth connection required. Please authorize access.",
            "oauth_required": True,
            "oauth_url": oauth_url,
            "message": f"Please visit the following URL to connect your {app_name} account: {oauth_url}",
        }

    return client, None


def register_tools(
    mcp: FastMCP,
    credentials: Optional["CredentialManager"] = None,
) -> None:
    """Register Gmail tools with the MCP server."""

    @mcp.tool()
    def gmail_send_email(
        to: str,
        subject: str,
        body: str,
        cc: str = "",
        bcc: str = "",
    ) -> dict:
        """
        Send an email via Gmail.

        Use this to compose and send an email from the user's Gmail account.

        Args:
            to: Recipient email address(es), comma-separated for multiple
            subject: Email subject line
            body: Email body content (plain text or HTML)
            cc: CC recipients, comma-separated (optional)
            bcc: BCC recipients, comma-separated (optional)

        Returns:
            Dict with message ID and status, or error dict
        """
        if not to:
            return {"error": "Recipient email address is required"}

        if not subject:
            return {"error": "Email subject is required"}

        if not body:
            return {"error": "Email body is required"}

        client, error_response = _ensure_oauth_connection(credentials, GMAIL_APP_NAME)
        if error_response:
            return error_response

        try:
            from composio import Action

            params = {
                "to": to,
                "subject": subject,
                "body": body,
            }
            if cc:
                params["cc"] = cc
            if bcc:
                params["bcc"] = bcc

            result = client.execute_action(
                action=Action.GMAIL_SEND_EMAIL,
                params=params,
            )

            if result.get("successful"):
                return {
                    "success": True,
                    "message_id": result.get("data", {}).get("id"),
                    "thread_id": result.get("data", {}).get("threadId"),
                    "message": "Email sent successfully",
                }
            else:
                return {"error": result.get("error", "Failed to send email")}

        except Exception as e:
            return {"error": f"Gmail send failed: {str(e)}"}

    @mcp.tool()
    def gmail_read_emails(
        max_results: int = 10,
        label: str = "INBOX",
        unread_only: bool = False,
    ) -> dict:
        """
        Read emails from Gmail.

        Use this to fetch emails from the user's Gmail account.

        Args:
            max_results: Maximum number of emails to return (1-100)
            label: Gmail label to read from (INBOX, SENT, DRAFTS, etc.)
            unread_only: If True, only return unread emails

        Returns:
            Dict with list of emails, or error dict
        """
        max_results = max(1, min(100, max_results))

        client, error_response = _ensure_oauth_connection(credentials, GMAIL_APP_NAME)
        if error_response:
            return error_response

        try:
            from composio import Action

            params = {
                "max_results": max_results,
                "label_ids": [label],
            }
            if unread_only:
                params["query"] = "is:unread"

            result = client.execute_action(
                action=Action.GMAIL_FETCH_EMAILS,
                params=params,
            )

            if result.get("successful"):
                messages = result.get("data", {}).get("messages", [])
                return {
                    "success": True,
                    "emails": [
                        {
                            "id": msg.get("id"),
                            "thread_id": msg.get("threadId"),
                            "from": msg.get("from"),
                            "to": msg.get("to"),
                            "subject": msg.get("subject"),
                            "snippet": msg.get("snippet"),
                            "date": msg.get("date"),
                            "is_unread": msg.get("isUnread", False),
                        }
                        for msg in messages[:max_results]
                    ],
                    "total": len(messages),
                }
            else:
                return {"error": result.get("error", "Failed to fetch emails")}

        except Exception as e:
            return {"error": f"Gmail read failed: {str(e)}"}

    @mcp.tool()
    def gmail_search_emails(
        query: str,
        max_results: int = 10,
    ) -> dict:
        """
        Search emails in Gmail.

        Use this to search for emails matching specific criteria.
        Supports Gmail search syntax (from:, to:, subject:, has:attachment, etc.)

        Args:
            query: Gmail search query (e.g., "from:user@example.com subject:meeting")
            max_results: Maximum number of results (1-100)

        Returns:
            Dict with search results, or error dict
        """
        if not query:
            return {"error": "Search query is required"}

        max_results = max(1, min(100, max_results))

        client, error_response = _ensure_oauth_connection(credentials, GMAIL_APP_NAME)
        if error_response:
            return error_response

        try:
            from composio import Action

            result = client.execute_action(
                action=Action.GMAIL_FETCH_EMAILS,
                params={
                    "query": query,
                    "max_results": max_results,
                },
            )

            if result.get("successful"):
                messages = result.get("data", {}).get("messages", [])
                return {
                    "success": True,
                    "results": [
                        {
                            "id": msg.get("id"),
                            "thread_id": msg.get("threadId"),
                            "from": msg.get("from"),
                            "to": msg.get("to"),
                            "subject": msg.get("subject"),
                            "snippet": msg.get("snippet"),
                            "date": msg.get("date"),
                        }
                        for msg in messages[:max_results]
                    ],
                    "total": len(messages),
                    "query": query,
                }
            else:
                return {"error": result.get("error", "Failed to search emails")}

        except Exception as e:
            return {"error": f"Gmail search failed: {str(e)}"}

    @mcp.tool()
    def gmail_create_draft(
        to: str,
        subject: str,
        body: str,
        cc: str = "",
        bcc: str = "",
    ) -> dict:
        """
        Create a draft email in Gmail.

        Use this to save an email as a draft without sending it.

        Args:
            to: Recipient email address(es), comma-separated for multiple
            subject: Email subject line
            body: Email body content (plain text or HTML)
            cc: CC recipients, comma-separated (optional)
            bcc: BCC recipients, comma-separated (optional)

        Returns:
            Dict with draft ID and status, or error dict
        """
        if not to:
            return {"error": "Recipient email address is required"}

        if not subject:
            return {"error": "Email subject is required"}

        client, error_response = _ensure_oauth_connection(credentials, GMAIL_APP_NAME)
        if error_response:
            return error_response

        try:
            from composio import Action

            params = {
                "to": to,
                "subject": subject,
                "body": body or "",
            }
            if cc:
                params["cc"] = cc
            if bcc:
                params["bcc"] = bcc

            result = client.execute_action(
                action=Action.GMAIL_CREATE_EMAIL_DRAFT,
                params=params,
            )

            if result.get("successful"):
                return {
                    "success": True,
                    "draft_id": result.get("data", {}).get("id"),
                    "message": "Draft created successfully",
                }
            else:
                return {"error": result.get("error", "Failed to create draft")}

        except Exception as e:
            return {"error": f"Gmail draft creation failed: {str(e)}"}
