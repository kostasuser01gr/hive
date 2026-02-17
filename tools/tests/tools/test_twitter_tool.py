"""
End-to-end test for Twitter tools against the live Twitter API.

Uses Aden credentials (ADEN_API_KEY must be set).

Tests the full lifecycle:
  1. Get authenticated user profile (/users/me)
  2. Post a tweet
  3. Get the posted tweet back
  4. Like the tweet
  5. Unlike the tweet
  6. Retweet the tweet
  7. Undo the retweet
  8. Search for recent tweets
  9. Get user tweets timeline
  10. Get mentions
  11. Delete the test tweet (cleanup)
"""

from __future__ import annotations

import sys
import time

from fastmcp import FastMCP
from aden_tools.credentials.store_adapter import CredentialStoreAdapter
from aden_tools.tools.twitter_tool import register_tools

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


def setup():
    """Create MCP server with real Aden credentials and return tool getter."""
    adapter = CredentialStoreAdapter.default()

    if not adapter.is_available("twitter"):
        print("ERROR: Twitter credential not available.")
        print("Make sure ADEN_API_KEY is set and Twitter is connected in Aden.")
        sys.exit(1)

    token = adapter.get("twitter")
    masked = token[:8] + "..." + token[-4:] if len(token) > 16 else "***"
    print(f"Twitter token resolved: {masked} (length={len(token)})\n")

    mcp = FastMCP("twitter-test")
    register_tools(mcp, credentials=adapter)

    def get_tool(name: str):
        return mcp._tool_manager._tools[name].fn

    return get_tool


def report(test_name, result, details=""):
    status = PASS if result else FAIL
    print(f"  [{status}] {test_name}")
    if details:
        print(f"         {details}")
    return result


