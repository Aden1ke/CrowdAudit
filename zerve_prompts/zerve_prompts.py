"""
CrowdAudit — Zerve Agent Prompts

Exploration questions and adversarial steering prompts for Zerve sessions.
These prompts drive the analytical depth of the project. The quality of
the questions determines the quality of the findings.

HOW TO USE

1. Open a Zerve session
2. Paste DATA_CONTEXT at the start to orient the agent
3. Run MASTER_EXPLORATION_QUESTION — this drives the bulk of each session
4. For each strong finding, call build_adversarial_prompt() and run the result
5. Document any failed agent paths using FAILED_PATH_LOG_TEMPLATE
"""

#  Data context

DATA_CONTEXT = """
You have access to three data sources, all aligned to 1-hour UTC windows:

1. WIKIPEDIA_DATA: Time-series of edit velocity per topic page.
   Columns: [topic_id, topic_title, edit_rate (edits/hour), timestamp_utc]
   Cadence: near real-time, resampled to hourly windows.
   Interpretation: rapid editing signals contested or rapidly-shifting narrative.

2. SOCIAL_DATA: Combined Reddit post volume + NewsAPI headline frequency, normalised 0–100.
   Columns: [topic_id, social_volume (0-100), top_terms, date]
   Cadence: daily. High values indicate strong public attention and emotional engagement.

3. OFFICIAL_DATA: Ground-truth indicators from authoritative sources.
   Columns: [topic_id, data_domain, indicator_value, source, date]
   Sources by domain:
     economic  — FRED (unemployment UNRATE, inflation CPIAUCSL, GDP GDPC1)
     health    — WHO / CDC (case rates, mortality rates, vaccine coverage)
     political — official polling aggregates, electoral commission releases
     climate   — NOAA / NASA measurements (temperature anomaly, sea level, CO2 ppm)
   Cadence: weekly or monthly depending on source.

All three are aligned to 1-hour UTC windows using forward-fill for lower-cadence sources.
Rows flagged any_source_stale=True should be excluded from analysis.
"""


#  Master exploration question

MASTER_EXPLORATION_QUESTION = """
CONTEXT:
{data_context}

TASK:
Analyse all three data sources and identify the top 5 topics where:
  (a) Wikipedia edit_rate spiked by more than 3× its 7-day rolling average
      within a 48-hour window
  (b) social_volume for the same topic spiked by more than 40% above its
      7-day rolling average WITHIN the same 48-hour window
  (c) The relevant official indicator did NOT move significantly in the same
      period — less than 5% relative change for economic/health data,
      or less than 0.1 units for climate measurements

For each identified topic:
  1. Report the exact timing of the Wikipedia spike and the social volume spike
  2. Calculate the "lag time" — did Wikipedia edits spike before or after social volume?
  3. Describe what the official data was saying at the same time
  4. Assess: is this a case where public narrative raced ahead of verified information,
     or where verified information was genuinely slow to be published?
  5. Assign a preliminary Irrationality Score:
       IrrScore = (wiki_velocity_ratio/3 × 0.25) + (social_zscore/3 × 0.40) + (data_gap × 0.35)

Format as a structured table, then write a 3-sentence summary of the most striking case.
""".format(
    data_context=DATA_CONTEXT
)


#  Hype lag deep dive

HYPE_LAG_PROMPT = """
CONTEXT:
{data_context}

HYPOTHESIS TO TEST:
"When social_volume for a topic spikes by 40%+ above baseline, Wikipedia edit activity
overcorrects in the same or following 48-hour window — even when official data shows
no corresponding change. The narrative is being shaped by attention, not by evidence."

TASK:
1. For each of the top 10 social volume spikes in the dataset, calculate:
   - The magnitude of the Wikipedia edit spike in the 48 hours following the social spike
   - Whether any official data release (FRED, WHO, NOAA) occurred in the same window
     that could explain the narrative shift
   - The "reversion rate" — how much did Wikipedia edit velocity drop within 7 days,
     and did the narrative return toward the pre-spike baseline?

2. Run a correlation analysis:
   - X-axis: social volume spike magnitude (z-score)
   - Y-axis: subsequent 48-hour Wikipedia edit rate change
   - Report Pearson r and p-value

3. Separate the results by data_domain (economic, health, political, climate).
   Is the hype lag effect stronger in some domains than others?

4. Conclude: is attention-driven narrative distortion a measurable phenomenon in this
   dataset, and which domain shows the strongest distortion pattern?
""".format(
    data_context=DATA_CONTEXT
)


#  Certainty trap analysis

