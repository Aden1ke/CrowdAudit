# CrowdAudit

CrowdAudit detects when public narrative on a topic has drifted away from verified, ground-truth data — and measures how far that drift has gone.

The internet produces enormous amounts of attention around any given topic. Wikipedia pages get edited rapidly. Reddit threads explode. News headlines multiply. Sometimes this activity reflects genuine new information. Often it reflects hype, fear, or misinformation outpacing what the evidence actually shows. CrowdAudit quantifies that gap in real time.

---

## How It Works

Three data layers are pulled simultaneously for any tracked topic:

**Crowd narrative** — Wikipedia edit velocity on the topic's page. When a topic's Wikipedia article is being edited rapidly, the public narrative around it is actively being contested or rewritten. This is a real-time signal of how much the collective story is shifting.

**Social hype** — combined Reddit post volume and news headline frequency, normalised to a 0–100 index. This captures the emotional intensity and reach of public attention around a topic, independent of whether that attention is grounded in new information.

**Ground reality** — official data from authoritative sources, selected by topic domain:

- Economics: FRED (Federal Reserve) — unemployment, inflation, GDP
- Health: WHO and CDC — case rates, mortality, vaccine coverage
- Climate: NOAA and NASA — temperature anomalies, sea level, CO2
- Politics: official polling aggregates, electoral commission data

These three layers update at very different speeds — Wikipedia edits happen in minutes, social data updates daily, official indicators update weekly or monthly. The ingestion pipeline resamples all three to a common 1-hour window using forward-fill, so the scoring engine is always comparing the same slice of time across all sources.

---

## The Sanity Score

Every tracked topic receives a **Sanity Score from 0 to 100**:

- **100** — narrative is fully grounded; public attention tracks what official data says
- **0** — narrative is completely detached; the story being told has no grounding in verified information

The score is computed from three signals:

**S1 — Narrative Velocity (weight 0.25)**  
How fast is the Wikipedia edit rate shifting relative to its historical baseline? Rapid shifts signal that the narrative is being actively rewritten, often ahead of any verified development. Weight is lowest because fast edits can also reflect legitimate knowledge-building.

**S2 — Hype Spike (weight 0.40)**  
How far above normal is the current social volume? Measured as a z-score against a 7-day rolling baseline. This carries the highest weight because historical benchmarks consistently show that abnormal social attention is the primary driver of narrative distortion — it precedes Wikipedia overcorrection by 24 to 48 hours.

**S3 — Reality Divergence (weight 0.35)**  
How large is the gap between narrative intensity and what official data implies? A topic where Wikipedia activity is surging but official indicators show nothing unusual scores high on this signal. This carries the second-highest weight because the gap between attention and evidence is the core of what CrowdAudit is measuring.

```
IrrationalityIndex = (0.25 × S1) + (0.40 × S2) + (0.35 × S3)
SanityScore = round((1 − IrrationalityIndex) × 100)
```

| Score  | Label        |
| ------ | ------------ |
| 90–100 | Grounded     |
| 70–89  | Mostly sound |
| 50–69  | Drifting     |
| 30–49  | Distorted    |
| 0–29   | Detached     |

---

## Adversarial Check

Every score above 50 irrationality passes through an adversarial counter-narrative check before being finalised. The system asks: _"What if the public is right and the official data is lagging?"_

This matters because official statistics have publication delays — a real health crisis may not appear in monthly case rate data for weeks, while Reddit and Wikipedia respond immediately. When a plausible counter-narrative exists, the result is flagged `low_confidence: true` and the specific counter-narrative is included in the API response so users can evaluate it themselves.

---

## File Structure

```
crowdaudit/
│
├── README.md                     ← This file
├── TESTING.md                    ← Step-by-step test commands for every module
│
├── ingestion/
│   └── temporal_align.py         ← Syncs three data sources to a common 1-hour window
│
├── scoring/
│   └── sanity_score.py           ← Weighted irrationality formula + adversarial check
│
├── api/
│   └── endpoint.py               ← FastAPI server exposing the Sanity Score as a REST API
│
├── zerve_prompts/
│   └── zerve_prompts.py          ← Zerve agent exploration and adversarial prompts
│
└── benchmarks/
    └── gold_events.json          ← 5 historical crowd-wrong events for formula calibration
```

---

## Setup

```bash
# Install dependencies
pip install pandas numpy fastapi uvicorn httpx pytrends requests python-dotenv

# Copy the environment template and fill in your keys
cp .env.example .env

# Run quick self-tests
python ingestion/temporal_align.py
PYTHONPATH=. python scoring/sanity_score.py

# Start the API server
PYTHONPATH=. uvicorn api.endpoint:app --reload --port 8000
```

API documentation is available at `http://localhost:8000/docs` once the server is running.

---

## API

```
GET /health
GET /v1/sanity-score/{topic_id}
GET /v1/topics/ranked?limit=20&min_irrationality=0.0&data_domain=health
```

The `/v1/topics/ranked` endpoint returns all tracked topics sorted by irrationality descending. The `data_domain` filter accepts `economic`, `health`, `political`, or `climate`.

Each response includes the full signal breakdown (S1/S2/S3), the top keywords driving the hype spike, a plain-English reason string, the adversarial notes if `low_confidence` is true, and the raw narrative intensity vs. data-implied score for the dashboard to display as a before/after comparison.

---

## Data Sources

| Source                   | Domain     | Cadence          | How to get access                           |
| ------------------------ | ---------- | ---------------- | ------------------------------------------- |
| Wikipedia API            | All topics | Real-time        | No key needed — public REST API             |
| Google Trends (pytrends) | All topics | Daily            | No key needed                               |
| Reddit API               | All topics | Daily            | Free account at reddit.com/prefs/apps       |
| NewsAPI                  | All topics | Daily            | Free tier at newsapi.org                    |
| FRED                     | Economic   | Monthly / weekly | Free key at fred.stlouisfed.org             |
| WHO GHO API              | Health     | Weekly           | No key needed — public REST API             |
| NOAA Climate API         | Climate    | Monthly          | Free key at www.ncdc.noaa.gov/cdo-web/token |
| Electoral data           | Political  | As released      | Varies by country                           |
