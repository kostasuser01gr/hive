"""
Twitter/X tool credentials.

Contains credentials for Twitter/X API v2 integration.
"""

from .base import CredentialSpec

TWITTER_CREDENTIALS = {
    "twitter": CredentialSpec(
        env_var="TWITTER_BEARER_TOKEN",
        tools=[
            # Tweets
            "twitter_post_tweet",
            "twitter_delete_tweet",
            "twitter_get_tweet",
            "twitter_search_tweets",
            # Engagement
            "twitter_like_tweet",
            "twitter_unlike_tweet",
            "twitter_retweet",
            "twitter_undo_retweet",
            # Users & Following
            "twitter_get_user",
            "twitter_follow_user",
            "twitter_unfollow_user",
            "twitter_get_followers",
            "twitter_get_following",
            # Timeline
            "twitter_get_user_tweets",
            "twitter_get_mentions",
        ],
        required=True,
        startup_required=False,
        help_url="https://developer.twitter.com/en/portal/dashboard",
        description="Twitter/X OAuth2 access token (via Aden) - used for Twitter/X",
        # Auth method support
        aden_supported=True,
        aden_provider_name="twitter",
        direct_api_key_supported=False,
        api_key_instructions="Twitter/X requires OAuth 2.0 User Context. Connect via hive.adenhq.com",
        # Health check configuration
        health_check_endpoint="https://api.twitter.com/2/users/me",
        health_check_method="GET",
        # Credential store mapping
        credential_id="twitter",
        credential_key="access_token",
    ),
}
