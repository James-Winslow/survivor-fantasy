# survivor-fantasy

A general-purpose Survivor data platform and fantasy league analytics engine, built on top of fifty seasons of episode-level data from the `survivoR` R package.

This project has two layers, kept deliberately separate:

**Layer 1 — Survivor Data Platform**: A normalized DuckDB database covering every season, episode, tribal council, vote, challenge, advantage, and confessional from Survivor US S1–S49, extended with live Season 50 data during the current season. This layer knows nothing about fantasy leagues. It is a research-grade dataset intended to support any Survivor analysis.

**Layer 2 — Fantasy League Application**: A scoring engine, weekly roster optimizer, and static web dashboard built on top of Layer 1. Specific to one league's scoring rules, which are fully externalized to `config.yaml`.

---

## What This Project Does

Each week during Survivor Season 50, this pipeline:

1. Accepts a small manual event log (`data/season50/events.csv`) capturing what happened in the episode
2. Computes fantasy league scores for all league members based on their rosters
3. Updates a Bayesian survival model with new information about each player's threat level
4. Produces a start/bench recommendation for the coming week
5. Publishes a static dashboard to Netlify with leaderboard standings and per-player score breakdowns

---

## Quickstart

### Prerequisites

- Python 3.11+
- R (for the one-time survivoR export step — see below)

### Installation

```bash
git clone https://github.com/James-Winslow/survivor-fantasy
cd survivor-fantasy
pip install -e ".[dev]"
```

### Data Setup (one-time)

The historical database is not committed to this repo. Rebuild it with:

```bash
# Step 1: Export survivoR data from R (one-time)
# Install the survivoR package in R and run:
#   source("scripts/export_survivoR.R")
# This writes CSVs to data/survivoR_exports/

# Step 2: Ingest historical data into DuckDB
make ingest

# Step 3: Materialize feature store
make build
```

See `docs/data_dictionary.md` for a full description of every table and field.

### Weekly Update (after each episode)

```bash
# 1. Fill in data/season50/events.csv with this episode's events
# 2. Run the full pipeline
make all
# 3. Push to deploy
git add frontend/data/ && git commit -m "Episode N scores" && git push
```

---

## Project Structure

```
survivor-fantasy/
│
├── config.yaml                 All configurable values (paths, scoring rules,
│                               model parameters). Single source of truth.
│
├── Makefile                    Pipeline entry points. Run `make help`.
├── pyproject.toml              Package definition and dependencies.
│
├── data/
│   ├── survivoR_exports/       Raw CSVs exported from the survivoR R package.
│   │                           Gitignored — see docs/data_dictionary.md to rebuild.
│   ├── season50/
│   │   ├── events.csv          Manual episode event log (your weekly input).
│   │   └── rosters.csv         League player rosters for the current season.
│   └── features/               Materialized feature parquets. Gitignored, rebuilt
│                               by `make build`.
│
├── src/survivor_fantasy/
│   ├── db/
│   │   ├── schema.py           CREATE TABLE DDL for all Layer 1 and Layer 2 tables.
│   │   └── connect.py          DuckDB connection factory (reads db_path from config).
│   │
│   ├── pipeline/
│   │   ├── ingest.py           survivoR CSVs → normalized DuckDB tables (Layer 1).
│   │   ├── ingest_s50.py       events.csv → DB (extends Layer 1 with live data).
│   │   ├── features.py         Raw DB tables → materialized feature store.
│   │   ├── scorer.py           Layer 1 events + Layer 2 rules → league points.
│   │   └── publish.py          Scores + model output → frontend/data/*.json.
│   │
│   ├── models/
│   │   ├── survival.py         Kaplan-Meier curves and Cox PH model.
│   │   ├── network.py          Alliance graph construction and centrality scoring.
│   │   ├── bayesian.py         Beta-Binomial survival probability updater.
│   │   ├── challenges.py       Tribe strength model and challenge outcome prediction.
│   │   └── optimizer.py        Expected points aggregator → start/bench recommendation.
│   │
│   ├── nlp/                    Phase 4 — text-based feature extraction.
│   │   ├── confessionals.py    Sentiment, agency, and loyalty scoring from transcripts.
│   │   └── edit_classifier.py  Winner's edit classifier trained on historical data.
│   │
│   ├── schemas/
│   │   ├── episode_output.py   Pydantic models for validated JSON output contract.
│   │   └── events_input.py     Pydantic models for validated events.csv input.
│   │
│   └── viz/
│       ├── survival_plots.py   Kaplan-Meier and hazard ratio visualizations.
│       ├── network_plots.py    Alliance network graph renderings.
│       └── posterior_plots.py  Bayesian posterior distribution visualizations.
│
├── frontend/                   Static site deployed to Netlify.
│   ├── index.html              Season leaderboard.
│   ├── scorecard.html          Per-player episode score breakdown.
│   ├── css/styles.css
│   ├── js/
│   │   ├── leaderboard.js
│   │   └── scorecard.js
│   └── data/                   JSON files written by publish.py. Gitignored
│                               except when deploying.
│
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_survival_analysis.ipynb
│   ├── 03_network_analysis.ipynb
│   ├── 04_bayesian_model.ipynb
│   └── 05_nlp_experiments.ipynb
│
├── tests/
├── docs/
│   ├── schema.md               Full DB schema documentation with field descriptions.
│   ├── data_dictionary.md      All data sources, how to obtain them, and what they mean.
│   └── modeling.md             Statistical methods, assumptions, and validation approach.
│
└── notes/
    ├── on_strategy_and_bias.md     Essay: strategic voting, structural bias, feedback loops.
    ├── methods_explainer.md        Lay explanation of survival analysis and Bayesian updating.
    └── project_plan.md             Living planning document.
```

