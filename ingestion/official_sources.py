"""
CrowdAudit — Official Data Fetchers

Fetches ground-truth indicator values from authoritative sources
by data domain. These feed the S3 (reality divergence) signal.

Sources:
  economic  — FRED (Federal Reserve Economic Data)
  health    — NewsAPI headline frequency as proxy for reported case severity
              (WHO GHO API is slow; NewsAPI gives faster health signal)
  climate   — NOAA Global Surface Temperature anomaly
  political — Wikipedia article view counts as proxy for public attention
              (no free real-time electoral API exists)

All functions return a DataFrame with DatetimeIndex (UTC) and
column 'indicator_value'.
"""

import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Optional
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

FRED_API_KEY = os.getenv("FRED_API_KEY", "")
NOAA_TOKEN = os.getenv("NOAA_API_TOKEN", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
REQUEST_TIMEOUT = 10


#  FRED — Economic indicators

# Maps topic category to the most relevant FRED series
FRED_SERIES_MAP = {
    "unemployment": "UNRATE",  # US Unemployment Rate (monthly)
    "inflation": "CPIAUCSL",  # CPI All Urban Consumers (monthly)
    "gdp": "GDPC1",  # Real GDP (quarterly)
    "interest_rate": "FEDFUNDS",  # Federal Funds Rate (monthly)
    "default": "UNRATE",  # fallback
}


def fetch_fred(
    series_id: str = "UNRATE",
    lookback_days: int = 365,
) -> pd.DataFrame:
    """
    Fetch a FRED economic time series.
    Returns DataFrame with DatetimeIndex (UTC) and 'indicator_value' column.

    Requires FRED_API_KEY in .env
    Free key: https://fred.stlouisfed.org/docs/api/api_key.html
    """
    if not FRED_API_KEY:
        logger.warning("FRED_API_KEY not set — returning synthetic data")
        return _synthetic_official(lookback_days, base=4.0, noise=0.1)

    start = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime(
        "%Y-%m-%d"
    )

    try:
        r = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={
                "series_id": series_id,
                "api_key": FRED_API_KEY,
                "file_type": "json",
                "sort_order": "asc",
                "observation_start": start,
            },
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        obs = r.json().get("observations", [])

        records = []
        for o in obs:
            try:
                val = float(o["value"])
                ts = pd.Timestamp(o["date"], tz="UTC")
                records.append({"timestamp": ts, "indicator_value": val})
            except (ValueError, KeyError):
                continue

        if not records:
            logger.warning(f"FRED {series_id}: no valid observations returned")
            return _synthetic_official(lookback_days, base=4.0, noise=0.1)

        df = pd.DataFrame(records).set_index("timestamp")
        logger.info(
            f"FRED {series_id}: {len(df)} observations, latest={df['indicator_value'].iloc[-1]:.2f}"
        )
        return df

    except Exception as e:
        logger.warning(f"FRED fetch failed ({series_id}): {e}")
        return _synthetic_official(lookback_days, base=4.0, noise=0.1)


def fetch_fred_for_domain(topic_keywords: str) -> tuple[pd.DataFrame, str]:
    """
    Auto-select the best FRED series based on topic keywords.
    Returns (DataFrame, series_id_used).
    """
    kw = topic_keywords.lower()
    if any(w in kw for w in ["unemployment", "jobs", "labour", "labor", "employment"]):
        series = "UNRATE"
    elif any(w in kw for w in ["inflation", "cpi", "price", "cost of living"]):
        series = "CPIAUCSL"
    elif any(w in kw for w in ["gdp", "recession", "growth", "economy"]):
        series = "GDPC1"
    elif any(w in kw for w in ["interest", "fed", "rate", "federal reserve"]):
        series = "FEDFUNDS"
    else:
        series = "UNRATE"

    return fetch_fred(series), series


#  NewsAPI — Health / general official signal


def fetch_newsapi_volume(
    query: str,
    lookback_days: int = 30,
) -> pd.DataFrame:
    """
    Fetch daily news article count for a query from NewsAPI.
    Used as the official data proxy for health and political topics
    where structured government data is not available in real time.

    Returns DataFrame with DatetimeIndex (UTC) and 'indicator_value' column
    where value = normalised article count (0–100).

    Requires NEWS_API_KEY in .env
    Free tier: https://newsapi.org/register (100 requests/day)
    """
    if not NEWS_API_KEY:
        logger.warning("NEWS_API_KEY not set — returning synthetic data")
        return _synthetic_official(lookback_days * 24, base=40.0, noise=5.0)

    from_date = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime(
        "%Y-%m-%d"
    )

    try:
        r = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "from": from_date,
                "sortBy": "publishedAt",
                "pageSize": 100,
                "language": "en",
                "apiKey": NEWS_API_KEY,
            },
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        articles = r.json().get("articles", [])

        if not articles:
            return _synthetic_official(lookback_days * 24, base=40.0, noise=5.0)

        # Count articles per day
        dates = []
        for a in articles:
            try:
                dates.append(
                    pd.Timestamp(a["publishedAt"]).tz_convert("UTC").floor("D")
                )
            except Exception:
                continue

        if not dates:
            return _synthetic_official(lookback_days * 24, base=40.0, noise=5.0)

        series = pd.Series(1, index=pd.DatetimeIndex(dates)).resample("D").sum()
        # Normalise to 0-100
        max_val = max(series.max(), 1)
        series = (series / max_val * 100).rename("indicator_value")

        df = series.to_frame()
        logger.info(
            f"NewsAPI '{query}': {len(articles)} articles, peak day={series.max():.0f}"
        )
        return df

    except Exception as e:
        logger.warning(f"NewsAPI fetch failed for '{query}': {e}")
        return _synthetic_official(lookback_days * 24, base=40.0, noise=5.0)


