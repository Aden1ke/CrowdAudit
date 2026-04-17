"""
CrowdAudit — REST API

Exposes the Sanity Score over HTTP. Three endpoints:

  GET /health
  GET /v1/sanity-score/{topic_id}
  GET /v1/topics/ranked

Run locally:
  pip install fastapi uvicorn
  PYTHONPATH=. uvicorn api.endpoint:app --reload --port 8000

Interactive docs: http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime


app = FastAPI(
    title="CrowdAudit API",
    description="Detects when public narrative on a topic has drifted from verified reality.",
    version="0.1.0",
)


#  Response schema


class SignalBreakdown(BaseModel):
    S1_narrative_velocity: float = Field(
        ...,
        ge=0,
        le=1,
        description="Speed of Wikipedia narrative shift vs historical baseline",
    )
    S2_hype_spike: float = Field(
        ..., ge=0, le=1, description="Social/search volume z-score, normalised 0–1"
    )
    S3_reality_divergence: float = Field(
        ..., ge=0, le=1, description="Gap between narrative intensity and official data"
    )
    weights: dict = Field(
        ..., description="Weight applied to each signal in the composite score"
    )


class SanityScoreResponse(BaseModel):
    topic_id: str = Field(..., description="Unique topic identifier")
    topic_title: str = Field(..., description="Human-readable topic description")
    sanity_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="0=narrative detached from reality, 100=fully grounded",
    )
    irrationality_index: float = Field(
        ..., ge=0, le=1, description="Raw distortion composite before inversion"
    )
    signal_breakdown: SignalBreakdown
    divergence_vector: float = Field(
        ..., description="narrative_intensity minus data_implied_score (signed)"
    )
    top_hype_keywords: list[str] = Field(
        default=[], description="Terms driving the social volume spike"
    )
    reason: str = Field(..., description="Plain-English explanation of the score")
    low_confidence: bool = Field(
        ..., description="True if a plausible counter-narrative was identified"
    )
    adversarial_notes: list[str] = Field(
        default=[], description="Counter-narratives the adversarial check raised"
    )
    data_implied_score: float = Field(
        ..., description="Normalised score from official ground-truth data (0–1)"
    )
    narrative_intensity: float = Field(
        ..., description="Normalised public narrative intensity (0–1)"
    )
    data_domain: str = Field(
        ..., description="Domain of official data: economic, health, political, climate"
    )
    computed_at: str = Field(..., description="UTC ISO timestamp of this computation")


class RankedTopicsResponse(BaseModel):
    topics: list[SanityScoreResponse]
    computed_at: str
    total_topics: int


#  Mock data

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
        "reason": "High social volume spike (S2=0.93) — activity is 2.8σ above baseline | Fast narrative shift (S1=0.74) — Wikipedia edit rate is 3× its historical baseline | Reality divergence (S3=0.69)",
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
    return {"status": "ok", "version": "0.1.0"}


@app.get("/v1/sanity-score/{topic_id}", response_model=SanityScoreResponse)
async def get_sanity_score(topic_id: str):
    """
    Get the Sanity Score for a specific topic.
    Returns 404 if the topic is not currently tracked.
    """
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

    Query params:
      limit              — max topics to return (default 20)
      min_irrationality  — only return topics above this threshold (0.0–1.0)
      data_domain        — filter by domain: economic, health, political, climate
    """
    filtered = [
        t
        for t in MOCK_TOPICS
        if t["irrationality_index"] >= min_irrationality
        and (not data_domain or t["data_domain"] == data_domain)
    ]
    sorted_topics = sorted(
        filtered, key=lambda t: t["irrationality_index"], reverse=True
    )
    limited = sorted_topics[:limit]

    return RankedTopicsResponse(
        topics=[SanityScoreResponse(**t) for t in limited],
        computed_at=datetime.utcnow().isoformat(),
        total_topics=len(limited),
    )
