"""
CrowdAudit — Temporal Alignment Engine

Syncs three data sources with different update cadences into a unified
1-hour window DataFrame for the scoring engine.

The "heartbeat problem":
  - Wikipedia edit velocity:          can spike within minutes
  - Social volume (HN+Bluesky+PS):    aggregated per 24h window, updated hourly
  - Official ground data:             weekly or monthly (FRED, WHO, NOAA)

Strategy: resample everything DOWN to 1-hour windows.
  - Wikipedia:      OHLC of edit-rate within each hour
  - Social volume:  forward-fill (latest 24h window carries until next update)
  - Official data:  forward-fill (this month's value carries until next release)

Social data is produced by ingestion/social_sources.py which combines:
  - HackerNews  (Algolia API — no auth)
  - Bluesky     (AT Protocol public API — no auth)
  - Arctic Shift (Pushshift Reddit archive — no auth)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

#  Constants

RESAMPLE_FREQ = "1h"

STALENESS_LIMITS = {
    "wikipedia": 2,  # edit data stale after 2 hours of silence
    "social": 36,  # 24h social window — 36h gives a safe buffer
    "official_data": 720,  # monthly official data ~= 720 hours
}


#  Core resampler


def to_hourly(df: pd.DataFrame, value_col: str, source: str) -> pd.DataFrame:
    """
    Resample a single source DataFrame to 1-hour windows.

    Expects df to have a DatetimeIndex in UTC and a column named value_col.
    Returns a DataFrame with [value_col, {source}_staleness_hrs].

    Wikipedia (source="wikipedia"):
        Uses OHLC — closing edit-rate is the canonical hourly value.
        High/low preserved for the narrative volatility baseline calculation.

    All other sources (social, official_data):
        Forward-fill — last known value carries into future hours.
    """
    df = df.copy()
    df.index = pd.to_datetime(df.index, utc=True)
    df = df.sort_index()

    if source == "wikipedia":
        resampled = (
            df[value_col]
            .resample(RESAMPLE_FREQ)
            .agg(close="last", high="max", low="min")
        )
        resampled = resampled.rename(columns={"close": value_col})
        resampled[f"{source}_high"] = resampled["high"]
        resampled[f"{source}_low"] = resampled["low"]
        resampled = resampled[[value_col, f"{source}_high", f"{source}_low"]]
    else:
        resampled = df[value_col].resample(RESAMPLE_FREQ).last().to_frame()

    resampled[value_col] = resampled[value_col].ffill()

    last_obs = df[value_col].resample(RESAMPLE_FREQ).last()
    was_null = last_obs.isna()
    staleness = was_null.groupby((~was_null).cumsum()).cumcount()
    resampled[f"{source}_staleness_hrs"] = staleness.values[: len(resampled)]

    return resampled


#  Master join


def align_all_sources(
    wikipedia_df: pd.DataFrame,
    social_df: pd.DataFrame,
    official_df: pd.DataFrame,
    topic_id: str,
    lookback_hours: int = 168,
) -> pd.DataFrame:
    """
    Master join. Resamples all three sources to 1-hour windows and aligns
    them on a common UTC DatetimeIndex.

    Expected input columns:
      wikipedia_df:  ['edit_rate']       — edits/hour on the topic's Wikipedia page
                                           Source: Wikimedia API (no auth)
      social_df:     ['social_volume']   — combined HN + Bluesky + Arctic Shift score (0–100)
                                           Source: ingestion/social_sources.py
      official_df:   ['indicator_value'] — raw value from FRED, WHO, NOAA, etc.

    Output: one row per hour with all three sources merged.
    Rows where any_source_stale is True should be skipped by the scoring engine.

    Output columns:
      timestamp, topic_id,
      edit_rate, wikipedia_high, wikipedia_low, wikipedia_staleness_hrs,
      social_volume, social_staleness_hrs,
      indicator_value, official_data_staleness_hrs,
      any_source_stale, narrative_volatility_baseline (added by compute_narrative_volatility)
    """
    wiki = to_hourly(wikipedia_df, "edit_rate", "wikipedia")
    social = to_hourly(social_df, "social_volume", "social")
    offic = to_hourly(official_df, "indicator_value", "official_data")

    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=lookback_hours)
    idx = pd.date_range(start=start, end=end, freq=RESAMPLE_FREQ, tz="UTC")

    wiki = wiki.reindex(idx).ffill()
    social = social.reindex(idx).ffill()
    offic = offic.reindex(idx).ffill()

    aligned = wiki.join(social, how="outer").join(offic, how="outer")
    aligned.index.name = "timestamp"
    aligned.insert(0, "topic_id", topic_id)

    stale = (
        (aligned.get("wikipedia_staleness_hrs", 0) > STALENESS_LIMITS["wikipedia"])
        | (aligned.get("social_staleness_hrs", 0) > STALENESS_LIMITS["social"])
        | (
            aligned.get("official_data_staleness_hrs", 0)
            > STALENESS_LIMITS["official_data"]
        )
    )
    aligned["any_source_stale"] = stale

    return aligned.reset_index()


#  Narrative volatility baseline


def compute_narrative_volatility(
    aligned_df: pd.DataFrame,
    window_hours: int = 72,
) -> pd.DataFrame:
    """
    Adds 'narrative_volatility_baseline' — rolling std of edit_rate over
    the past window_hours. Used to normalise S1 (narrative velocity signal).
    Must be called before compute_sanity_score.
    """
    df = aligned_df.copy()
    df["narrative_volatility_baseline"] = (
        df["edit_rate"].rolling(window=window_hours, min_periods=6).std().fillna(0.5)
    )
    return df


#  Self-test

if __name__ == "__main__":
    hours = pd.date_range("2026-04-01", periods=720, freq="1h", tz="UTC")

    wiki_raw = pd.DataFrame(
        {"edit_rate": np.clip(5 + np.cumsum(np.random.normal(0, 0.5, 720)), 0, 100)},
        index=hours,
    )

    # social_df would normally come from social_sources.build_social_dataframe()
    social_raw = pd.DataFrame(
        {"social_volume": np.clip(40 + np.cumsum(np.random.normal(0, 2, 720)), 0, 100)},
        index=hours,
    )

    official_raw = pd.DataFrame(
        {"indicator_value": [3.5 + i * 0.005 for i in range(720)]}, index=hours
    )

    aligned = align_all_sources(wiki_raw, social_raw, official_raw, "TEST_TOPIC_001")
    aligned = compute_narrative_volatility(aligned)

    print(aligned.tail(3).to_string())
    print(f"\nShape: {aligned.shape} | Stale rows: {aligned['any_source_stale'].sum()}")
    print("\nColumns:", list(aligned.columns))
