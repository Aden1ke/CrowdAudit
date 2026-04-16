# CrowdAudit

**An AI-powered prediction market irrationality detector**  
ZerveHack 2026 | Deadline: April 29 @ 7:00PM GMT+1

---

## What It Is

Prediction markets like Polymarket and Kalshi are often cited as the most accurate forecasters in the world — people bet real money on real outcomes, so the incentive to be right is strong. But there's a hidden flaw: when social media hype spikes around an event, crowds pile in not because the data supports it, but because the noise is deafening.

CrowdAudit detects that drift in real time. It watches three layers of data simultaneously — market odds, search volume, and economic indicators — and surfaces a **Sanity Score (0–100)** for any live market:

- **100** — fully rational, market reflects economic reality
- **0** — pure hype, the crowd is flying blind

---

## How It Works

Three data sources feed into a single scoring pipeline:

**Market consensus (Polymarket / Kalshi)** — real-money prediction market odds, updated every few seconds. This is what the crowd currently believes, with skin in the game.

**Public hype (Google Trends / Reddit)** — search volume and social media activity around an event topic. High volume often precedes irrational market moves; the crowd follows noise.

**Ground reality (FRED — Federal Reserve Economic Data)** — unemployment, CPI, fed funds rate, GDP. Slow-moving but honest. When market odds diverge from what this data implies, that's where the signal lives.

The insight is in the **space between** these three sources. One dataset alone tells you nothing. The gap between all three tells you everything.

---

## The Sanity Score Formula

```
IrrationalityIndex = (0.25 × S1) + (0.40 × S2) + (0.35 × S3)
SanityScore = round((1 − IrrationalityIndex) × 100)
```

**S1 — Odds Velocity (weight 0.25)**  
How fast are market odds moving relative to their historical volatility? A market moving 3× its normal daily range scores S1 = 1.0. Velocity is a lagging confirmation — fast movement can indicate real news, so it carries the lowest weight.

**S2 — Hype Spike (weight 0.40)**  
How far above baseline is the current search volume? Computed as a z-score against a 7-day rolling average. A 3-sigma spike scores S2 = 1.0. This gets the highest weight because historical benchmarks show Trends spikes are the primary driver of irrational markets — they precede price peaks by 24–48 hours.

**S3 — Economic Divergence (weight 0.35)**  
How far is the market's implied probability from what FRED economic data would predict? A 35 percentage-point gap between market odds and FRED-implied probability scores S3 = 1.0. This gets the second-highest weight because fundamental data is the ground truth — when markets drift from it without a corresponding FRED move, that's the clearest irrationality signal.

**Score interpretation:**

| Range  | Label                 |
| ------ | --------------------- |
| 90–100 | Highly rational       |
| 70–89  | Mostly rational       |
| 50–69  | Warning zone          |
| 30–49  | Irrational            |
| 0–29   | Detached from reality |

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

## Module Reference

### `ingestion/temporal_align.py`

The data collision engine. Polymarket updates every few seconds, Google Trends updates daily, and FRED updates monthly. This module resamples all three down to a common 1-hour window so the scoring engine is always comparing the same slice of time across all sources.

The core technique is **forward-fill with staleness tracking**: when a daily or monthly source hasn't updated yet, the last known value carries forward — but a staleness counter tracks how old it is. Rows that exceed staleness limits are flagged with `any_source_stale = True` and skipped by the scoring engine.

Key functions:

`align_all_sources(polymarket_df, trends_df, fred_df, market_id, lookback_hours=168)` — master join. Takes raw DataFrames from each source and returns a single wide DataFrame, one row per hour, aligned on a UTC DatetimeIndex.

`compute_historical_volatility(aligned_df, window_hours=72)` — adds `odds_volatility_baseline`, the rolling standard deviation of implied probability over the past 72 hours. Must be called before scoring; the S1 signal depends on it.

**Aligned DataFrame columns:**

| Column                        | Type         | Description                                 |
| ----------------------------- | ------------ | ------------------------------------------- |
| `timestamp`                   | datetime UTC | Hour window start                           |
| `market_id`                   | str          | Market identifier                           |
| `implied_prob`                | float        | Closing probability for the hour            |
| `polymarket_high` / `_low`    | float        | Price range within the hour                 |
| `search_volume`               | float        | Google Trends index (0–100), forward-filled |
| `google_trends_staleness_hrs` | int          | Hours since last real Trends update         |
| `indicator_value`             | float        | FRED value, forward-filled                  |
| `fred_staleness_hrs`          | int          | Hours since last real FRED update           |
| `any_source_stale`            | bool         | True if any source is too stale to trust    |
| `odds_volatility_baseline`    | float        | 72-hour rolling std of implied_prob         |

---

### `scoring/sanity_score.py`

The core of the project. Implements the three signal functions, the weighted composite, an explainability layer that produces a plain-English reason string, and an adversarial counter-narrative check.

**Signal functions:**

`compute_S1_odds_velocity(df, window_hours=24)` — returns a float 0–1. Computes `mean(|hourly_prob_change|) / historical_std / 3.0`, capped at 1.0.

`compute_S2_hype_spike(df, window_hours=48, baseline_window=168)` — returns `(float, list[str])`. Z-scores recent search volume against a 7-day baseline, normalised to 0–1. Also returns `top_keywords` (wire to Reddit API for production; placeholder in current version).

`compute_S3_econ_divergence(df, fred_series_type)` — returns `(float, float)`. Maps the FRED indicator value to an implied probability using calibrated heuristics, then measures the gap against market odds. Returns both the S3 score and the `fred_implied_prob` for the API response. Supported series types: `"unemployment"`, `"cpi"`.

