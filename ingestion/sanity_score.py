"""
CrowdAudit — Sanity Score Engine

Computes a Sanity Score (0–100) measuring how far public narrative on a topic
has drifted from verified ground-truth data.

FORMULA
-------
  SanityScore = 100 − IrrationalityIndex

  IrrationalityIndex = (
      0.25 × S1_narrative_velocity  +   # how fast public narrative is shifting
      0.40 × S2_hype_spike          +   # how abnormal the social/search volume is
      0.35 × S3_reality_divergence      # how far narrative deviates from official data
  ) × 100

  Score interpretation:
    90–100  Grounded      — narrative closely reflects verified data
    70–89   Mostly sound  — minor hype influence, no major distortion
    50–69   Drifting      — notable gap between narrative and data
    30–49   Distorted     — significant hype is warping public understanding
    0–29    Detached      — narrative has little connection to reality

ADVERSARIAL CHECK
-----------------
After scoring, the engine runs a counter-narrative pass:
  "Assume the crowd is right and the data is lagging — what could explain this?"
If a plausible counter-narrative exists, the result is flagged low_confidence=True.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field, asdict
import json

#  Weights

WEIGHTS = {
    "S1_narrative_velocity": 0.25,
    "S2_hype_spike": 0.40,
    "S3_reality_divergence": 0.35,
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"

ADVERSARIAL_AMBIGUITY_THRESHOLD = 0.20


#  Signal functions


def compute_S1_narrative_velocity(
    df: pd.DataFrame,
    window_hours: int = 24,
) -> float:
    """
    S1 — Narrative Velocity (normalised 0–1).

    Measures how fast the Wikipedia edit rate is shifting relative to its
    historical baseline. A sudden spike in edits signals that a topic's
    public narrative is being rapidly rewritten — often a leading indicator
    that hype is outpacing verified information.

    Formula:
      velocity_ratio = mean(|hourly_edit_rate_change|) / narrative_volatility_baseline
      S1 = min(velocity_ratio / 3.0, 1.0)

    A topic whose edit rate is moving 3× its normal pace scores S1 = 1.0.
    """
    recent = df.tail(window_hours).copy()
    hourly_moves = recent["edit_rate"].diff(1).abs().dropna()

    if hourly_moves.empty or recent["narrative_volatility_baseline"].mean() == 0:
        return 0.0

    velocity_ratio = (
        hourly_moves.mean() / recent["narrative_volatility_baseline"].mean()
    )
    return float(np.clip(velocity_ratio / 3.0, 0.0, 1.0))


def compute_S2_hype_spike(
    df: pd.DataFrame,
    window_hours: int = 48,
    baseline_window: int = 168,
) -> tuple[float, list[str]]:
    """
    S2 — Hype Spike (normalised 0–1).

    Z-scores recent social/search volume against a 7-day baseline.
    Captures when a topic is receiving abnormal public attention — the
    primary driver of narrative distortion across all topic categories.

    Formula:
      z = (recent_mean_volume − baseline_mean) / baseline_std
      S2 = min(max(z / 3.0, 0.0), 1.0)

    A 3-sigma spike in social volume scores S2 = 1.0.
    Returns (S2, top_keywords) — keywords are pulled from Reddit/News APIs.
    """
    if "social_volume" not in df.columns:
        return 0.0, []

    recent = df["social_volume"].tail(window_hours)
    baseline = df["social_volume"].tail(baseline_window)

    baseline_std = baseline.std()
    if baseline_std == 0:
        return 0.0, []

    z_score = (recent.mean() - baseline.mean()) / baseline_std
    s2 = float(np.clip(z_score / 3.0, 0.0, 1.0))

    top_keywords = []
    if s2 > 0.3:
        # Wire this to Reddit API / NewsAPI for production keyword extraction
        top_keywords = ["[pull top terms from Reddit/NewsAPI for this topic]"]

    return s2, top_keywords


def compute_S3_reality_divergence(
    df: pd.DataFrame,
    data_domain: str = "economic",
) -> tuple[float, float]:
    """
    S3 — Reality Divergence (normalised 0–1).

    Measures how far the public narrative signal (Wikipedia edit intensity)
    has drifted from what official ground-truth data implies. When these two
    diverge significantly without a corresponding change in official data,
    the gap is the distortion signal.

    data_domain options:
      "economic"  — FRED indicators (unemployment, CPI, GDP)
      "health"    — WHO / CDC metrics (case rates, mortality, vaccine coverage)
      "political" — official polling averages, electoral commission data
      "climate"   — NOAA / NASA measurements

    Returns (S3, data_implied_score) where data_implied_score is the
    normalised ground-truth level on a 0–1 scale.
    """
    if "indicator_value" not in df.columns:
        return 0.0, 0.5

    latest_indicator = df["indicator_value"].dropna().iloc[-1]
    latest_edit_rate = df["edit_rate"].dropna().iloc[-1]

    # Normalise edit rate to a 0–1 narrative intensity score
    # (assumes edit_rate is on a 0–100 scale; adjust as needed)
    narrative_intensity = float(np.clip(latest_edit_rate / 100.0, 0.0, 1.0))

    # Map the official indicator to a normalised 0–1 "expected narrative intensity"
    # These heuristics should be replaced with calibrated models post-benchmarking
    if data_domain == "economic":
        # High unemployment or CPI → higher expected public concern (0–1)
        data_implied = float(np.clip((latest_indicator - 3.0) / 7.0, 0.0, 1.0))

    elif data_domain == "health":
        # High case rate per 100k → higher expected public concern
        data_implied = float(np.clip(latest_indicator / 500.0, 0.0, 1.0))

    elif data_domain == "political":
        # Normalise polling margin or approval rating to 0–1
        data_implied = float(np.clip(latest_indicator / 100.0, 0.0, 1.0))

    elif data_domain == "climate":
        # Normalise anomaly metric to 0–1
        data_implied = float(np.clip(latest_indicator / 3.0, 0.0, 1.0))

    else:
        data_implied = 0.5

    divergence = abs(narrative_intensity - data_implied)
    S3 = float(np.clip(divergence / 0.35, 0.0, 1.0))

    return S3, data_implied


#  Adversarial counter-check


def adversarial_counter_check(
    S1: float,
    S2: float,
    S3: float,
    narrative_intensity: float,
    data_implied: float,
) -> dict:
    """
    After scoring, ask: "Could the crowd actually be right and the data lagging?"

    Flags low_confidence=True if any signal is below the ambiguity threshold,
    meaning a plausible counter-narrative exists that the formula cannot rule out.
    """
    ambiguous_signals = []

    if S1 < ADVERSARIAL_AMBIGUITY_THRESHOLD:
        ambiguous_signals.append(
            f"S1 (narrative velocity) is low ({S1:.2f}) — Wikipedia edits are stable. "
            "Could reflect settled consensus rather than uninformed hype."
        )

    if S2 < ADVERSARIAL_AMBIGUITY_THRESHOLD:
        ambiguous_signals.append(
            f"S2 (hype spike) is low ({S2:.2f}) — social volume is normal. "
            "Narrative shift may be driven by real developments, not noise."
        )

    if S3 < ADVERSARIAL_AMBIGUITY_THRESHOLD:
        ambiguous_signals.append(
            f"S3 (reality divergence) is low ({S3:.2f}) — narrative aligns with official data. "
            "Official sources may themselves be lagging the real situation."
        )

    hidden_variable_hints = []
    if narrative_intensity > 0.70 and data_implied < 0.40:
        hidden_variable_hints.append(
            "Narrative intensity is high but official data is low. Possible explanations: "
            "official data has a publication lag, a breaking development hasn't yet appeared "
            "in official releases, or the public has access to localised information not "
            "captured at the national/global indicator level."
        )

    return {
        "low_confidence": len(ambiguous_signals) > 0,
        "ambiguous_signals": ambiguous_signals,
        "hidden_variable_hints": hidden_variable_hints,
        "divergence_gap": round(abs(narrative_intensity - data_implied), 4),
    }


#  Result dataclass


@dataclass
class SanityScoreResult:
    topic_id: str
    topic_title: str
    sanity_score: int  # 0–100
    irrationality_index: float  # 0.0–1.0
    signal_breakdown: dict = field(default_factory=dict)
    divergence_vector: float = 0.0  # narrative_intensity − data_implied (signed)
    top_hype_keywords: list = field(default_factory=list)
    reason: str = ""
    low_confidence: bool = False
    adversarial_notes: list = field(default_factory=list)
    data_implied_score: float = 0.5
    narrative_intensity: float = 0.5
    data_domain: str = ""
    computed_at: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


#  Master scoring function


def compute_sanity_score(
    aligned_df: pd.DataFrame,
    topic_id: str,
    topic_title: str = "",
    data_domain: str = "economic",
) -> SanityScoreResult:
    """
    Master function. Takes an aligned DataFrame from temporal_align.py,
    computes all three signals, applies the weighted formula, runs the
    adversarial check, and returns a SanityScoreResult.

    Call .to_json() on the result to get the API-ready JSON payload.
    """
    if aligned_df.empty or aligned_df["any_source_stale"].all():
        raise ValueError(f"No valid data for topic {topic_id}")

    clean = aligned_df[~aligned_df["any_source_stale"]].copy()

    S1 = compute_S1_narrative_velocity(clean)
    S2, keywords = compute_S2_hype_spike(clean)
    S3, data_impl = compute_S3_reality_divergence(clean, data_domain)

    irrationality = (
        WEIGHTS["S1_narrative_velocity"] * S1
        + WEIGHTS["S2_hype_spike"] * S2
        + WEIGHTS["S3_reality_divergence"] * S3
    )
    sanity = int(np.clip(round((1.0 - irrationality) * 100), 0, 100))

    # Build human-readable reason string
    reasons = []
    if S2 > 0.6:
        reasons.append(
            f"High social volume spike (S2={S2:.2f}) — "
            f"activity is {S2 * 3:.1f}σ above baseline"
        )
    if S3 > 0.5:
        latest_intensity = float(np.clip(clean["edit_rate"].iloc[-1] / 100.0, 0, 1))
        reasons.append(
            f"Reality divergence (S3={S3:.2f}) — "
            f"narrative intensity at {latest_intensity:.0%} vs data-implied {data_impl:.0%}"
        )
    if S1 > 0.5:
        reasons.append(
            f"Fast narrative shift (S1={S1:.2f}) — "
            "Wikipedia edit rate is 3× its historical baseline"
        )
    if not reasons:
        reasons.append(
            "All signals within normal range — narrative appears grounded in data"
        )

    latest_intensity = float(np.clip(clean["edit_rate"].iloc[-1] / 100.0, 0, 1))
    adversarial = adversarial_counter_check(S1, S2, S3, latest_intensity, data_impl)

    return SanityScoreResult(
        topic_id=topic_id,
        topic_title=topic_title,
        sanity_score=sanity,
        irrationality_index=round(irrationality, 4),
        signal_breakdown={
            "S1_narrative_velocity": round(S1, 4),
            "S2_hype_spike": round(S2, 4),
            "S3_reality_divergence": round(S3, 4),
            "weights": WEIGHTS,
        },
        divergence_vector=round(latest_intensity - data_impl, 4),
        top_hype_keywords=keywords,
        reason=" | ".join(reasons),
        low_confidence=adversarial["low_confidence"],
        adversarial_notes=(
            adversarial["ambiguous_signals"] + adversarial["hidden_variable_hints"]
        ),
        data_implied_score=round(data_impl, 4),
        narrative_intensity=round(latest_intensity, 4),
        data_domain=data_domain,
        computed_at=pd.Timestamp.utcnow().isoformat(),
    )


#  Self-test

if __name__ == "__main__":
    import sys

    sys.path.insert(0, ".")
    from ingestion.temporal_align import align_all_sources, compute_narrative_volatility

    hours = pd.date_range("2026-04-01", periods=336, freq="1h", tz="UTC")

    # Simulate: Wikipedia edits spiking heavily (narrative racing ahead of data)
    wiki = pd.DataFrame({"edit_rate": np.linspace(5, 80, 336)}, index=hours)
    social = pd.DataFrame({"social_volume": np.linspace(38, 95, 336)}, index=hours)
    offic = pd.DataFrame({"indicator_value": [3.6] * 336}, index=hours)

    aligned = align_all_sources(wiki, social, offic, "VACCINE_SAFETY_NARRATIVE")
    aligned = compute_narrative_volatility(aligned)

    result = compute_sanity_score(
        aligned,
        topic_id="VACCINE_SAFETY_NARRATIVE",
        topic_title="Public narrative on vaccine safety vs. clinical data",
        data_domain="health",
    )
    print(result.to_json())
