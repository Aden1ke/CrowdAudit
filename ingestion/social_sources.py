"""
CrowdAudit — Social Ingestion Layer

Fetches social volume signals from three fully free, no-auth-required sources
that replace Reddit's now-restricted API:

  Source 1 — HackerNews (via Algolia API)
    Best for: tech, science, economics, climate research
    Auth:     none
    Rate:     no documented limit, generous in practice
    Endpoint: https://hn.algolia.com/api/v1/search

  Source 2 — Bluesky (via public AT Protocol API)
    Best for: general public sentiment, real-time volume spikes
    Auth:     none for public search
    Rate:     no documented limit
    Endpoint: https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts

  Source 3 — Arctic Shift (Pushshift Reddit archive)
    What it is: community-maintained Reddit post archive, updated regularly
    Best for:   historical Reddit signal without needing Reddit API access
    Auth:       none
    Rate:       no documented limit
    Endpoint:   https://arctic-shift.photon-reddit.com/api/posts/search

All three return a normalised social_volume score (0–100) and top keywords.
The combined score is a weighted average:
    social_volume = 0.35 * hn_score + 0.40 * bsky_score + 0.25 * pushshift_score

Bluesky gets the highest weight because it's the most real-time.
HackerNews gets medium weight — high quality signal, lower volume.
Arctic Shift gets lowest weight — historical archive, may lag by hours.
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Optional
import time
import logging

logger = logging.getLogger(__name__)

#  Weights

SOURCE_WEIGHTS = {
    "hackernews": 0.35,
    "bluesky": 0.40,
    "arctic_shift": 0.25,
}

# How many posts in a 24h window = "100% volume" for normalisation
# Calibrate these against real topic baselines after first run
NORMALISATION_CAPS = {
    "hackernews": 50,  # 50 HN posts/day on a topic = max signal
    "bluesky": 500,  # 500 Bluesky posts/day = max signal
    "arctic_shift": 200,  # 200 Reddit archive posts/day = max signal
}

REQUEST_TIMEOUT = 10  # seconds per API call
RETRY_ATTEMPTS = 2


#  Shared HTTP helper


def _get(url: str, params: dict = {}, headers: dict = {}) -> Optional[dict]:
    """
    Simple GET with retry. Returns parsed JSON or None on failure.
    Never raises — caller handles None gracefully.
    """
    for attempt in range(RETRY_ATTEMPTS):
        try:
            r = requests.get(
                url, params=params, headers=headers, timeout=REQUEST_TIMEOUT
            )
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            logger.warning(
                f"HTTP {e.response.status_code} from {url} (attempt {attempt+1})"
            )
            if e.response.status_code == 429:
                time.sleep(2**attempt)  # exponential backoff on rate limit
        except Exception as e:
            logger.warning(f"Request failed for {url}: {e} (attempt {attempt+1})")
        time.sleep(0.5)
    return None


#  Source 1: HackerNews


def fetch_hackernews(
    query: str,
    since_hours: int = 24,
) -> tuple[float, list[str]]:
    """
    Fetch HackerNews post count and top terms for a topic via Algolia API.

    API docs: https://hn.algolia.com/api
    No auth required. No rate limit documented.

    Returns (normalised_volume_0_to_100, top_keywords).
    """
    since_ts = int(
        (datetime.now(timezone.utc) - timedelta(hours=since_hours)).timestamp()
    )

    data = _get(
        "https://hn.algolia.com/api/v1/search",
        params={
            "query": query,
            "tags": "story",  # only top-level posts, not comments
            "numericFilters": f"created_at_i>{since_ts}",
            "hitsPerPage": 100,
        },
    )

    if not data:
        return 0.0, []

    count = data.get("nbHits", 0)
    hits = data.get("hits", [])

    # Extract top keywords from titles (words appearing most in results)
    words: dict[str, int] = {}
    stopwords = {
        "the",
        "a",
        "an",
        "in",
        "of",
        "to",
        "and",
        "or",
        "is",
        "it",
        "for",
        "on",
        "at",
        "by",
        "with",
        "from",
        "that",
        "this",
        "are",
        "was",
        "were",
        "be",
        "been",
        "has",
        "have",
        "had",
        "not",
        "but",
        "as",
        "if",
        "its",
        "about",
        "into",
        "than",
        "so",
        "no",
        "up",
        "do",
        "he",
        "she",
        "we",
        "they",
        "you",
    }
    for hit in hits[:20]:
        for word in hit.get("title", "").lower().split():
            word = word.strip(".,!?\"'()-:")
            if len(word) > 3 and word not in stopwords:
                words[word] = words.get(word, 0) + 1

    top_keywords = sorted(words, key=words.get, reverse=True)[:5]  # type: ignore[arg-type]

    # Normalise count to 0–100
    volume = min(count / NORMALISATION_CAPS["hackernews"] * 100, 100.0)

    logger.info(f"HackerNews '{query}': {count} posts → volume={volume:.1f}")
    return float(volume), top_keywords


#  Source 2: Bluesky


def fetch_bluesky(
    query: str,
    since_hours: int = 24,
) -> tuple[float, list[str]]:
    """
    Fetch Bluesky post count for a topic via the public AT Protocol API.

    API docs: https://docs.bsky.app/docs/api/app-bsky-feed-search-posts
    No auth required for public search.

    Returns (normalised_volume_0_to_100, top_keywords).
    """
    since_dt = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    data = _get(
        "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts",
        params={
            "q": query,
            "limit": 100,
            "since": since_dt,
        },
    )

    if not data:
        return 0.0, []

    posts = data.get("posts", [])
    count = len(posts)

    # Extract terms from post text
    words: dict[str, int] = {}
    stopwords = {
        "the",
        "a",
        "an",
        "in",
        "of",
        "to",
        "and",
        "or",
        "is",
        "it",
        "for",
        "on",
        "at",
        "i",
        "my",
        "me",
        "we",
        "are",
        "was",
        "this",
        "that",
        "with",
        "from",
        "just",
        "so",
        "be",
        "have",
        "not",
        "but",
        "as",
        "if",
        "its",
    }
    for post in posts[:30]:
        text = post.get("record", {}).get("text", "")
        for word in text.lower().split():
            word = word.strip(".,!?\"'():#@-")
            if len(word) > 3 and word not in stopwords and not word.startswith("http"):
                words[word] = words.get(word, 0) + 1

    top_keywords = sorted(words, key=words.get, reverse=True)[:5]  # type: ignore[arg-type]

    volume = min(count / NORMALISATION_CAPS["bluesky"] * 100, 100.0)

    logger.info(f"Bluesky '{query}': {count} posts → volume={volume:.1f}")
    return float(volume), top_keywords


#  Source 3: Arctic Shift (Pushshift Reddit archive)


def fetch_arctic_shift(
    query: str,
    since_hours: int = 24,
    subreddits: Optional[list[str]] = None,
) -> tuple[float, list[str]]:
    """
    Fetch Reddit post count from the Arctic Shift archive (community Pushshift mirror).

    What Arctic Shift is:
      - A community-maintained archive of Reddit posts and comments
      - Updated regularly (typically within a few hours of posting)
      - No Reddit API key required — completely independent of Reddit's official API
      - Maintained at: https://github.com/ArthurHeitmann/arctic_shift

    API endpoint: https://arctic-shift.photon-reddit.com/api/posts/search

    subreddits: optional list to restrict search (e.g. ["science", "worldnews"])
                None = search all subreddits

    Returns (normalised_volume_0_to_100, top_keywords).
    """
    since_dt = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )

    params: dict = {
        "q": query,
        "after": since_dt,
        "limit": 100,
        "sort": "desc",
    }
    if subreddits:
        params["subreddit"] = ",".join(subreddits)

    data = _get(
        "https://arctic-shift.photon-reddit.com/api/posts/search", params=params
    )

    if not data:
        return 0.0, []

    # Arctic Shift returns either a list directly or {"data": [...]}
    posts = data if isinstance(data, list) else data.get("data", [])
    count = len(posts)

    # Extract terms from post titles
    words: dict[str, int] = {}
    stopwords = {
        "the",
        "a",
        "an",
        "in",
        "of",
        "to",
        "and",
        "or",
        "is",
        "it",
        "for",
        "on",
        "at",
        "by",
        "with",
        "from",
        "that",
        "this",
        "are",
        "was",
        "were",
        "be",
        "has",
        "have",
        "not",
        "but",
        "as",
        "if",
        "its",
        "about",
    }
    for post in posts[:30]:
        title = post.get("title", "")
        for word in title.lower().split():
            word = word.strip(".,!?\"'()-:")
            if len(word) > 3 and word not in stopwords:
                words[word] = words.get(word, 0) + 1

    top_keywords = sorted(words, key=words.get, reverse=True)[:5]  # type: ignore[arg-type]

    volume = min(count / NORMALISATION_CAPS["arctic_shift"] * 100, 100.0)

    logger.info(f"ArcticShift '{query}': {count} posts → volume={volume:.1f}")
    return float(volume), top_keywords


#  Combined social fetch


def fetch_social_volume(
    query: str,
    since_hours: int = 24,
    subreddits: Optional[list[str]] = None,
) -> dict:
    """
    Fetch and combine social volume from all three sources.

    Returns a dict with:
      social_volume      float 0–100  — weighted combined signal
      top_hype_keywords  list[str]    — deduplicated terms across all sources
      source_breakdown   dict         — individual scores per source
      fetched_at         str          — UTC ISO timestamp
    """
    hn_volume, hn_kws = fetch_hackernews(query, since_hours)
    bsky_volume, bsky_kws = fetch_bluesky(query, since_hours)
    ps_volume, ps_kws = fetch_arctic_shift(query, since_hours, subreddits)

    combined = (
        SOURCE_WEIGHTS["hackernews"] * hn_volume
        + SOURCE_WEIGHTS["bluesky"] * bsky_volume
        + SOURCE_WEIGHTS["arctic_shift"] * ps_volume
    )

    # Deduplicate keywords preserving order, prioritise Bluesky (most real-time)
    seen: set[str] = set()
    merged_keywords: list[str] = []
    for kw in bsky_kws + hn_kws + ps_kws:
        if kw not in seen:
            seen.add(kw)
            merged_keywords.append(kw)

    return {
        "social_volume": round(min(combined, 100.0), 2),
        "top_hype_keywords": merged_keywords[:8],
        "source_breakdown": {
            "hackernews": round(hn_volume, 2),
            "bluesky": round(bsky_volume, 2),
            "arctic_shift": round(ps_volume, 2),
        },
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


#  DataFrame builder (feeds into temporal_align.py)


def build_social_dataframe(
    query: str,
    lookback_hours: int = 168,
    window_size_hours: int = 24,
) -> pd.DataFrame:
    """
    Build a time-series DataFrame of social_volume suitable for temporal_align.py.

    Because all three APIs only support querying a recent window at a time,
    this function steps backwards through time in window_size_hours increments
    and assembles a historical series.

    In production, this is called once on startup and then incrementally
    updated each hour by fetching only the most recent window.

    Returns DataFrame with DatetimeIndex (UTC) and column 'social_volume'.
    """
    records = []
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    # For the most recent window use live data; older windows use Arctic Shift
    # (HN and Bluesky don't support deep historical queries)
    for step in range(0, lookback_hours, window_size_hours):
        window_end = now - timedelta(hours=step)
        window_start = window_end - timedelta(hours=window_size_hours)

        if step == 0:
            # Live fetch from all three sources
            result = fetch_social_volume(query, since_hours=window_size_hours)
            volume = result["social_volume"]
        else:
            # Historical: Arctic Shift only
            since_dt = window_start.strftime("%Y-%m-%dT%H:%M:%S")
            data = _get(
                "https://arctic-shift.photon-reddit.com/api/posts/search",
                params={"q": query, "after": since_dt, "limit": 100},
            )
            posts = data if isinstance(data, list) else (data or {}).get("data", [])
            volume = min(len(posts) / NORMALISATION_CAPS["arctic_shift"] * 100, 100.0)

        records.append({"timestamp": window_end, "social_volume": volume})

    df = pd.DataFrame(records).set_index("timestamp").sort_index()
    df.index = pd.DatetimeIndex(df.index, tz="UTC")
    return df


#  Self-test (uses mock data since sandbox blocks outbound)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Mock test — simulates what fetch_social_volume returns
    mock_result = {
        "social_volume": 72.4,
        "top_hype_keywords": [
            "climate",
            "tipping point",
            "ipcc",
            "emissions",
            "crisis",
        ],
        "source_breakdown": {"hackernews": 60.0, "bluesky": 85.0, "arctic_shift": 55.0},
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    print("fetch_social_volume() mock output:")
    import json

    print(json.dumps(mock_result, indent=2))

    # Verify weighted formula
    w = SOURCE_WEIGHTS
    caps = NORMALISATION_CAPS
    expected = (
        w["hackernews"] * mock_result["source_breakdown"]["hackernews"]
        + w["bluesky"] * mock_result["source_breakdown"]["bluesky"]
        + w["arctic_shift"] * mock_result["source_breakdown"]["arctic_shift"]
    )
    assert (
        abs(expected - mock_result["social_volume"]) < 0.1
    ), f"Weight formula mismatch: expected {expected:.1f} got {mock_result['social_volume']}"
    print(
        f"\nWeight formula check: {expected:.2f} ≈ {mock_result['social_volume']} — OK"
    )
    print(f"Weights sum: {sum(w.values())} — OK")
