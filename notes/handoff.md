# survivor-fantasy — Session Handoff Document
**Date**: March 25, 2026 (ep5 night)
**Transcript location**: /mnt/transcripts/2026-03-25-19-58-45-survivor-fantasy-pipeline.txt

---

## Current State — What's Working

- **Full pipeline working on both Mac and Windows**
- **GitHub Pages live**: 
  - https://james-winslow.github.io/survivor-fantasy/buffs.html
  - https://james-winslow.github.io/survivor-fantasy/fjv.html
- **DB through ep4** (Mike White voted out)
- **Elimination tracking** via `season_state` table (authoritative, from `still_in_game=0`)
- **Mac setup**: uses `bootstrap_s50.py` for minimal DB (no S1-S49 history needed)
- **venv**: `.venv/` in project root, activate with `source .venv/bin/activate` or `sfenv` alias
- **Scoring**: all 8 picks score per manager (active/bench NOT yet implemented)

---

## Current Standings (through ep4, all 8 scoring)

**In the Buffs League:**
1. Chris Roth 184
2. Amy 182
3. Natalie Bailey 173
4. Jimmy Winslow 170 (tied)
4. Lo 170 (tied)
6. The Merpenters 164
7. Joe 155
8. Lindsay Beaty 154
9. rachel fagan 125

**FJV Survivor Heads League:**
1. Austin Dickman 190
2. Alec Hartman 183
3. Kaitlynn Durham 178
4. Jimmy Winslow 170
5. Sidney 135

---

## Jimmy Winslow FJV Roster (current, ep5)

**Starters (5):** Rick Devens, Genevieve Mushaluk, Jonathan Young, Charlie Davis, Dee Valladares
**Bench (3):** Christian Hubicki, Ozzy Lusth, Emily Flippen

UUID mapping confirmed via console script on tribal-council.com:
- 3ba2b294 = Rick Devens
- 8682d041 = Genevieve Mushaluk
- d794dd7f = Jonathan Young
- ab8ea829 = Charlie Davis
- 24577db8 = Dee Valladares
- 1e8e16fa = Christian Hubicki (bench)
- c5d0e6ea = Ozzy Lusth (bench)
- 1a580ce6 = Emily Flippen (bench)

---

## All FJV Manager Rosters (current ep5, scraped via console script)

**Austin Dickman starters:** Charlie Davis, Christian Hubicki, Rizo Velovic, Genevieve Mushaluk, Joe Hunter
**Austin bench:** Kamilla Karthigesu, Mike White (eliminated), Cirie Fields

**Alec Hartman starters:** Angelina Keeley, Charlie Davis, Christian Hubicki, Colby Donaldson, Joe Hunter
**Alec bench:** Genevieve Mushaluk (big miss!), Emily Flippen, Stephenie LaGrossa

**Kaitlynn Durham starters:** Christian Hubicki, Cirie Fields, Kamilla Karthigesu, Genevieve Mushaluk, Ozzy Lusth
**Kaitlynn bench:** Dee Valladares, Rick Devens, Tiffany Ervin

**Sidney starters:** Angelina Keeley, Kamilla Karthigesu, Cirie Fields, Mike White (eliminated!), Jenna Lewis (eliminated!)
**Sidney bench:** Emily Flippen, Christian Hubicki, Dee Valladares

---

## S50 Current Game State (after ep4)

**Eliminated**: Jenna Lewis (ep1), Kyle Fraser (ep1 medevac), Savannah Louie (ep2), Q Burdette (ep3), Mike White (ep4)
**Remaining**: 19 players

**Tribe compositions (post-ep3 swap, unchanged ep4):**
- Cila: Charlie Davis, Cirie Fields, Dee Valladares, Jonathan Young, Kamilla Karthigesu, Rick Devens, Rizo Velovic
- Kalo: Aubry Bracco, Benjamin Wade, Chrissy Hofbeck, Colby Donaldson, Genevieve Mushaluk, Joe Hunter, Tiffany Ervin
- Vatu: Angelina Keeley, Christian Hubicki, Emily Flippen, Ozzy Lusth, Stephenie LaGrossa

**Ep5 context ("Open Wounds", tonight March 25):**
- DOUBLE ELIMINATION — two tribes sent to TC, only one tribe safe
- Charlie vs Rizo "Operation Bad Blood" rivalry peaks on Cila
- Vatu has been losing every challenge, likely goes to TC again
- Ozzy pissed after being left out of Mike vote
- Rick Devens recognizes he may be on the bottom of Cila (original Kalo majority)
- Stephenie on the outs on Vatu

---

## Key File Locations

**Local Mac**: ~/Documents/Projects/DataScience/survivor-fantasy
**Local Windows**: C:\Users\james\Projects\DataScience\Repositories\survivor-fantasy
**Repo**: github.com/James-Winslow/survivor-fantasy

**Key files:**
- `data/season50/events.csv` — manual weekly entry, 87 rows through ep4
- `data/season50/rosters.csv` — 112 rows, 14 manager×league combinations
- `data/survivor.duckdb` — gitignored, rebuild per machine
- `bootstrap_s50.py` — Mac minimal DB setup
- `src/survivor_fantasy/pipeline/ingest_s50.py` — loads episodes through ep4
- `src/survivor_fantasy/pipeline/scorer.py` — scoring engine
- `src/survivor_fantasy/pipeline/publish.py` — generates HTML dashboards
- `docs/buffs.html`, `docs/fjv.html` — GitHub Pages output

