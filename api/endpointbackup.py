"""
CrowdAudit — REST API

Exposes the Sanity Score over HTTP. Three endpoints:

  GET /health
  GET /v1/sanity-score/{topic_id}
  GET /v1/topics/ranked

Run locally:
  PYTHONPATH=. uvicorn api.endpoint:app --reload --port 8000
  Interactive docs: http://localhost:8000/docs

Data source behaviour:
  Development (ZERVE_ENDPOINT_URL not set in .env):
    Returns mock data so Role B can build the frontend immediately.
    No Zerve account needed during this phase.

  Production (ZERVE_ENDPOINT_URL set in .env after Day 7-9):
    Calls zerve_client.get_live_score() which forwards the request to
    your deployed Zerve scoring workflow and returns live scores.
    No code changes needed — flipping the env var is the only step.
"""

import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

ZERVE_ENDPOINT_URL = os.getenv("ZERVE_ENDPOINT_URL", "")
USE_LIVE_ZERVE = bool(ZERVE_ENDPOINT_URL)

if USE_LIVE_ZERVE:
    from zerve_client import get_live_score

    logger.info(f"Zerve live scoring active — endpoint: {ZERVE_ENDPOINT_URL}")
else:
    logger.info("ZERVE_ENDPOINT_URL not set — serving mock data (development mode)")


app = FastAPI(
    title="CrowdAudit API",
    description="Detects when public narrative on a topic has drifted from verified reality.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


#  Response schema


class SignalBreakdown(BaseModel):
    S1_narrative_velocity: float = Field(..., ge=0, le=1)
    S2_hype_spike: float = Field(..., ge=0, le=1)
    S3_reality_divergence: float = Field(..., ge=0, le=1)
    weights: dict


class SanityScoreResponse(BaseModel):
    topic_id: str
    topic_title: str
    sanity_score: int = Field(..., ge=0, le=100)
    irrationality_index: float = Field(..., ge=0, le=1)
    signal_breakdown: SignalBreakdown
    divergence_vector: float
    top_hype_keywords: list[str] = []
    reason: str
    low_confidence: bool
    adversarial_notes: list[str] = []
    data_implied_score: float
    narrative_intensity: float
    data_domain: str
    computed_at: str


class RankedTopicsResponse(BaseModel):
    topics: list[SanityScoreResponse]
    computed_at: str
    total_topics: int


#  Mock data (used when ZERVE_ENDPOINT_URL is not set)

MOCK_TOPICS = [
    {
        "topic_id": "COVID_ORIGIN_NARRATIVE",
        "topic_title": "Public narrative on COVID-19 origin vs. scientific consensus",
        "sanity_score": 27,
        "irrationality_index": 0.73,
        "signal_breakdown": {
            "S1_narrative_velocity": 0.68,
            "S2_hype_spike": 0.91,
            "S3_reality_divergence": 0.56,
            "weights": {
                "S1_narrative_velocity": 0.25,
                "S2_hype_spike": 0.40,
                "S3_reality_divergence": 0.35,
            },
        },
        "divergence_vector": 0.44,
        "top_hype_keywords": ["lab leak", "natural origin", "wuhan", "fauci emails"],
        "reason": "High social volume spike (S2=0.91) — activity is 2.7σ above baseline | Reality divergence (S3=0.56) — narrative intensity at 82% vs data-implied 38%",
        "low_confidence": False,
        "adversarial_notes": [],
        "data_implied_score": 0.38,
        "narrative_intensity": 0.82,
        "data_domain": "health",
        "computed_at": datetime.utcnow().isoformat(),
    },
    {
        "topic_id": "INFLATION_CAUSE_NARRATIVE",
        "topic_title": "Public understanding of inflation causes vs. economic data",
        "sanity_score": 61,
        "irrationality_index": 0.39,
        "signal_breakdown": {
            "S1_narrative_velocity": 0.22,
            "S2_hype_spike": 0.48,
            "S3_reality_divergence": 0.41,
            "weights": {
                "S1_narrative_velocity": 0.25,
                "S2_hype_spike": 0.40,
                "S3_reality_divergence": 0.35,
            },
        },
        "divergence_vector": 0.19,
        "top_hype_keywords": ["greedflation", "corporate profits", "supply chain"],
        "reason": "All signals within normal range — narrative appears grounded in data",
        "low_confidence": True,
        "adversarial_notes": [
            "S1 (narrative velocity) is low (0.22) — Wikipedia edits are stable. Could reflect settled consensus rather than uninformed hype."
        ],
        "data_implied_score": 0.51,
        "narrative_intensity": 0.70,
        "data_domain": "economic",
        "computed_at": datetime.utcnow().isoformat(),
    },
    {
        "topic_id": "CLIMATE_TIPPING_POINTS",
        "topic_title": "Public narrative on climate tipping points vs. IPCC data",
        "sanity_score": 19,
        "irrationality_index": 0.81,
        "signal_breakdown": {
            "S1_narrative_velocity": 0.74,
            "S2_hype_spike": 0.93,
            "S3_reality_divergence": 0.69,
            "weights": {
                "S1_narrative_velocity": 0.25,
                "S2_hype_spike": 0.40,
                "S3_reality_divergence": 0.35,
            },
        },
        "divergence_vector": 0.52,
        "top_hype_keywords": [
            "climate collapse",
            "6 degrees",
            "point of no return",
            "climate emergency",
        ],
        "reason": "High social volume spike (S2=0.93) — activity is 2.8σ above baseline | Fast narrative shift (S1=0.74) | Reality divergence (S3=0.69)",
        "low_confidence": False,
        "adversarial_notes": [],
        "data_implied_score": 0.29,
        "narrative_intensity": 0.81,
        "data_domain": "climate",
        "computed_at": datetime.utcnow().isoformat(),
    },
]


#  Endpoints


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "0.1.0",
        "data_source": "zerve_live" if USE_LIVE_ZERVE else "mock",
        "zerve_url": ZERVE_ENDPOINT_URL or "not configured",
    }


