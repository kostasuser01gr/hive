"""
Twitter/X Tool - Post tweets, search, and interact with Twitter/X via API v2.

Uses OAuth 2.0 Bearer Token for authentication (single token for read+write).
Credentials can be provided via Aden OAuth flow or TWITTER_BEARER_TOKEN env var.

API Reference: https://developer.twitter.com/en/docs/twitter-api
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import httpx
from fastmcp import FastMCP

if TYPE_CHECKING:
    from aden_tools.credentials import CredentialStoreAdapter

TWITTER_API_BASE = "https://api.twitter.com/2"


class _TwitterClient:
    """Internal client wrapping Twitter API v2 calls."""

    def __init__(self, bearer_token: str):
        self._token = bearer_token
        self._me_id: str | None = None

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle Twitter API v2 response format."""
        if response.status_code == 429:
            reset = response.headers.get("x-rate-limit-reset", "unknown")
            return {"error": f"Rate limited. Resets at timestamp: {reset}"}
        if response.status_code == 401:
            return {"error": "Invalid or expired Twitter token"}
        if response.status_code == 403:
            return {"error": "Forbidden - check token permissions (need read+write scope)"}
        if response.status_code not in (200, 201, 204):
            try:
                err = response.json()
                errors = err.get("errors", [])
                msg = errors[0].get("message") if errors else err.get("detail", response.text)
            except Exception:
                msg = response.text
            return {"error": f"Twitter API error ({response.status_code}): {msg}"}
        if response.status_code == 204:
            return {"success": True}
        return response.json()

    def _get_me_id(self) -> str | dict[str, Any]:
        """Get the authenticated user's ID (lazy-cached)."""
        if self._me_id is not None:
            return self._me_id
        response = httpx.get(
            f"{TWITTER_API_BASE}/users/me",
            headers=self._headers,
            timeout=30.0,
        )
        result = self._handle_response(response)
        if "error" in result:
            return result
        self._me_id = result["data"]["id"]
        return self._me_id

    # --- Tweets ---

    def post_tweet(self, text: str, reply_to: str | None = None) -> dict[str, Any]:
        """Create a tweet."""
        body: dict[str, Any] = {"text": text}
        if reply_to:
            body["reply"] = {"in_reply_to_tweet_id": reply_to}
        response = httpx.post(
            f"{TWITTER_API_BASE}/tweets",
            headers=self._headers,
            json=body,
            timeout=30.0,
        )
        return self._handle_response(response)

    def delete_tweet(self, tweet_id: str) -> dict[str, Any]:
        """Delete a tweet by ID."""
        response = httpx.delete(
            f"{TWITTER_API_BASE}/tweets/{tweet_id}",
            headers=self._headers,
            timeout=30.0,
        )
        return self._handle_response(response)

    def get_tweet(
        self,
        tweet_id: str,
        tweet_fields: str = "created_at,author_id,public_metrics",
    ) -> dict[str, Any]:
        """Get a single tweet by ID."""
        response = httpx.get(
            f"{TWITTER_API_BASE}/tweets/{tweet_id}",
            headers=self._headers,
            params={"tweet.fields": tweet_fields},
            timeout=30.0,
        )
        return self._handle_response(response)

    def search_tweets(
        self,
        query: str,
        max_results: int = 10,
        tweet_fields: str = "created_at,author_id,public_metrics",
    ) -> dict[str, Any]:
        """Search recent tweets (last 7 days)."""
        response = httpx.get(
            f"{TWITTER_API_BASE}/tweets/search/recent",
            headers=self._headers,
            params={
                "query": query,
                "max_results": max(10, min(max_results, 100)),
                "tweet.fields": tweet_fields,
            },
            timeout=30.0,
        )
        return self._handle_response(response)

    # --- Engagement ---

    def like_tweet(self, tweet_id: str) -> dict[str, Any]:
        """Like a tweet."""
        me_id = self._get_me_id()
        if isinstance(me_id, dict):
            return me_id
        response = httpx.post(
            f"{TWITTER_API_BASE}/users/{me_id}/likes",
            headers=self._headers,
            json={"tweet_id": tweet_id},
            timeout=30.0,
        )
        return self._handle_response(response)

    def unlike_tweet(self, tweet_id: str) -> dict[str, Any]:
        """Unlike a tweet."""
        me_id = self._get_me_id()
        if isinstance(me_id, dict):
            return me_id
        response = httpx.delete(
            f"{TWITTER_API_BASE}/users/{me_id}/likes/{tweet_id}",
            headers=self._headers,
            timeout=30.0,
        )
        return self._handle_response(response)

    def retweet(self, tweet_id: str) -> dict[str, Any]:
        """Retweet a tweet."""
        me_id = self._get_me_id()
        if isinstance(me_id, dict):
            return me_id
        response = httpx.post(
            f"{TWITTER_API_BASE}/users/{me_id}/retweets",
            headers=self._headers,
            json={"tweet_id": tweet_id},
            timeout=30.0,
        )
        return self._handle_response(response)

    def undo_retweet(self, tweet_id: str) -> dict[str, Any]:
        """Undo a retweet."""
        me_id = self._get_me_id()
        if isinstance(me_id, dict):
            return me_id
        response = httpx.delete(
            f"{TWITTER_API_BASE}/users/{me_id}/retweets/{tweet_id}",
            headers=self._headers,
            timeout=30.0,
        )
        return self._handle_response(response)

    # --- Users & Following ---

    def get_user(self, username: str) -> dict[str, Any]:
        """Get user profile by username."""
        response = httpx.get(
            f"{TWITTER_API_BASE}/users/by/username/{username}",
            headers=self._headers,
            params={"user.fields": "created_at,description,public_metrics,verified"},
            timeout=30.0,
        )
        return self._handle_response(response)

    def follow_user(self, target_user_id: str) -> dict[str, Any]:
        """Follow a user."""
        me_id = self._get_me_id()
        if isinstance(me_id, dict):
            return me_id
        response = httpx.post(
            f"{TWITTER_API_BASE}/users/{me_id}/following",
            headers=self._headers,
            json={"target_user_id": target_user_id},
            timeout=30.0,
        )
        return self._handle_response(response)

    def unfollow_user(self, target_user_id: str) -> dict[str, Any]:
        """Unfollow a user."""
        me_id = self._get_me_id()
        if isinstance(me_id, dict):
            return me_id
        response = httpx.delete(
            f"{TWITTER_API_BASE}/users/{me_id}/following/{target_user_id}",
            headers=self._headers,
            timeout=30.0,
        )
        return self._handle_response(response)

    def get_followers(
        self,
        user_id: str,
        max_results: int = 100,
        pagination_token: str | None = None,
    ) -> dict[str, Any]:
        """Get followers of a user."""
        params: dict[str, Any] = {
            "max_results": min(max_results, 1000),
            "user.fields": "created_at,description,public_metrics",
        }
        if pagination_token:
            params["pagination_token"] = pagination_token
        response = httpx.get(
            f"{TWITTER_API_BASE}/users/{user_id}/followers",
            headers=self._headers,
            params=params,
            timeout=30.0,
        )
        return self._handle_response(response)

    def get_following(
        self,
        user_id: str,
        max_results: int = 100,
        pagination_token: str | None = None,
    ) -> dict[str, Any]:
        """Get users that a user is following."""
        params: dict[str, Any] = {
            "max_results": min(max_results, 1000),
            "user.fields": "created_at,description,public_metrics",
        }
        if pagination_token:
            params["pagination_token"] = pagination_token
        response = httpx.get(
            f"{TWITTER_API_BASE}/users/{user_id}/following",
            headers=self._headers,
            params=params,
            timeout=30.0,
        )
        return self._handle_response(response)

    # --- Timeline ---

    def get_user_tweets(
        self,
        user_id: str,
        max_results: int = 10,
        pagination_token: str | None = None,
        tweet_fields: str = "created_at,public_metrics",
    ) -> dict[str, Any]:
        """Get recent tweets from a user."""
        params: dict[str, Any] = {
            "max_results": max(5, min(max_results, 100)),
            "tweet.fields": tweet_fields,
        }
        if pagination_token:
            params["pagination_token"] = pagination_token
        response = httpx.get(
            f"{TWITTER_API_BASE}/users/{user_id}/tweets",
            headers=self._headers,
            params=params,
            timeout=30.0,
        )
        return self._handle_response(response)

    def get_mentions(
        self,
        user_id: str,
        max_results: int = 10,
        pagination_token: str | None = None,
        tweet_fields: str = "created_at,author_id,public_metrics",
    ) -> dict[str, Any]:
        """Get recent mentions of a user."""
        params: dict[str, Any] = {
            "max_results": max(5, min(max_results, 100)),
            "tweet.fields": tweet_fields,
        }
        if pagination_token:
            params["pagination_token"] = pagination_token
        response = httpx.get(
            f"{TWITTER_API_BASE}/users/{user_id}/mentions",
            headers=self._headers,
            params=params,
            timeout=30.0,
        )
        return self._handle_response(response)


