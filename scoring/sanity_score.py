"""
CrowdAudit — Sanity Score Engine
Role A Core Deliverable: the weighted irrationality formula.

FORMULA
  SanityScore = 100 − IrrationalityIndex

  IrrationalityIndex = (
      0.25 × S1_odds_velocity     +   # how fast odds moved vs baseline
      0.40 × S2_hype_spike        +   # how abnormal the search/social volume is
      0.35 × S3_econ_divergence       # how far odds are from FRED-implied reality
  ) × 100

  Score interpretation:
    90–100  Highly rational — market reflects data
    70–89   Mostly rational — minor hype influence
    50–69   Warning zone — notable divergence
    30–49   Irrational — significant hype premium
    0–29    Detached — crowd is flying blind

ADVERSARIAL CHECK
After computing the raw score, the engine runs a counter-narrative pass:
  "Assume the crowd is correct. What data could justify this price?"
If a plausible counter-narrative exists and the confidence threshold is
not met, the score is flagged with low_confidence=True.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field, asdict
from typing import Optional
import json
import sys
import os


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#  Weights (tunable — calibrate against gold benchmarks)

WEIGHTS = {
    "S1_odds_velocity": 0.25,
    "S2_hype_spike": 0.40,
    "S3_econ_divergence": 0.35,
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"

# Adversarial confidence threshold: if any single signal is ambiguous,
# flag the score for human review
ADVERSARIAL_AMBIGUITY_THRESHOLD = (
    0.20  # if any signal < 0.20, possible counter-narrative
)


#  Signal computers


def compute_S1_odds_velocity(
    df: pd.DataFrame,
    window_hours: int = 24,
) -> float:
    """
    S1 — Odds Velocity (normalised).
    How fast odds moved in the past window vs the historical baseline.

    Formula:
      recent_change = |implied_prob.diff(1)| over last window_hours
      velocity_raw  = mean(recent_change) / odds_volatility_baseline
      S1            = min(velocity_raw / 3.0, 1.0)   ← cap at 1.0

    A market that moved 3× its historical daily volatility gets S1 = 1.0.
    A market moving at its normal pace gets S1 ≈ 0.33.
    """
    recent = df.tail(window_hours).copy()
    daily_moves = recent["implied_prob"].diff(1).abs().dropna()

    if daily_moves.empty or recent["odds_volatility_baseline"].mean() == 0:
        return 0.0

    velocity_ratio = daily_moves.mean() / recent["odds_volatility_baseline"].mean()
    return float(np.clip(velocity_ratio / 3.0, 0.0, 1.0))


def compute_S2_hype_spike(
    df: pd.DataFrame,
    window_hours: int = 48,
    baseline_window: int = 168,  # 7-day baseline
) -> tuple[float, list[str]]:
    """
    S2 — Hype Spike (normalised).
    Z-score of recent search volume against a 7-day baseline.

    Formula:
      z = (recent_mean_volume − baseline_mean) / baseline_std
      S2 = min(max(z / 3.0, 0.0), 1.0)   ← 3-sigma spike → S2 = 1.0

    Returns (S2, top_keywords_list).
    top_keywords are synthetic here — real impl queries Reddit/Trends for
    the specific terms driving the volume spike.
    """
    if "search_volume" not in df.columns:
        return 0.0, []

    recent = df["search_volume"].tail(window_hours)
    baseline = df["search_volume"].tail(baseline_window)

    baseline_mean = baseline.mean()
    baseline_std = baseline.std()

    if baseline_std == 0:
        return 0.0, []

    z_score = (recent.mean() - baseline_mean) / baseline_std
    s2 = float(np.clip(z_score / 3.0, 0.0, 1.0))

    # Keyword extraction placeholder — wire to Reddit API for real terms
    top_keywords = []
    if s2 > 0.3:
        top_keywords = ["[pull from Reddit /api/search for this market's topic]"]

    return s2, top_keywords


def compute_S3_econ_divergence(
    df: pd.DataFrame,
    fred_series_type: str = "unemployment",  # or "cpi", "gdp_growth", etc.
) -> tuple[float, float]:
    """
    S3 — Economic Divergence.
    How far market implied_prob deviates from what FRED data would predict.

    This requires a calibrated mapping from economic indicator → expected probability.
    The mapping is trained on gold standard benchmarks (see benchmarks/gold_events.json).

    we use a simple heuristic rule set per series type.
    Replace with a regression model once gold benchmarks are validated.

    Returns (S3, fred_implied_prob).
    """
    if "indicator_value" not in df.columns:
        return 0.0, 0.5

    latest_indicator = df["indicator_value"].dropna().iloc[-1]
    latest_odds = df["implied_prob"].dropna().iloc[-1]

    #  Heuristic mappings (REPLACE with calibrated model post-benchmarking)
    if fred_series_type == "unemployment":
        # High unemployment → Fed rate cut more likely → map to 0.0–1.0 prob
        fred_implied = float(np.clip((latest_indicator - 3.5) / 4.0, 0.0, 1.0))

    elif fred_series_type == "cpi":
        # High CPI → rate hike more likely
        fred_implied = float(np.clip((latest_indicator - 2.0) / 6.0, 0.0, 1.0))

    else:
        fred_implied = 0.5  # unknown series — neutral assumption

    divergence = abs(latest_odds - fred_implied)
    S3 = float(np.clip(divergence / 0.35, 0.0, 1.0))  # 35pp divergence → max score

    return S3, fred_implied


#  Adversarial check


def adversarial_counter_check(
    S1: float,
    S2: float,
    S3: float,
    implied_prob: float,
    fred_implied_prob: float,
) -> dict:
    """
    Zerve adversarial steering prompt output.
    This function documents what the agent is asked to challenge,
    and returns a structured result the agent's response should populate.

    The actual Zerve prompt is in zerve_prompts/adversarial_prompts.py.
    This function produces the CONTEXT that prompt receives.
    """
    ambiguous_signals = []

    if S1 < ADVERSARIAL_AMBIGUITY_THRESHOLD:
        ambiguous_signals.append(
            f"S1 (odds velocity) is low ({S1:.2f}) — market has been stable. "
            "Could be rational consensus, not complacency."
        )

    if S2 < ADVERSARIAL_AMBIGUITY_THRESHOLD:
        ambiguous_signals.append(
            f"S2 (hype spike) is low ({S2:.2f}) — search volume is normal. "
            "Crowd may be acting on private information, not noise."
        )

    if S3 < ADVERSARIAL_AMBIGUITY_THRESHOLD:
        ambiguous_signals.append(
            f"S3 (econ divergence) is low ({S3:.2f}) — odds align with FRED data. "
            "Market may be pricing in forward-looking info FRED doesn't capture."
        )

    prob_gap = abs(implied_prob - fred_implied_prob)
    hidden_variable_hints = []

    if implied_prob > 0.75 and fred_implied_prob < 0.55:
        hidden_variable_hints.append(
            "Market is pricing high confidence not supported by FRED. "
            "Possible hidden variable: insider information, non-public policy signal, "
            "or a structural break in the FRED series' predictive power."
        )

    return {
        "low_confidence": len(ambiguous_signals) > 0,
        "ambiguous_signals": ambiguous_signals,
        "hidden_variable_hints": hidden_variable_hints,
        "probability_gap": round(prob_gap, 4),
    }


#  Main scoring function


@dataclass
class SanityScoreResult:
    market_id: str
    sanity_score: int  # 0–100
    irrationality_index: float  # 0.0–1.0 (raw before inversion)
    signal_breakdown: dict = field(default_factory=dict)
    divergence_vector: float = 0.0  # latest odds − fred_implied_prob
    top_hype_keywords: list = field(default_factory=list)
    reason: str = ""  # human-readable explainability
    low_confidence: bool = False
    adversarial_notes: list = field(default_factory=list)
    fred_implied_prob: float = 0.5
    market_implied_prob: float = 0.5
    computed_at: str = ""

    def to_json(self) -> str:
        """Serialize to the API contract JSON (what Role B receives)."""
        return json.dumps(asdict(self), indent=2)


def compute_sanity_score(
    aligned_df: pd.DataFrame,
    market_id: str,
    fred_series_type: str = "unemployment",
) -> SanityScoreResult:
    """
    Master scoring function. Takes aligned DataFrame, returns SanityScoreResult.
    This is what Zerve calls on each market tick.
    """
    if aligned_df.empty or aligned_df["any_source_stale"].all():
        raise ValueError(f"No valid data for market {market_id}")

    # Filter to non-stale rows
    clean = aligned_df[~aligned_df["any_source_stale"]].copy()

    #  Compute signals
    S1 = compute_S1_odds_velocity(clean)
    S2, top_keywords = compute_S2_hype_spike(clean)
    S3, fred_implied = compute_S3_econ_divergence(clean, fred_series_type)

    #  Weighted irrationality index
    irrationality = (
        WEIGHTS["S1_odds_velocity"] * S1
        + WEIGHTS["S2_hype_spike"] * S2
        + WEIGHTS["S3_econ_divergence"] * S3
    )
    sanity = int(round((1.0 - irrationality) * 100))
    sanity = max(0, min(100, sanity))

    #  Explainability: build human-readable reason
    reasons = []

    if S2 > 0.6:
        reasons.append(
            f"High hype spike (S2={S2:.2f}) — search volume is {S2*3:.1f}σ above baseline"
        )
    if S3 > 0.5:
        latest_odds = clean["implied_prob"].iloc[-1]
        reasons.append(
            f"Economic divergence (S3={S3:.2f}) — market at {latest_odds:.0%} "
            f"vs FRED-implied {fred_implied:.0%}"
        )
    if S1 > 0.5:
        reasons.append(
            f"Fast odds movement (S1={S1:.2f}) — 3× historical daily volatility"
        )
    if not reasons:
        reasons.append(
            "All signals within normal range — market appears rationally priced"
        )

    reason_str = " | ".join(reasons)

    #  Adversarial check
    latest_prob = clean["implied_prob"].iloc[-1]
    adversarial = adversarial_counter_check(S1, S2, S3, latest_prob, fred_implied)

    return SanityScoreResult(
        market_id=market_id,
        sanity_score=sanity,
        irrationality_index=round(irrationality, 4),
        signal_breakdown={
            "S1_odds_velocity": round(S1, 4),
            "S2_hype_spike": round(S2, 4),
            "S3_econ_divergence": round(S3, 4),
            "weights": WEIGHTS,
        },
        divergence_vector=round(latest_prob - fred_implied, 4),
        top_hype_keywords=top_keywords,
        reason=reason_str,
        low_confidence=adversarial["low_confidence"],
        adversarial_notes=adversarial["ambiguous_signals"]
        + adversarial["hidden_variable_hints"],
        fred_implied_prob=round(fred_implied, 4),
        market_implied_prob=round(latest_prob, 4),
        computed_at=pd.Timestamp.utcnow().isoformat(),
    )


#  Quick test

if __name__ == "__main__":
    from ingestion.temporal_align import (
        align_all_sources,
        compute_narrative_volatility,
    )

    # Synthetic: market at 85% but FRED implies only 52% → strong divergence
    hours = pd.date_range("2026-04-01", periods=336, freq="1h", tz="UTC")
    pm = pd.DataFrame({"implied_prob": np.linspace(0.60, 0.85, 336)}, index=hours)
    gt = pd.DataFrame({"search_volume": np.linspace(40, 90, 336)}, index=hours)
    fred = pd.DataFrame({"indicator_value": np.linspace(3.5, 4.2, 336)}, index=hours)

    aligned = align_all_sources(pm, gt, fred, "FED_RATE_CUT_JUL26")
    aligned = compute_historical_volatility(aligned)

    result = compute_sanity_score(
        aligned, "FED_RATE_CUT_JUL26", fred_series_type="unemployment"
    )
    print(result.to_json())
