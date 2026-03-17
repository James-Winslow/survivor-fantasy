# Project Plan — survivor-fantasy
Living planning document. Updated as decisions are made.

## Status

### Phase 1 — Historical Data Platform ✅
- [x] Directory structure
- [x] README
- [x] config.yaml (all scoring rules externalized)
- [x] pyproject.toml (installable package)
- [x] Makefile (pipeline entry points)
- [x] .gitignore
- [x] Pydantic input/output schemas
- [x] Module stubs with docstrings
- [x] Data dictionary
- [x] DB schema DDL (schema.py) — 29 tables, 132 indexes
- [x] survivoR R export script
- [x] ingest.py — all 12 Layer 1 tables loaded, S1–S49
- [x] sf-ingest --validate-only passes all 8 checks

### Phase 2 — S50 Live Scoring ✅ (through ep3)
- [x] scrape_rosters.py — scrapes tribal-council.com rosters (requires Chrome login)
- [x] fix_rosters.py — cleans scraped roster CSV
- [x] data/season50/rosters.csv — 14 manager×league entries, 112 survivors
- [x] data/season50/events.csv — episodes 1–3, 67 rows
- [x] ingest_s50.py — loads episodes, tribes, tribe_memberships, confessionals, league rosters
- [x] scorer.py — applies config.yaml rules, writes episode_scores + league_standings
- [x] publish.py — generates self-contained HTML dashboards (no CORS issues)
- [x] Dashboard v1 — buffs.html + fjv.html, Survivor palette, all four views

### Phase 2 — Remaining / Known Issues
- [ ] Active/bench tracking — see section below
- [ ] events.csv needs reward/immunity flag audit (ep1–3 data may have errors)
- [ ] scrape_rosters.py: browser_cookie3 doesn't work on this setup;
      workaround is manual cookie paste (cookies expire ~5 min, XSRF + tribal_council_session)
- [ ] Redraft rosters after ep3 tribe swap not yet captured

### Phase 3 — Models (deferred)
- [ ] features.py
- [ ] survival model
- [ ] challenge prediction model
- [ ] optimizer ("who should I start this week?")

### Phase 4 — NLP (deferred)
- [ ] confessional text ingestion
- [ ] edit classifier
- [ ] claim extraction

---

## Active / Bench System

tribal-council.com uses a **5 active / 3 bench** roster system:
- Each manager drafts 8 survivors
- Each episode, exactly 5 are "active" (score points) and 3 are "benched" (score nothing)
- Managers can change who is active/benched any time before episode lock (~5pm MST)
- Benched survivors earn and lose NO points that episode
- Redrafts (swap survivors in/out of the 8) are triggered by:
  - Before the season begins
  - After episode 1
  - After any tribe switch-up (swap, split, rocks, etc.)
  - At the final merge

**Current pipeline status:** `league_rosters.is_active` exists but is always `TRUE`.
We are scoring all 8 survivors per manager, which inflates scores vs tribal-council.com.

**To fix:** We need to know which 5 of each manager's 8 were active each episode.
This data is not in rosters.csv currently. Options:
1. Scrape the episode-specific roster view from tribal-council.com (preferred)
2. Manual entry by each manager
3. Accept the difference and note it in the dashboard

The tribal-council.com site shows "Episode 1", "Episode 2", "Episode 3" roster views
per league (visible in the screenshots). The scraper can likely pull these.

---

## Decisions Made

| Decision | Choice | Rationale |
|---|---|---|
| Database | DuckDB | Columnar, analytical, file-based, parquet-native |
| Package structure | src/ layout | Proper installable package, not scripts |
| Config | config.yaml | All scoring rules + paths externalized |
| Frontend | Static HTML | No server needed, opens locally or deploys to Netlify |
| Data git strategy | Gitignore everything in data/ | Documented rebuild, keeps repo clean |
| Historical data | survivoR R package | TC-grain, S1–S49, maintained through 2026 |
| Layer separation | Layer 1 (show) / Layer 2 (league) | General-purpose data platform |
| Feature store | Materialized parquets | Models never query raw tables |
| JSON contract | Pydantic-validated | Bad data can't silently break frontend |
| League separation | league_players has league_name column | Jimmy Winslow appears in both leagues with separate IDs |
| episode_id scheme | season_id * 1000 + episode_num | e.g. S50 ep3 = 50003, avoids collision with historical IDs |
| Dashboard data | JSON embedded inline in HTML | Avoids CORS issues when opening local files |
| Scoring scope | All 8 survivors scored (not 5) | Pending active/bench data; see above |

## Player Name Mapping (events.csv → DB)
The survivoR package uses different name formats than show credits:

| events.csv / rosters.csv | DB full_name |
|---|---|
| Benjamin "Coach" Wade | Benjamin Wade |
| Jenna Lewis-Dougherty | Jenna Lewis |
| Ozzy Lusth | Oscar Lusth |
| Stephenie LaGrossa Kendrick | Stephenie LaGrossa |
| Joseph "Joe" Hunter | Joe Hunter |
| Tiffany Ervin | Tiffany Nicole Ervin |

---

## Phase Gates

### Phase 1 Gate ✅
Query: "Give me everything about every player still active in S45 episode 5"
Expected: tribe, votes received, idol status, challenge results, confessionals
Layer 1 only — no league context required.

### Phase 2 Gate ✅ (partial)
Query: "What did each league member score in S50 episode 3, broken down by event?"
Expected: shareable dashboard URL with accurate per-player breakdowns
Status: Dashboard exists and shows breakdowns. Score totals differ from
tribal-council.com due to active/bench system not yet implemented.

### Phase 3 Gate
Query: "Who should I start this week?"
Expected: optimizer recommendation with probability estimates and confidence tiers

---

## Weekly Update Workflow (each Wednesday after episode airs)

1. Update `data/season50/events.csv` — add new episode rows
2. If redraft triggered: run `python scripts/scrape_rosters.py` to refresh rosters
3. `python src/survivor_fantasy/pipeline/ingest_s50.py`
4. `python src/survivor_fantasy/pipeline/scorer.py`
5. `python src/survivor_fantasy/pipeline/publish.py`
6. Open `frontend/buffs.html` and `frontend/fjv.html` to verify