`adversarial_counter_check(S1, S2, S3, implied_prob, fred_implied_prob)` — runs after scoring. If any signal is below the ambiguity threshold (default 0.20), the check asks: "what if the crowd is right?" It flags plausible counter-narratives — hidden variables not captured by FRED or Trends, cases where the FRED series may be the wrong proxy — and marks the result `low_confidence = True`.

`compute_sanity_score(aligned_df, market_id, fred_series_type)` — master function that chains everything and returns a `SanityScoreResult` dataclass. Call `.to_json()` to get the API-ready JSON string.

Tunable constants at the top of the file: `WEIGHTS` (must sum to 1.0) and `ADVERSARIAL_AMBIGUITY_THRESHOLD` (default 0.20).

---

### `api/endpoint.py`

A FastAPI server exposing the Sanity Score over HTTP. Three endpoints:

```
GET /health
GET /v1/sanity-score/{market_id}
GET /v1/markets/ranked?limit=20&min_irrationality=0.0
```

`/v1/markets/ranked` returns all tracked markets sorted by irrationality descending — the primary feed for the dashboard's ranked list. The `min_irrationality` filter lets the UI show only markets above a chosen threshold.

**Full response schema per market:**

| Field                 | Type       | Description                                          |
| --------------------- | ---------- | ---------------------------------------------------- |
| `market_id`           | str        | Unique identifier                                    |
| `market_title`        | str        | Human-readable market question                       |
| `sanity_score`        | int 0–100  | The headline number                                  |
| `irrationality_index` | float 0–1  | Raw composite before inversion                       |
| `signal_breakdown`    | object     | S1, S2, S3 values and their weights                  |
| `divergence_vector`   | float      | market_implied_prob minus fred_implied_prob (signed) |
| `top_hype_keywords`   | string[]   | Terms driving the search volume spike                |
| `reason`              | str        | Plain-English explanation of the score               |
| `low_confidence`      | bool       | True if adversarial check raised a counter-narrative |
| `adversarial_notes`   | string[]   | The specific counter-narratives flagged              |
| `fred_implied_prob`   | float      | Probability the economic data predicts               |
| `market_implied_prob` | float      | Current crowd odds                                   |
| `computed_at`         | ISO string | UTC timestamp of computation                         |

Three mock markets are pre-loaded so the dashboard can be built against real API shapes immediately: `FED_RATE_CUT_JUL26` (score 31), `US_RECESSION_2026` (score 74), `BTC_100K_DEC26` (score 18).

---

### `zerve_prompts/zerve_prompts.py`

All the Zerve agent prompts in one place. The master exploration question asks the agent to find events where market odds shifted significantly but the underlying FRED indicators stayed flat. Specialised deep-dive prompts cover the Hype Lag Effect (does a Trends spike reliably predict a 48-hour price overcorrection?) and the Sure Thing Trap (are markets with 85%+ odds statistically overpriced when fundamentals don't support the certainty?).

`build_adversarial_prompt(market_id, score, S1, S2, S3)` generates a market-specific devil's advocate prompt — "assume the crowd is correct, what are we missing?" — used to stress-test any market that scores below 40.

Also contains `FAILED_PATH_LOG_TEMPLATE` for documenting agent sessions that went off-track and how they were corrected, and `API_DOCUMENTATION_FOR_ROLE_B`, a complete API reference formatted to share with the frontend developer.

---

### `benchmarks/gold_events.json`

Five historical prediction market failures used to validate that the formula weights produce the right answer on known cases before being trusted on live markets.

| ID   | Event                                         | Expected score range                         |
| ---- | --------------------------------------------- | -------------------------------------------- |
| B001 | 2022 'transitory inflation' markets           | 20–30                                        |
| B002 | 2020 V-shaped recovery markets                | 15–25                                        |
| B003 | 2022 UK recession markets (post-Truss budget) | 45–55 (borderline — should not over-trigger) |
| B004 | 2021 Bitcoin $100K markets                    | 15–25                                        |
| B005 | 2023 US debt ceiling default markets          | 55–65 with `low_confidence = True`           |

Calibration target: after running against real historical data for each benchmark, aim for Pearson r > 0.75 between `irrationality_index` and actual market error at expiry. If r < 0.75, adjust `WEIGHTS` in `sanity_score.py` and re-run.

---

## Setup

```bash
# Install dependencies
pip install pandas numpy fastapi uvicorn httpx pytrends requests python-dotenv

# Create a .env file in the project root
echo "FRED_API_KEY=your_key_here" > .env
echo "KALSHI_API_KEY=your_key_here" >> .env

# Quick smoke tests
python ingestion/temporal_align.py
PYTHONPATH=. python scoring/sanity_score.py

# Start the API server
PYTHONPATH=. uvicorn api.endpoint:app --reload --port 8000
# API docs available at http://localhost:8000/docs
```

See `TESTING.md` for the full test suite with expected outputs for every module.

---

## API Keys

| Source        | How to get it                                     | Cost                                 |
| ------------- | ------------------------------------------------- | ------------------------------------ |
| FRED          | https://fred.stlouisfed.org/docs/api/api_key.html | Free, instant                        |
| Kalshi        | https://trading.kalshi.com → Dashboard → API      | Free account                         |
| Polymarket    | https://docs.polymarket.com                       | No key needed for public market data |
| Google Trends | No key needed — uses the `pytrends` library       | Free                                 |
