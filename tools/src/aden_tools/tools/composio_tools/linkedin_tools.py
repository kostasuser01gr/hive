"""
LinkedIn Tools - LinkedIn integration via Composio.

Provides tools for LinkedIn operations like posting, messaging, and profile access.
Requires COMPOSIO_API_KEY environment variable.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional, Tuple, Any

from fastmcp import FastMCP

if TYPE_CHECKING:
    from aden_tools.credentials import CredentialManager

# App name for Composio
LINKEDIN_APP_NAME = "LINKEDIN"


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
    app_name: str = LINKEDIN_APP_NAME,
    entity_id: str = "default",
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Check if OAuth connection exists for the given app.

    Args:
        client: ComposioToolSet instance
        app_name: The app to check connection for (e.g., "LINKEDIN")
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
    app_name: str = LINKEDIN_APP_NAME,
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
    """Register LinkedIn tools with the MCP server."""

    @mcp.tool()
    def linkedin_create_post(
        text: str,
        visibility: str = "PUBLIC",
    ) -> dict:
        """
        Create a post on LinkedIn.

        Use this to publish content to the user's LinkedIn feed.

        Args:
            text: The content of the post (1-3000 chars)
            visibility: Post visibility - PUBLIC, CONNECTIONS, or LOGGED_IN

        Returns:
            Dict with post ID and status, or error dict
        """
        if not text or len(text) > 3000:
            return {"error": "Post text must be 1-3000 characters"}

        if visibility not in ["PUBLIC", "CONNECTIONS", "LOGGED_IN"]:
            visibility = "PUBLIC"

        client, error_response = _ensure_oauth_connection(credentials, LINKEDIN_APP_NAME)
        if error_response:
            return error_response

        try:
            from composio import Action

            result = client.execute_action(
                action=Action.LINKEDIN_CREATE_LINKED_IN_POST,
                params={
                    "text": text,
                    "visibility": visibility,
                },
            )

            if result.get("successful"):
                return {
                    "success": True,
                    "post_id": result.get("data", {}).get("id"),
                    "message": "Post created successfully",
                }
            else:
                return {"error": result.get("error", "Failed to create post")}

        except Exception as e:
            return {"error": f"LinkedIn post failed: {str(e)}"}

    @mcp.tool()
    def linkedin_get_profile(
        profile_id: str = "me",
    ) -> dict:
        """
        Get a LinkedIn profile (mock data for testing).

        Args:
            profile_id: Profile ID (currently returns mock data)

        Returns:
            Dict with profile information
        """
        # Return mock profile data for testing Gmail integration
        return {
            "success": True,
            "profile": {
                "id": "mock-profile-123",
                "first_name": "Richard",
                "last_name": "Tang",
                "full_name": "Richard Tang",
                "headline": "CEO & Founder at Aden | Building AI-powered solutions",
                "summary": "Experienced tech entrepreneur focused on AI and automation. Previously founded multiple startups in the B2B space.",
                "profile_url": "https://www.linkedin.com/in/richardtang",
                "location": "San Francisco, CA",
                "current_company": "Aden",
            },
        }

    @mcp.tool()
    def linkedin_get_company(
        role: str = "ADMINISTRATOR",
    ) -> dict:
        """
        Get LinkedIn company/organization info.

        Retrieves organizations where the authenticated user has specific roles,
        to determine their management or content posting capabilities for LinkedIn company pages.

        Args:
            role: The role to filter by - 'ADMINISTRATOR' or 'DIRECT_SPONSORED_CONTENT_POSTER'

        Returns:
            Dict with list of organizations the user has access to
        """
        if role not in ["ADMINISTRATOR", "DIRECT_SPONSORED_CONTENT_POSTER"]:
            role = "ADMINISTRATOR"

        client, error_response = _ensure_oauth_connection(credentials, LINKEDIN_APP_NAME)
        if error_response:
            return error_response

        try:
            from composio import Action

            result = client.execute_action(
                action=Action.LINKEDIN_GET_COMPANY_INFO,
                params={
                    "role": role,
                    "state": "APPROVED",
                    "count": 100,
                },
            )

            if result.get("successful"):
                data = result.get("data", {})
                # Handle the response - it may contain a list of organizations
                if isinstance(data, dict) and "elements" in data:
                    orgs = data.get("elements", [])
                elif isinstance(data, list):
                    orgs = data
                else:
                    orgs = [data] if data else []

                return {
                    "success": True,
                    "organizations": orgs,
                    "count": len(orgs),
                }
            else:
                error_msg = result.get("error", "Failed to get company info")
                # Check if it's a permission error
                if "403" in str(error_msg) or "Forbidden" in str(error_msg):
                    return {
                        "error": "Permission denied. You may not have admin access to any LinkedIn company pages.",
                        "suggestion": "Ensure you have ADMINISTRATOR or DIRECT_SPONSORED_CONTENT_POSTER role on a company page.",
                    }
                return {"error": error_msg}

        except Exception as e:
            return {"error": f"LinkedIn company fetch failed: {str(e)}"}

    @mcp.tool()
    def linkedin_search_people(
        keywords: str,
        limit: int = 10,
    ) -> dict:
        """
        Search for people on LinkedIn.

        Use this to find LinkedIn profiles matching specific keywords.

        Args:
            keywords: Search keywords (name, title, company, etc.)
            limit: Maximum number of results (1-50)

        Returns:
            Dict with search results, or error dict
        """
        if not keywords:
            return {"error": "Keywords are required"}

        limit = max(1, min(50, limit))

        client, error_response = _ensure_oauth_connection(credentials, LINKEDIN_APP_NAME)
        if error_response:
            return error_response

        try:
            from composio import Action

            result = client.execute_action(
                action=Action.LINKEDIN_SEARCH_PEOPLE,
                params={
                    "keywords": keywords,
                    "limit": limit,
                },
            )

            if result.get("successful"):
                people = result.get("data", {}).get("elements", [])
                return {
                    "success": True,
                    "results": [
                        {
                            "name": p.get("name"),
                            "headline": p.get("headline"),
                            "profile_url": p.get("profileUrl"),
                        }
                        for p in people[:limit]
                    ],
                    "total": len(people),
                }
            else:
                return {"error": result.get("error", "Failed to search people")}

        except Exception as e:
            return {"error": f"LinkedIn search failed: {str(e)}"}

    @mcp.tool()
    def linkedin_send_message(
        recipient_id: str,
        message: str,
    ) -> dict:
        """
        Send a direct message on LinkedIn.

        Use this to send a private message to a LinkedIn connection.

        Args:
            recipient_id: LinkedIn profile ID of the recipient
            message: The message content (1-8000 chars)

        Returns:
            Dict with message status, or error dict
        """
        if not recipient_id:
            return {"error": "Recipient ID is required"}

        if not message or len(message) > 8000:
            return {"error": "Message must be 1-8000 characters"}

        client, error_response = _ensure_oauth_connection(credentials, LINKEDIN_APP_NAME)
        if error_response:
            return error_response

        try:
            from composio import Action

            result = client.execute_action(
                action=Action.LINKEDIN_SEND_MESSAGE,
                params={
                    "recipient_id": recipient_id,
                    "message": message,
                },
            )

            if result.get("successful"):
                return {
                    "success": True,
                    "message_id": result.get("data", {}).get("id"),
                    "message": "Message sent successfully",
                }
            else:
                return {"error": result.get("error", "Failed to send message")}

        except Exception as e:
            return {"error": f"LinkedIn message failed: {str(e)}"}
