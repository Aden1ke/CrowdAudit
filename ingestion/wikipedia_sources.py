"""
CrowdAudit — Wikipedia Ingestion

Fetches edit velocity for a topic's Wikipedia page using the
public Wikimedia REST API. No API key required.

Edit velocity = number of edits per hour on a page.
A spike in edits signals the public narrative is being actively
rewritten — often a leading indicator of distortion.

API used: https://api.wikimedia.org/wiki/Core_REST_API
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)

WIKIPEDIA_BASE = "https://en.wikipedia.org/w/api.php"
WIKIMEDIA_BASE = "https://api.wikimedia.org/core/v1/wikipedia/en"
REQUEST_TIMEOUT = 10


def find_wikipedia_page(topic_query: str) -> Optional[str]:
    """
    Search Wikipedia for the most relevant page title for a topic query.
    Returns the page title string or None if nothing found.

    Example:
        find_wikipedia_page("COVID-19 origin") → "COVID-19 lab leak hypothesis"
    """
    params = {
        "action": "query",
        "list": "search",
        "srsearch": topic_query,
        "srlimit": 1,
        "format": "json",
    }
    try:
        r = requests.get(WIKIPEDIA_BASE, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        results = r.json().get("query", {}).get("search", [])
        if results:
            return results[0]["title"]
    except Exception as e:
        logger.warning(f"Wikipedia search failed for '{topic_query}': {e}")
    return None


def fetch_edit_history(
    page_title: str,
    lookback_hours: int = 168,
) -> pd.DataFrame:
    """
    Fetch the revision history for a Wikipedia page and return a DataFrame
    of hourly edit counts.

    Uses the Wikipedia revisions API which requires no authentication.

    Returns DataFrame with DatetimeIndex (UTC) and column 'edit_rate'
    (edits per hour in that window).
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=lookback_hours)

    revisions = []
    params = {
        "action": "query",
        "prop": "revisions",
        "titles": page_title,
        "rvprop": "timestamp",
        "rvlimit": "500",
        "rvstart": end.isoformat(),
        "rvend": start.isoformat(),
        "rvdir": "older",
        "format": "json",
    }

    try:
        while True:
            r = requests.get(WIKIPEDIA_BASE, params=params, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            pages = data.get("query", {}).get("pages", {})

            for page in pages.values():
                for rev in page.get("revisions", []):
                    ts = rev.get("timestamp")
                    if ts:
                        revisions.append(pd.Timestamp(ts, tz="UTC"))

            # Handle pagination
            cont = data.get("continue")
            if not cont:
                break
            params["rvcontinue"] = cont.get("rvcontinue", "")

    except Exception as e:
        logger.warning(f"Wikipedia revision fetch failed for '{page_title}': {e}")
        return _empty_edit_df(start, end)

    if not revisions:
        logger.info(f"No revisions found for '{page_title}' in window")
        return _empty_edit_df(start, end)

    # Build hourly edit count series
    series = pd.Series(1, index=pd.DatetimeIndex(revisions))
    hourly = (
        series.resample("1h")
        .sum()
        .reindex(pd.date_range(start=start, end=end, freq="1h", tz="UTC"), fill_value=0)
    )

    df = hourly.rename("edit_rate").to_frame()
    logger.info(
        f"Wikipedia '{page_title}': {len(revisions)} edits → max hourly={hourly.max():.0f}"
    )
    return df


def fetch_wikipedia_edit_rate(
    topic_query: str,
    page_title_override: Optional[str] = None,
    lookback_hours: int = 168,
) -> tuple[pd.DataFrame, str]:
    """
    Master function. Finds the Wikipedia page for a topic and returns
    its hourly edit rate DataFrame.

    Args:
        topic_query:          Natural language topic (e.g. "COVID-19 origin")
        page_title_override:  If you already know the exact Wikipedia page title,
                              pass it here to skip the search step.
        lookback_hours:       How many hours of history to fetch (default 7 days)

    Returns:
        (DataFrame with 'edit_rate' column, page_title_used)
    """
    title = page_title_override or find_wikipedia_page(topic_query)

    if not title:
        logger.warning(f"No Wikipedia page found for '{topic_query}' — returning zeros")
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=lookback_hours)
        return _empty_edit_df(start, end), ""

    df = fetch_edit_history(title, lookback_hours)
    return df, title


def _empty_edit_df(start: datetime, end: datetime) -> pd.DataFrame:
    """Return a zeroed edit rate DataFrame when no data is available."""
    idx = pd.date_range(start=start, end=end, freq="1h", tz="UTC")
    return pd.DataFrame({"edit_rate": np.zeros(len(idx))}, index=idx)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df, title = fetch_wikipedia_edit_rate(
        "COVID-19 origin laboratory", lookback_hours=72
    )
    print(f"Page: {title}")
    print(f"Shape: {df.shape}")
    print(f"Total edits in window: {df['edit_rate'].sum():.0f}")
    print(f"Peak hourly edits: {df['edit_rate'].max():.0f}")
    print(df[df["edit_rate"] > 0].tail(5))