---

## The Data

### Historical Data (Layer 1)

All historical data is sourced from the [`survivoR` R package](https://github.com/doehm/survivoR) maintained by Dan Oehm, which covers US Survivor S1–S49 at episode and tribal council grain. The package is sourced primarily from Wikipedia and is updated through recent seasons.

Key tables loaded from survivoR:

| Table | Grain | Key fields |
|---|---|---|
| `seasons` | Season | format, location, n_players, n_episodes |
| `players` | Player-Season | age, gender, placement, jury_votes |
| `episodes` | Episode | air_date, merge_occurred, swap_occurred |
| `tribal_councils` | TC | tribe, tc_type |
| `votes` | Vote | voter, voted_for, nullified, immunity_type |
| `challenges` | Challenge | type, format, winner |
| `advantages` | Advantage event | type, found_by, played_by, outcome |
| `confessionals` | Player-Episode | count, screen_time |

### Live Data (Season 50, Layer 1 extension)

Season 50 data is entered manually via `data/season50/events.csv` after each episode airs. The schema mirrors the historical tables exactly, allowing all models and queries to operate on combined data without branching logic.

See `docs/data_dictionary.md` for the full events.csv field specification and entry instructions.

### Layer 2 — League Data

League rosters, scoring rules, and computed scores live in separate tables and are never mixed into Layer 1. The scoring rules are defined entirely in `config.yaml` — the scorer contains no hardcoded point values.

---

## Analytical Methods

### Survival Analysis

Player elimination is modeled as a survival problem — each episode is a time step, and elimination is the event. Kaplan-Meier curves estimate unconditional survival functions stratified by player archetype, merge phase, and demographic group. Cox proportional hazards models estimate the effect of time-varying covariates (votes received, alliance centrality, idol possession) on instantaneous elimination risk.

This framing is natural given the project author's background in biostatistics: the math is identical to clinical trial survival analysis, with episodes replacing days and elimination replacing the clinical endpoint.

### Alliance Network Analysis

An alliance index is computed for every pair of players who attended the same tribal councils, based on co-voting frequency. This produces a weighted graph at each episode where edge weights encode relationship strength. Network centrality measures (degree, betweenness, eigenvector) identify players who are structurally central vs. peripheral to their alliance — a strong predictor of short-term elimination risk.

### Bayesian Survival Probability

Each player carries a Beta-distributed prior on their per-episode survival probability, initialized from historical base rates for their archetype and updated each episode using a Beta-Binomial conjugate model. This produces credible intervals rather than point estimates — allowing the optimizer to distinguish between "confidently safe" and "uncertain but probably safe."

This approach directly parallels Bayesian methods used in fraud analytics: a prior belief about a baseline rate, updated continuously as new observations arrive.

### Roster Optimizer

Expected points per player per episode are estimated as a weighted sum over all scoreable events, where each event probability is drawn from the models above. The optimizer recommends starting the 5 players with highest expected points from the current 8-player roster, with an override flag for players in structurally high-variance positions (idol possession, immunity run).

### NLP Layer (Phase 4)

Confessional transcripts are scored for sentiment, expressed loyalty to named allies, and explicit threat assessments. A winner's edit classifier trained on historical seasons attempts to identify players receiving disproportionate narrative attention — a known predictor of deep game runs. See `notes/methods_explainer.md` for a plain-language walkthrough.

---

## Further Reading

- `docs/modeling.md` — detailed statistical methods and assumption documentation
- `docs/data_dictionary.md` — every field, every table, every data source
- `notes/on_strategy_and_bias.md` — an essay on strategic voting, structural bias, and what Survivor data reveals about collective decision-making under bias
- `notes/methods_explainer.md` — survival analysis and Bayesian updating explained through the lens of Survivor, intended for non-statistician readers

---

## Roadmap

| Phase | Description | Status |
|---|---|---|
| 1 | Database schema, historical ingestion, S50 event schema | 🔨 In progress |
| 2 | Scoring engine, dashboard v1, README | 🔨 In progress |
| 3 | Survival models, network analysis, Bayesian model, optimizer | ⏳ Planned |
| 4 | NLP layer, winner's edit classifier, season explorer | ⏳ Planned |

---

## Author

Jimmy Winslow · [james-winslow.github.io](https://james-winslow.github.io) · Data Scientist
