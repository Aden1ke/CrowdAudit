"""
CrowdAudit — Data Pipeline

The single file that connects everything:
  ingestion → alignment → scoring → API-ready result

This is what api/endpoint.py calls instead of mock data.
No Zerve endpoint URL required — runs entirely on your machine.

Usage:
  from pipeline import run_pipeline

  result = run_pipeline(
      topic_id      = "COVID_ORIGIN_NARRATIVE",
      topic_title   = "Public narrative on COVID-19 origin vs. scientific consensus",
      topic_query   = "COVID-19 origin laboratory leak",
      data_domain   = "health",
      wikipedia_page = "COVID-19 lab leak hypothesis",  # optional, auto-detected if None
  )
  print(result)  # dict matching the SanityScoreResponse schema

Run standalone to test:
  PYTHONPATH=. python pipeline.py
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import numpy as np
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

#  Import all layers

from ingestion.social_sources import fetch_social_volume, build_social_dataframe
from ingestion.wikipedia_sources import fetch_wikipedia_edit_rate
from ingestion.official_sources import fetch_official_data
from ingestion.temporal_align import align_all_sources, compute_narrative_volatility
from scoring.sanity_score import compute_sanity_score

LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "168"))


#  Topic registry
# Add your real topics here. Each entry replaces a mock topic in endpoint.py.
# topic_query    = what you search for in social/news/Wikipedia
# wikipedia_page = exact Wikipedia page title (leave None for auto-detect)
# fred_keywords  = passed to FRED series selector for economic topics

TOPIC_REGISTRY = [
    {
        "topic_id": "COVID_ORIGIN_NARRATIVE",
        "topic_title": "Public narrative on COVID-19 origin vs. scientific consensus",
        "topic_query": "COVID-19 origin laboratory",
        "data_domain": "health",
        "wikipedia_page": "COVID-19 lab leak hypothesis",
    },
    {
        "topic_id": "INFLATION_CAUSE_NARRATIVE",
        "topic_title": "Public understanding of inflation causes vs. economic data",
        "topic_query": "inflation greedflation corporate profits",
        "data_domain": "economic",
        "wikipedia_page": None,  # auto-detect
    },
    {
        "topic_id": "CLIMATE_TIPPING_POINTS",
        "topic_title": "Public narrative on climate tipping points vs. IPCC data",
        "topic_query": "climate tipping points collapse emergency",
        "data_domain": "climate",
        "wikipedia_page": "Tipping points in the climate system",
    },
]


#  Core pipeline function


def run_pipeline(
    topic_id: str,
    topic_title: str,
    topic_query: str,
    data_domain: str,
    wikipedia_page: Optional[str] = None,
    lookback_hours: int = LOOKBACK_HOURS,
) -> dict:
    """
    Full pipeline for one topic. Fetches all data, aligns it,
    scores it, and returns a dict matching SanityScoreResponse schema.

    Falls back gracefully at each step — if one source fails,
    the pipeline continues with synthetic data rather than crashing.
    """
    logger.info(f"Pipeline starting for {topic_id}")

    #  Step 1: Fetch Wikipedia edit rate
    try:
        wiki_df, page_used = fetch_wikipedia_edit_rate(
            topic_query,
            page_title_override=wikipedia_page,
            lookback_hours=lookback_hours,
        )
        logger.info(
            f"Wikipedia: {page_used}, {wiki_df['edit_rate'].sum():.0f} total edits"
        )
    except Exception as e:
        logger.warning(f"Wikipedia fetch failed: {e} — using zeros")
        wiki_df = _zero_df("edit_rate", lookback_hours)

    #  Step 2: Fetch social volume
    try:
        social_result = fetch_social_volume(topic_query, since_hours=24)
        # Build a time-series DataFrame from the single combined score
        # In production, call build_social_dataframe() for a full history
        social_df = _constant_df(
            "social_volume", social_result["social_volume"], lookback_hours
        )
        top_keywords = social_result["top_hype_keywords"]
        logger.info(
            f"Social volume: {social_result['social_volume']:.1f}, "
            f"breakdown={social_result['source_breakdown']}"
        )
    except Exception as e:
        logger.warning(f"Social fetch failed: {e} — using zeros")
        social_df = _zero_df("social_volume", lookback_hours)
        top_keywords = []

    #  Step 3: Fetch official data
    try:
        official_df = fetch_official_data(
            data_domain=data_domain,
            topic_keywords=topic_query,
            lookback_days=max(lookback_hours // 24, 30),
        )
        logger.info(
            f"Official data: {len(official_df)} observations for domain={data_domain}"
        )
    except Exception as e:
        logger.warning(f"Official data fetch failed: {e} — using synthetic")
        official_df = _zero_df("indicator_value", lookback_hours)

    #  Step 4: Temporal alignment
    try:
        aligned = align_all_sources(
            wikipedia_df=wiki_df,
            social_df=social_df,
            official_df=official_df,
            topic_id=topic_id,
            lookback_hours=lookback_hours,
        )
        aligned = compute_narrative_volatility(aligned)
        logger.info(
            f"Alignment: {aligned.shape[0]} rows, "
            f"{aligned['any_source_stale'].sum()} stale"
        )
    except Exception as e:
        logger.error(f"Temporal alignment failed: {e}")
        return _error_response(topic_id, topic_title, data_domain, str(e))

    #  Step 5: Compute Sanity Score
    try:
        result = compute_sanity_score(
            aligned_df=aligned,
            topic_id=topic_id,
            topic_title=topic_title,
            data_domain=data_domain,
        )
        logger.info(f"Score: {result.sanity_score}/100 for {topic_id}")
    except Exception as e:
        logger.error(f"Scoring failed: {e}")
        return _error_response(topic_id, topic_title, data_domain, str(e))

    #  Step 6: Build API response dict
    import json, dataclasses

    response = json.loads(result.to_json())

    # Merge in the real keywords from social sources
    if top_keywords:
        response["top_hype_keywords"] = top_keywords

    return response


#  Batch pipeline (all topics in registry)


def run_all_topics() -> list[dict]:
    """
    Run the pipeline for every topic in TOPIC_REGISTRY.
    Returns a list of response dicts sorted by irrationality_index descending.
    Used by api/endpoint.py to populate the /v1/topics/ranked endpoint.
    """
    results = []
    for topic in TOPIC_REGISTRY:
        try:
            result = run_pipeline(
                topic_id=topic["topic_id"],
                topic_title=topic["topic_title"],
                topic_query=topic["topic_query"],
                data_domain=topic["data_domain"],
                wikipedia_page=topic.get("wikipedia_page"),
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Pipeline failed for {topic['topic_id']}: {e}")

    return sorted(results, key=lambda r: r.get("irrationality_index", 0), reverse=True)


#  Helpers


def _zero_df(col: str, hours: int) -> pd.DataFrame:
    """Return a DataFrame of zeros for the given column over lookback_hours."""
    from datetime import timedelta

    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=hours)
    idx = pd.date_range(start=start, end=end, freq="1h", tz="UTC")
    return pd.DataFrame({col: np.zeros(len(idx))}, index=idx)


def _constant_df(col: str, value: float, hours: int) -> pd.DataFrame:
    """Return a DataFrame with a constant value for the given column."""
    from datetime import timedelta

    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=hours)
    idx = pd.date_range(start=start, end=end, freq="1h", tz="UTC")
    return pd.DataFrame({col: np.full(len(idx), value)}, index=idx)


def _error_response(
    topic_id: str, topic_title: str, data_domain: str, error: str
) -> dict:
    """Return a minimal valid response dict when the pipeline fails."""
    return {
        "topic_id": topic_id,
        "topic_title": topic_title,
        "sanity_score": 50,
        "irrationality_index": 0.5,
        "signal_breakdown": {
            "S1_narrative_velocity": 0.0,
            "S2_hype_spike": 0.0,
            "S3_reality_divergence": 0.0,
            "weights": {
                "S1_narrative_velocity": 0.25,
                "S2_hype_spike": 0.40,
                "S3_reality_divergence": 0.35,
            },
        },
        "divergence_vector": 0.0,
        "top_hype_keywords": [],
        "reason": f"Pipeline error — {error}",
        "low_confidence": True,
        "adversarial_notes": [
            "Data pipeline encountered an error — score is unreliable"
        ],
        "data_implied_score": 0.5,
        "narrative_intensity": 0.5,
        "data_domain": data_domain,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


#  Self-test

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    print("\n=== Running pipeline for single topic ===\n")
    result = run_pipeline(
        topic_id="COVID_ORIGIN_NARRATIVE",
        topic_title="Public narrative on COVID-19 origin vs. scientific consensus",
        topic_query="COVID-19 origin laboratory",
        data_domain="health",
        wikipedia_page="COVID-19 lab leak hypothesis",
    )

    import json

    print(
        json.dumps(
            {
                "topic_id": result["topic_id"],
                "score": result["sanity_score"],
                "reason": result["reason"],
                "keywords": result["top_hype_keywords"],
                "computed_at": result["computed_at"],
            },
            indent=2,
        )
    )