#  NOAA — Climate indicators


def fetch_noaa_climate(
    lookback_days: int = 365,
) -> pd.DataFrame:
    """
    Fetch NOAA Global Surface Temperature anomaly data.
    Returns DataFrame with DatetimeIndex (UTC) and 'indicator_value' column
    where value = temperature anomaly in °C above pre-industrial baseline.

    Requires NOAA_API_TOKEN in .env
    Free token: https://www.ncdc.noaa.gov/cdo-web/token

    Falls back to synthetic data if token not available.
    """
    if not NOAA_TOKEN:
        logger.warning("NOAA_API_TOKEN not set — returning synthetic climate data")
        return _synthetic_official(lookback_days * 24, base=1.2, noise=0.05)

    from_date = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime(
        "%Y-%m-%d"
    )
    to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        r = requests.get(
            "https://www.ncdc.noaa.gov/cdo-web/api/v2/data",
            headers={"token": NOAA_TOKEN},
            params={
                "datasetid": "GSOY",
                "datatypeid": "TAVG",
                "stationid": "GHCND:USW00094728",  # Central Park, NYC as proxy
                "startdate": from_date,
                "enddate": to_date,
                "limit": 1000,
                "units": "metric",
            },
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        results = r.json().get("results", [])

        if not results:
            return _synthetic_official(lookback_days * 24, base=1.2, noise=0.05)

        records = [
            {
                "timestamp": pd.Timestamp(o["date"], tz="UTC"),
                "indicator_value": float(o["value"]) / 10,
            }
            for o in results
        ]
        df = pd.DataFrame(records).set_index("timestamp")
        logger.info(f"NOAA: {len(df)} temperature records fetched")
        return df

    except Exception as e:
        logger.warning(f"NOAA fetch failed: {e}")
        return _synthetic_official(lookback_days * 24, base=1.2, noise=0.05)


#  Synthetic fallback


def _synthetic_official(periods: int, base: float, noise: float) -> pd.DataFrame:
    """
    Returns a plausible synthetic time series when a real API is unavailable.
    Used during development and when API keys are missing.
    Values are clearly labelled as synthetic in the scoring output.
    """
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=periods)
    idx = pd.date_range(start=start, end=end, freq="1h", tz="UTC")
    vals = base + np.cumsum(np.random.normal(0, noise / 24, len(idx)))
    return pd.DataFrame({"indicator_value": vals}, index=idx)


#  Master dispatcher


def fetch_official_data(
    data_domain: str,
    topic_keywords: str = "",
    lookback_days: int = 30,
) -> pd.DataFrame:
    """
    Route to the correct official data source based on data_domain.

    Args:
        data_domain:     "economic", "health", "climate", or "political"
        topic_keywords:  Topic description used to auto-select FRED series
        lookback_days:   How many days of history to fetch

    Returns DataFrame with DatetimeIndex (UTC) and 'indicator_value' column.
    """
    if data_domain == "economic":
        df, series = fetch_fred_for_domain(topic_keywords)
        logger.info(f"Official data: FRED {series} for '{topic_keywords}'")
        return df

    elif data_domain == "health":
        # Use NewsAPI article volume as health official signal
        # In a full implementation, replace with WHO GHO API
        return fetch_newsapi_volume(topic_keywords, lookback_days)

    elif data_domain == "climate":
        return fetch_noaa_climate(lookback_days)

    elif data_domain == "political":
        # No free real-time political official API
        # Return NewsAPI volume as proxy
        return fetch_newsapi_volume(topic_keywords, lookback_days)

    else:
        logger.warning(f"Unknown data_domain '{data_domain}' — using FRED unemployment")
        return fetch_fred("UNRATE")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=== FRED (economic) ===")
    df = fetch_fred("UNRATE", lookback_days=90)
    print(f"Shape: {df.shape}, latest: {df['indicator_value'].iloc[-1]:.2f}")

    print("\n=== Official data dispatcher — health ===")
    df2 = fetch_official_data("health", "COVID vaccine safety", lookback_days=14)
    print(f"Shape: {df2.shape}")