def register_tools(
    mcp: FastMCP,
    credentials: CredentialStoreAdapter | None = None,
) -> None:
    """Register Twitter/X tools with the MCP server."""

    def _get_token() -> str | None:
        """Get Twitter token from credential store or environment."""
        if credentials is not None:
            token = credentials.get("twitter")
            if token is not None and not isinstance(token, str):
                raise TypeError(
                    f"Expected string from credentials.get('twitter'), got {type(token).__name__}"
                )
            return token
        return os.getenv("TWITTER_BEARER_TOKEN")

    def _get_client() -> _TwitterClient | dict[str, str]:
        """Get a Twitter client, or return an error dict if no credentials."""
        token = _get_token()
        if not token:
            return {
                "error": "Twitter credentials not configured",
                "help": (
                    "Set TWITTER_BEARER_TOKEN environment variable "
                    "or connect Twitter via hive.adenhq.com"
                ),
            }
        return _TwitterClient(token)

    # --- Tweets ---

    @mcp.tool()
    def twitter_post_tweet(
        text: str,
        reply_to: str = "",
    ) -> dict:
        """
        Post a tweet to Twitter/X. Supports threading via reply_to.

        Args:
            text: The tweet text (up to 280 characters).
            reply_to: Optional tweet ID to reply to (for creating threads).

        Returns:
            Dict with tweet data (id, text) on success, or error dict.
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            result = client.post_tweet(text, reply_to=reply_to or None)
            if "error" in result:
                return result
            data = result.get("data", {})
            return {"success": True, "tweet_id": data.get("id"), "text": data.get("text")}
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}

    @mcp.tool()
    def twitter_delete_tweet(tweet_id: str) -> dict:
        """
        Delete a tweet by ID.

        Args:
            tweet_id: The ID of the tweet to delete (must be owned by authenticated user).

        Returns:
            Dict with deletion confirmation or error.
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            result = client.delete_tweet(tweet_id)
            if "error" in result:
                return result
            deleted = result.get("data", {}).get("deleted", False)
            return {"success": True, "deleted": deleted}
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}

    @mcp.tool()
    def twitter_get_tweet(
        tweet_id: str,
        tweet_fields: str = "created_at,author_id,public_metrics",
    ) -> dict:
        """
        Get a single tweet by ID.

        Args:
            tweet_id: The ID of the tweet to retrieve.
            tweet_fields: Comma-separated fields to include (default: created_at,author_id,public_metrics).

        Returns:
            Dict with tweet data or error.
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            result = client.get_tweet(tweet_id, tweet_fields=tweet_fields)
            if "error" in result:
                return result
            return result
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}

    @mcp.tool()
    def twitter_search_tweets(
        query: str,
        max_results: int = 10,
        tweet_fields: str = "created_at,author_id,public_metrics",
    ) -> dict:
        """
        Search recent tweets (last 7 days).

        Args:
            query: Search query (supports Twitter operators like "from:", "#hashtag", etc.).
            max_results: Number of results to return (10-100, default 10).
            tweet_fields: Comma-separated fields to include.

        Returns:
            Dict with matching tweets and metadata, or error.
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            result = client.search_tweets(query, max_results=max_results, tweet_fields=tweet_fields)
            if "error" in result:
                return result
            return result
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}

    # --- Engagement ---

    @mcp.tool()
    def twitter_like_tweet(tweet_id: str) -> dict:
        """
        Like a tweet.

        Args:
            tweet_id: The ID of the tweet to like.

        Returns:
            Dict with like confirmation or error.
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            result = client.like_tweet(tweet_id)
            if "error" in result:
                return result
            liked = result.get("data", {}).get("liked", False)
            return {"success": True, "liked": liked}
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}

    @mcp.tool()
    def twitter_unlike_tweet(tweet_id: str) -> dict:
        """
        Unlike a previously liked tweet.

        Args:
            tweet_id: The ID of the tweet to unlike.

        Returns:
            Dict with unlike confirmation or error.
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            result = client.unlike_tweet(tweet_id)
            if "error" in result:
                return result
            liked = result.get("data", {}).get("liked", False)
            return {"success": True, "liked": liked}
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}

    @mcp.tool()
    def twitter_retweet(tweet_id: str) -> dict:
        """
        Retweet a tweet.

        Args:
            tweet_id: The ID of the tweet to retweet.

        Returns:
            Dict with retweet confirmation or error.
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            result = client.retweet(tweet_id)
            if "error" in result:
                return result
            retweeted = result.get("data", {}).get("retweeted", False)
            return {"success": True, "retweeted": retweeted}
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}

    @mcp.tool()
    def twitter_undo_retweet(tweet_id: str) -> dict:
        """
        Undo a retweet.

        Args:
            tweet_id: The ID of the tweet to un-retweet.

        Returns:
            Dict with confirmation or error.
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            result = client.undo_retweet(tweet_id)
            if "error" in result:
                return result
            retweeted = result.get("data", {}).get("retweeted", False)
            return {"success": True, "retweeted": retweeted}
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}

    # --- Users & Following ---

    @mcp.tool()
    def twitter_get_user(username: str) -> dict:
        """
        Get a Twitter/X user profile by username.

        Args:
            username: The Twitter username (without @).

        Returns:
            Dict with user data (id, name, username, description, public_metrics) or error.
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            result = client.get_user(username)
            if "error" in result:
                return result
            return result
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}

    @mcp.tool()
    def twitter_follow_user(target_user_id: str) -> dict:
        """
        Follow a user.

        Args:
            target_user_id: The numeric user ID to follow (use twitter_get_user to find IDs).

        Returns:
            Dict with follow confirmation or error.
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            result = client.follow_user(target_user_id)
            if "error" in result:
                return result
            following = result.get("data", {}).get("following", False)
            return {"success": True, "following": following}
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}

    @mcp.tool()
    def twitter_unfollow_user(target_user_id: str) -> dict:
        """
        Unfollow a user.

        Args:
            target_user_id: The numeric user ID to unfollow.

        Returns:
            Dict with unfollow confirmation or error.
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            result = client.unfollow_user(target_user_id)
            if "error" in result:
                return result
            following = result.get("data", {}).get("following", True)
            return {"success": True, "following": following}
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}

    @mcp.tool()
    def twitter_get_followers(
        user_id: str,
        max_results: int = 100,
        pagination_token: str = "",
    ) -> dict:
        """
        Get followers of a user.

        Args:
            user_id: The numeric user ID whose followers to retrieve.
            max_results: Number of results per page (1-1000, default 100).
            pagination_token: Token for pagination (from previous response's meta.next_token).

        Returns:
            Dict with list of followers and pagination metadata, or error.
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            result = client.get_followers(
                user_id,
                max_results=max_results,
                pagination_token=pagination_token or None,
            )
            if "error" in result:
                return result
            return result
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}

    @mcp.tool()
    def twitter_get_following(
        user_id: str,
        max_results: int = 100,
        pagination_token: str = "",
    ) -> dict:
        """
        Get users that a user is following.

        Args:
            user_id: The numeric user ID whose following list to retrieve.
            max_results: Number of results per page (1-1000, default 100).
            pagination_token: Token for pagination (from previous response's meta.next_token).

        Returns:
            Dict with list of followed users and pagination metadata, or error.
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            result = client.get_following(
                user_id,
                max_results=max_results,
                pagination_token=pagination_token or None,
            )
            if "error" in result:
                return result
            return result
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}

    # --- Timeline ---

    @mcp.tool()
    def twitter_get_user_tweets(
        user_id: str,
        max_results: int = 10,
        pagination_token: str = "",
        tweet_fields: str = "created_at,public_metrics",
    ) -> dict:
        """
        Get recent tweets from a user.

        Args:
            user_id: The numeric user ID whose tweets to retrieve.
            max_results: Number of results (5-100, default 10).
            pagination_token: Token for pagination.
            tweet_fields: Comma-separated fields to include.

        Returns:
            Dict with list of tweets and pagination metadata, or error.
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            result = client.get_user_tweets(
                user_id,
                max_results=max_results,
                pagination_token=pagination_token or None,
                tweet_fields=tweet_fields,
            )
            if "error" in result:
                return result
            return result
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}

    @mcp.tool()
    def twitter_get_mentions(
        user_id: str,
        max_results: int = 10,
        pagination_token: str = "",
        tweet_fields: str = "created_at,author_id,public_metrics",
    ) -> dict:
        """
        Get recent mentions of a user.

        Args:
            user_id: The numeric user ID whose mentions to retrieve.
            max_results: Number of results (5-100, default 10).
            pagination_token: Token for pagination.
            tweet_fields: Comma-separated fields to include.

        Returns:
            Dict with list of mention tweets and pagination metadata, or error.
        """
        client = _get_client()
        if isinstance(client, dict):
            return client
        try:
            result = client.get_mentions(
                user_id,
                max_results=max_results,
                pagination_token=pagination_token or None,
                tweet_fields=tweet_fields,
            )
            if "error" in result:
                return result
            return result
        except httpx.TimeoutException:
            return {"error": "Request timed out"}
        except httpx.RequestError as e:
            return {"error": f"Network error: {e}"}