def main():
    get_tool = setup()
    results = {}
    tweet_id = None
    user_id = None

    # --- 1. Get authenticated user ---
    print("--- Test: twitter_get_user (self lookup) ---")
    try:
        # First get our own username via a raw /users/me call through the get_user tool
        # We need the user_id for later tests, so let's get a known user first
        # Actually, the tool takes a username. We'll test with a public account.
        fn = get_tool("twitter_get_user")
        result = fn(username="twitter")  # @twitter is always there
        if "error" in result:
            report("twitter_get_user", False, f"Error: {result['error']}")
            results["get_user"] = False
        else:
            data = result.get("data", {})
            user_id = data.get("id")
            report("twitter_get_user", True, f"Found @{data.get('username')} (id={user_id})")
            results["get_user"] = True
    except Exception as e:
        report("twitter_get_user", False, f"Exception: {e}")
        results["get_user"] = False

    # --- 2. Post a tweet ---
    print("\n--- Test: twitter_post_tweet ---")
    try:
        fn = get_tool("twitter_post_tweet")
        ts = int(time.time())
        test_text = f"Automated test tweet from Hive agent framework - {ts} (will be deleted)"
        result = fn(text=test_text)
        if "error" in result:
            report("twitter_post_tweet", False, f"Error: {result['error']}")
            results["post_tweet"] = False
        else:
            tweet_id = result.get("tweet_id")
            report("twitter_post_tweet", True, f"Posted tweet_id={tweet_id}")
            results["post_tweet"] = True
    except Exception as e:
        report("twitter_post_tweet", False, f"Exception: {e}")
        results["post_tweet"] = False

    if not tweet_id:
        print("\nCannot continue without a posted tweet. Skipping remaining tests.")
        _print_summary(results)
        return

    # Small delay to let Twitter propagate
    time.sleep(2)

    # --- 3. Get the posted tweet ---
    print("\n--- Test: twitter_get_tweet ---")
    try:
        fn = get_tool("twitter_get_tweet")
        result = fn(tweet_id=tweet_id)
        if "error" in result:
            report("twitter_get_tweet", False, f"Error: {result['error']}")
            results["get_tweet"] = False
        else:
            data = result.get("data", {})
            report("twitter_get_tweet", True, f"Retrieved: '{data.get('text', '')[:60]}...'")
            results["get_tweet"] = True
    except Exception as e:
        report("twitter_get_tweet", False, f"Exception: {e}")
        results["get_tweet"] = False

    # --- 4. Like the tweet ---
    print("\n--- Test: twitter_like_tweet ---")
    try:
        fn = get_tool("twitter_like_tweet")
        result = fn(tweet_id=tweet_id)
        if "error" in result:
            report("twitter_like_tweet", False, f"Error: {result['error']}")
            results["like_tweet"] = False
        else:
            report("twitter_like_tweet", True, f"liked={result.get('liked')}")
            results["like_tweet"] = True
    except Exception as e:
        report("twitter_like_tweet", False, f"Exception: {e}")
        results["like_tweet"] = False

    # --- 5. Unlike the tweet ---
    print("\n--- Test: twitter_unlike_tweet ---")
    try:
        fn = get_tool("twitter_unlike_tweet")
        result = fn(tweet_id=tweet_id)
        if "error" in result:
            report("twitter_unlike_tweet", False, f"Error: {result['error']}")
            results["unlike_tweet"] = False
        else:
            report("twitter_unlike_tweet", True, f"liked={result.get('liked')}")
            results["unlike_tweet"] = True
    except Exception as e:
        report("twitter_unlike_tweet", False, f"Exception: {e}")
        results["unlike_tweet"] = False

    # --- 6. Retweet ---
    print("\n--- Test: twitter_retweet ---")
    try:
        fn = get_tool("twitter_retweet")
        result = fn(tweet_id=tweet_id)
        if "error" in result:
            report("twitter_retweet", False, f"Error: {result['error']}")
            results["retweet"] = False
        else:
            report("twitter_retweet", True, f"retweeted={result.get('retweeted')}")
            results["retweet"] = True
    except Exception as e:
        report("twitter_retweet", False, f"Exception: {e}")
        results["retweet"] = False

    # --- 7. Undo retweet ---
    print("\n--- Test: twitter_undo_retweet ---")
    try:
        fn = get_tool("twitter_undo_retweet")
        result = fn(tweet_id=tweet_id)
        if "error" in result:
            report("twitter_undo_retweet", False, f"Error: {result['error']}")
            results["undo_retweet"] = False
        else:
            report("twitter_undo_retweet", True, f"retweeted={result.get('retweeted')}")
            results["undo_retweet"] = True
    except Exception as e:
        report("twitter_undo_retweet", False, f"Exception: {e}")
        results["undo_retweet"] = False

    # --- 8. Search tweets ---
    print("\n--- Test: twitter_search_tweets ---")
    try:
        fn = get_tool("twitter_search_tweets")
        result = fn(query="python programming", max_results=10)
        if "error" in result:
            report("twitter_search_tweets", False, f"Error: {result['error']}")
            results["search_tweets"] = False
        else:
            count = len(result.get("data", []))
            report("twitter_search_tweets", True, f"Found {count} tweets")
            results["search_tweets"] = True
    except Exception as e:
        report("twitter_search_tweets", False, f"Exception: {e}")
        results["search_tweets"] = False

    # --- 9. Get user tweets (using @twitter's user_id from test 1) ---
    print("\n--- Test: twitter_get_user_tweets ---")
    if user_id:
        try:
            fn = get_tool("twitter_get_user_tweets")
            result = fn(user_id=user_id, max_results=5)
            if "error" in result:
                report("twitter_get_user_tweets", False, f"Error: {result['error']}")
                results["get_user_tweets"] = False
            else:
                count = len(result.get("data", []))
                report("twitter_get_user_tweets", True, f"Got {count} tweets from @twitter")
                results["get_user_tweets"] = True
        except Exception as e:
            report("twitter_get_user_tweets", False, f"Exception: {e}")
            results["get_user_tweets"] = False
    else:
        print(f"  [{SKIP}] twitter_get_user_tweets - no user_id from get_user test")

    # --- 10. Get mentions (using @twitter's user_id) ---
    print("\n--- Test: twitter_get_mentions ---")
    if user_id:
        try:
            fn = get_tool("twitter_get_mentions")
            result = fn(user_id=user_id, max_results=5)
            if "error" in result:
                # Mentions endpoint may require user-level auth, might 403
                report("twitter_get_mentions", False, f"Error: {result['error']}")
                results["get_mentions"] = False
            else:
                count = len(result.get("data", []))
                report("twitter_get_mentions", True, f"Got {count} mentions")
                results["get_mentions"] = True
        except Exception as e:
            report("twitter_get_mentions", False, f"Exception: {e}")
            results["get_mentions"] = False
    else:
        print(f"  [{SKIP}] twitter_get_mentions - no user_id")

    # --- 11. Delete the test tweet (cleanup) ---
    print("\n--- Cleanup: twitter_delete_tweet ---")
    try:
        fn = get_tool("twitter_delete_tweet")
        result = fn(tweet_id=tweet_id)
        if "error" in result:
            report("twitter_delete_tweet", False, f"Error: {result['error']}")
            results["delete_tweet"] = False
        else:
            report("twitter_delete_tweet", True, f"deleted={result.get('deleted')}")
            results["delete_tweet"] = True
    except Exception as e:
        report("twitter_delete_tweet", False, f"Exception: {e}")
        results["delete_tweet"] = False

    _print_summary(results)


def _print_summary(results):
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    passed = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)
    total = len(results)
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}: {name}")
    print(f"\n  {passed}/{total} passed, {failed} failed")


if __name__ == "__main__":
    main()