@app.get("/v1/sanity-score/{topic_id}", response_model=SanityScoreResponse)
async def get_sanity_score(topic_id: str):
    """
    Get the Sanity Score for a specific topic.

    When ZERVE_ENDPOINT_URL is set: forwards request to the live Zerve
    scoring workflow and returns the result.

    When ZERVE_ENDPOINT_URL is not set: returns mock data for development.
    """
    if USE_LIVE_ZERVE:
        try:
            # Resolve topic metadata from mock list (or your own topic registry)
            meta = next((t for t in MOCK_TOPICS if t["topic_id"] == topic_id), None)
            title = meta["topic_title"] if meta else topic_id
            domain = meta["data_domain"] if meta else "economic"

            result = get_live_score(topic_id, title, domain)
            return SanityScoreResponse(**result)
        except Exception as e:
            logger.error(f"Zerve scoring failed for {topic_id}: {e}")
            raise HTTPException(
                status_code=502, detail=f"Zerve endpoint error: {str(e)}"
            )

    # Development: serve from mock data
    for topic in MOCK_TOPICS:
        if topic["topic_id"] == topic_id:
            return SanityScoreResponse(**topic)

    raise HTTPException(status_code=404, detail=f"Topic '{topic_id}' not found")


@app.get("/v1/topics/ranked", response_model=RankedTopicsResponse)
async def get_ranked_topics(
    limit: int = 20,
    min_irrationality: float = 0.0,
    data_domain: str = "",
):
    """
    Returns tracked topics sorted by irrationality_index descending.
    Filters: limit, min_irrationality (0.0–1.0), data_domain.
    """
    source = MOCK_TOPICS  # in production, replace with a live topic registry

    filtered = [
        t
        for t in source
        if t["irrationality_index"] >= min_irrationality
        and (not data_domain or t["data_domain"] == data_domain)
    ]
    ranked = sorted(filtered, key=lambda t: t["irrationality_index"], reverse=True)
    limited = ranked[:limit]

    return RankedTopicsResponse(
        topics=[SanityScoreResponse(**t) for t in limited],
        computed_at=datetime.utcnow().isoformat(),
        total_topics=len(limited),
    )