CERTAINTY_TRAP_PROMPT = """
CONTEXT:
{data_context}

HYPOTHESIS TO TEST:
"When narrative_intensity (normalised Wikipedia edit rate) exceeds 0.80 for a topic,
official data supports that level of public concern less than 40% of the time.
High-confidence public narratives are frequently not grounded in data."

TASK:
1. Find all topic-hours where narrative_intensity > 0.80 (edit_rate > 80th percentile)
2. For each cluster, check: does the official indicator justify this level of intensity?
   Use these calibration thresholds by domain:
     economic:  unemployment > 6% OR CPI > 5% → high intensity justified
     health:    case rate > 200/100k OR mortality rate significantly elevated → justified
     political: polling margin < 3% (genuine uncertainty) → high attention justified
     climate:   anomaly > 1.5°C above pre-industrial baseline → justified

3. For clusters where official data does NOT justify the intensity:
   - What were the top social terms driving the narrative?
   - Did the narrative eventually correct toward the data, or persist?

4. Report: the "Certainty Gap" — average proportion of high-intensity narrative
   periods that are not supported by official data, across all domains.
""".format(
    data_context=DATA_CONTEXT
)


#  Adversarial counter-narrative prompt

ADVERSARIAL_PROMPT_TEMPLATE = """
CONTEXT:
{data_context}

YOU ARE NOW PLAYING DEVIL'S ADVOCATE.

CrowdAudit has computed a Sanity Score of {sanity_score}/100 for topic "{topic_id}",
suggesting the public narrative has drifted significantly from official data.
The signals were:
  - S1 (narrative velocity):   {S1:.2f}
  - S2 (hype spike):           {S2:.2f}
  - S3 (reality divergence):   {S3:.2f}

YOUR TASK — ASSUME THE PUBLIC IS RIGHT AND THE DATA IS LAGGING:
1. What real-world developments could the public be responding to that have NOT
   yet appeared in official data? List at least 3 plausible candidates.
   Consider: publication lags in official statistics, localised events not captured
   at national/global level, whistleblower or leaked information, genuine expert
   disagreement not yet resolved in official publications.

2. Is it possible that the official data source we are using is the WRONG proxy
   for this topic? What alternative official source might better capture reality?

3. Is the Wikipedia edit spike potentially a sign of genuine knowledge-building
   (experts updating articles with new verified information) rather than
   narrative distortion?

4. Given the above, what is your confidence (0–100%) that the Sanity Score is
   correctly identifying distortion rather than a data lag false positive?

5. If confidence < 70%, flag this topic as LOW_CONFIDENCE and state what additional
   data would resolve the ambiguity.
"""


def build_adversarial_prompt(
    topic_id: str,
    sanity_score: int,
    S1: float,
    S2: float,
    S3: float,
) -> str:
    """Build a fully formatted adversarial prompt for a specific topic."""
    return ADVERSARIAL_PROMPT_TEMPLATE.format(
        data_context=DATA_CONTEXT,
        topic_id=topic_id,
        sanity_score=sanity_score,
        S1=S1,
        S2=S2,
        S3=S3,
    )


#  Failed path log

FAILED_PATH_LOG_TEMPLATE = """
# Zerve Agent — Failed Path Log

## Session: {session_id}
## Date: {date}

### Attempt {n}
**Prompt summary:** {prompt_summary}

**What the agent did:**
{agent_action}

**Why it failed or led nowhere:**
{failure_reason}

**How we steered it back:**
{correction_action}

**Lesson learned:**
{lesson}
---
"""

EXAMPLE_FAILED_PATH = FAILED_PATH_LOG_TEMPLATE.format(
    session_id="SESSION_001",
    date="2026-04-15",
    n=1,
    prompt_summary="Asked agent to correlate official health data directly with Wikipedia edit rate across all health topics simultaneously",
    agent_action="Agent ran a single Pearson correlation across all health topics, finding r=0.08 (near zero)",
    failure_reason="Signal was diluted because different health topics respond to completely different official indicators. Mixing vaccine topics (respond to case rates) with nutrition topics (respond to WHO dietary guidelines) destroyed the correlation.",
    correction_action="Instructed agent to group topics by sub-domain first (infectious disease, chronic disease, mental health), then run per-group correlations using the relevant official series for each group.",
    lesson="Always segment by sub-domain before running cross-source correlations. The master question must specify which official series maps to which topic category.",
)


if __name__ == "__main__":
    print("=" * 70)
    print("MASTER EXPLORATION QUESTION")
    print("=" * 70)
    print(MASTER_EXPLORATION_QUESTION)

    print("\n" + "=" * 70)
    print("EXAMPLE ADVERSARIAL PROMPT (COVID_ORIGIN_NARRATIVE, score=27)")
    print("=" * 70)
    print(build_adversarial_prompt("COVID_ORIGIN_NARRATIVE", 27, 0.68, 0.91, 0.56))
