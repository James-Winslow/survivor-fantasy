# Project Plan — survivor-fantasy

Living planning document. Updated as decisions are made.

## Status

- [x] Directory structure
- [x] README
- [x] config.yaml (all scoring rules externalized)
- [x] pyproject.toml (installable package)
- [x] Makefile (pipeline entry points)
- [x] .gitignore
- [x] Pydantic input/output schemas
- [x] Module stubs with docstrings
- [x] Data dictionary
- [ ] DB schema DDL (schema.py) ← next
- [ ] survivoR R export script
- [ ] ingest.py (historical data → DuckDB)
- [ ] ingest_s50.py (events.csv → DuckDB)
- [ ] features.py (feature store)
- [ ] scorer.py
- [ ] publish.py
- [ ] Dashboard v1

## Decisions Made

See README for full architectural rationale.

| Decision | Choice | Rationale |
|---|---|---|
| Database | DuckDB | Columnar, analytical, file-based, parquet-native |
| Package structure | src/ layout | Proper installable package, not scripts |
| Config | config.yaml | All scoring rules + paths externalized |
| Frontend | Static site | Netlify deploy, no server, portfolio-friendly |
| Data git strategy | Gitignore everything in data/ | Documented rebuild, keeps repo clean |
| Historical data | survivoR R package | TC-grain, S1–S49, maintained through 2026 |
| Layer separation | Layer 1 (show) / Layer 2 (league) | General-purpose data platform |
| Feature store | Materialized parquets | Models never query raw tables |
| JSON contract | Pydantic-validated | Bad data can't silently break frontend |

## Intentionally Deferred (schema-ready, not yet built)

The following features have table definitions and indexes already in place
but will not be implemented until the base database is complete and stable:

- **Collaborative data entry interface** — submission_queue table exists,
  Pydantic input schemas exist, review/approve workflow designed.
  Build after: base ingestion, scoring engine, and dashboard v1 are working.

- **Web scraping pipeline** — scrape_log and player_postseason_statements
  tables exist. Scraper modules stubbed in src/survivor_fantasy/nlp/.
  Build after: historical analysis is producing real results worth enriching.

- **Claude-assisted claim extraction** — extracted_claims field on
  submission_queue is ready. Phase 4 NLP pipeline feeds it.
  Build after: scraping pipeline exists and has real data to process.

- **Social media ingestion** — social_media_posts table exists.
  Build after: post-season statement pipeline is working.

The design principle: infrastructure exists, implementation waits.
Adding these features later requires zero schema changes.

---

## Phase Gates

### Phase 1 Gate
Query: "Give me everything about every player still active in S45 episode 5"
Expected: tribe, votes received, idol status, challenge results, confessionals
Layer 1 only — no league context required.

### Phase 2 Gate
Query: "What did each league member score in S50 episode 3, broken down by event?"
Expected: shareable dashboard URL with accurate per-player breakdowns

### Phase 3 Gate
Query: "Who should I start this week?"
Expected: optimizer recommendation with probability estimates and confidence tiers
