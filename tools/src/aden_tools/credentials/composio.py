"""
Composio credentials for third-party integrations.

Contains credentials for Composio-powered tools like LinkedIn, Gmail, etc.
"""
from .base import CredentialSpec

COMPOSIO_CREDENTIALS = {
    "composio": CredentialSpec(
        env_var="COMPOSIO_API_KEY",
        tools=[
            "linkedin_create_post",
            "linkedin_get_profile",
            "linkedin_search_people",
            "linkedin_send_message",
            "gmail_send_email",
            "gmail_read_emails",
            "gmail_search_emails",
            "gmail_create_draft",
        ],
        node_types=[],
        required=True,
        startup_required=False,
        help_url="https://app.composio.dev/settings",
        description="API key for Composio (enables LinkedIn, Gmail, and other integrations)",
    ),
}