---

## Player Name Mapping (events.csv → DB)

| events.csv | DB full_name |
|---|---|
| Benjamin "Coach" Wade | Benjamin Wade |
| Jenna Lewis-Dougherty | Jenna Lewis |
| Ozzy Lusth | Oscar Lusth |
| Stephenie LaGrossa Kendrick | Stephenie LaGrossa |
| Joseph "Joe" Hunter | Joe Hunter |
| Tiffany Ervin | Tiffany Nicole Ervin |

---

## Weekly Pipeline (run after each episode)

```bash
# Mac
cd ~/Documents/Projects/DataScience/survivor-fantasy
source .venv/bin/activate   # or: sfenv

# 1. Add new episode rows to data/season50/events.csv
# 2. Add episode to EPISODES list in ingest_s50.py
# 3. Run pipeline
python src/survivor_fantasy/pipeline/ingest_s50.py
python src/survivor_fantasy/pipeline/scorer.py
python src/survivor_fantasy/pipeline/publish.py

# 4. Push
git add docs/buffs.html docs/fjv.html src/survivor_fantasy/pipeline/ingest_s50.py
git commit -m "ep5 scores: [who was voted out]"
git push
```

---

## Immediate Next Steps (do after ep5 airs tonight)

1. **Enter ep5 events.csv data** — double elimination, two boots
2. **Add ep5 to EPISODES list in ingest_s50.py**:
   ```python
   (5, 'Open Wounds', '2026-03-25', False, 19, 17),
   ```
   Note: `is_merge=False`, starts with 19, ends with 17 (two eliminations)
3. **Run pipeline and push**

---

## Backlog — Prioritized

### High priority (correctness)
1. **Active/bench scoring** — biggest gap vs tribal-council.com scores
   - Need `is_starter` per player per episode in `league_rosters`
   - Console script approach works for scraping (UUID extraction confirmed)
   - Need to build scraper that hits each episode tab per manager
   - Scorer needs `WHERE is_starter = TRUE` filter

2. **Missing scoring events** — from tribal-council.com episode feed:
   - Journey/summit participation (`participates_in_summit_pts: 1`)
   - Boomerang idol gifted (`gifts_boomerang_idol_pts: 1`) — currently using `found_idol_clue`
   - Boomerang idol received (`receives_boomerang_idol_pts: 3`) — currently missing
   - Extra vote earned (`earns_extra_vote_pts: 3`) — Ozzy ep1, Savannah ep1
   - Need 4 new columns in events.csv: `gifted_boomerang_idol`, `received_boomerang_idol`, 
     `received_extra_vote`, `played_extra_vote`

3. **events.csv audit ep1-4** — several known errors:
   - Genevieve ep1: should score finds_idol (3) + gifts_boomerang (1), not just idol_clue (1)
   - Aubry ep2: received boomerang from Christian — missing +3
   - Ozzy ep1: received boomerang — scored as idol_clue (+1) but should be +3
   - Cirie ep1: received extra vote from Ozzy — missing +3
   - Journey participants ep1: Coach, Ozzy, Q on journey (+1 each) — missing
   - Savannah ep1: won advantage on journey (+3) — missing

### Medium priority (architecture)
4. **`season_state` table in schema.py** — currently created inline in ingest_s50.py
5. **`league_players` DDL in schema.py** — stale, has old UNIQUE(name) constraint
6. **Remove confessional skip logic** — no longer needed since season_state is authority
7. **pyproject.toml build-backend** — confirmed fixed to `setuptools.build_meta`

### Lower priority (features)
8. **Dashboard per-episode drill-down modal**
9. **Boomerang idol chain visualization**
10. **Survivor optimizer** ("who should I start?" — Phase 3)

---

## Architecture Decisions (locked)

| Decision | Choice | Rationale |
|---|---|---|
| Elimination authority | `season_state` table | Direct from `still_in_game=0` in events.csv |
| episode_id scheme | season_id * 1000 + episode_num | e.g. S50 ep5 = 50005 |
| Dashboard data | JSON embedded inline in HTML | No CORS issues for local file opening |
| League separation | `league_players.league_name` column | Jimmy appears twice (once per league) |
| Mac setup | bootstrap_s50.py minimal DB | Full historical DB only on Windows |
| Layer separation | Layer 1 (show facts) / Layer 2 (league) | Layer 1 has zero league knowledge |
| Scoring scope | All 8 picks score (pending fix) | is_starter implementation in progress |

---

## Technical Debt — Documented Assumptions

- **Confessional skip logic**: ingest_s50.py skips confessional rows for eliminated 
  players in their exit episode. This was a workaround before season_state existed.
  Should be removed — it corrupts confessional count analytics.

- **Double elimination episodes**: The confessional-absence approach to elimination 
  detection would fail for these. season_state table handles it correctly since it 
  reads `still_in_game=0` directly. Ep5 is the first double elimination test.

- **Boomerang idol scoring**: Currently using `found_idol_clue=1` as a proxy for 
  boomerang events. This is wrong — clue is +1, receiving boomerang is +3. 
  All episodes need retroactive correction once new fields are added.

- **players.exit_type**: Unreliable for live S50 — all returnees default to 'voted_out'. 
  Never use for elimination detection. Use season_state only.
