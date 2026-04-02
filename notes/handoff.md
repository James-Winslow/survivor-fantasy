# survivor-fantasy — Session Handoff Document
**Last updated**: April 1, 2026 (ep6 night — The Blood Moon, merge episode)
**Transcript**: /mnt/transcripts/2026-03-25-19-58-45-survivor-fantasy-pipeline.txt

---

## Current State — What's Working

- **Full pipeline working on Mac and Windows**
- **GitHub Pages live**:
  - https://james-winslow.github.io/survivor-fantasy/buffs.html
  - https://james-winslow.github.io/survivor-fantasy/fjv.html
- **DB through ep5** (Charlie Davis + Angelina Keeley voted out)
- **Ep6 events NOT yet entered** — do this next session
- **Elimination tracking** via `season_state` table (authoritative)
- **Mac setup**: `bootstrap_s50.py` for minimal DB
- **venv**: `.venv/` in project root, activate: `source .venv/bin/activate` or `sfenv`
- **Scoring**: all 8 picks score (active/bench NOT yet implemented in scorer)
- **starters.csv**: ep6 data captured for all 14 managers (both leagues)

---

## Current Standings (through ep5, all 8 scoring)

**In the Buffs League** (from pipeline output):
1. Amy 189 (was 182 through ep3 — note: Buffs ep4 data may need verification)
2. Jimmy Winslow 177
3. Natalie Bailey 173
4. Chris Roth 172
5. Lo 158
6. Joe 155
7. Lindsay Beaty 154
8. The Merpenters 152
9. rachel fagan 125

**FJV Survivor Heads League**:
1. Alec Hartman 190
2. Austin Dickman 185 (was leading before)
3. Kaitlynn Durham 178
4. Jimmy Winslow 177
5. Sidney 135

**tribal-council.com standings (ep6, their scoring)**:
- Buffs: Lindsay Beaty 308, Lo 289, Natalie Bailey 286, Joe 272, Jimmy 270, Merpenters 268, Chris Roth 266, rachel fagan 240, Amy 225
- FJV: Jimmy 270, Austin 204, Alec 202, Kaitlynn 193, Sidney 142

Note: Large gap between our scores and theirs due to:
1. Active/bench not implemented (all 8 score vs their 5)
2. Missing scoring events (journeys, boomerang idols, extra votes)
3. Post-merge survived pts = +6, not yet in our events.csv for ep6

---

## Ep6 "The Blood Moon" — What Happened

**Merge at 17 players** — largest in Survivor history.
**Blood Moon twist**: Players split into 3 groups, each voted someone out = 3 boots.

**Eliminated ep6**: Colby Donaldson, Genevieve Mushaluk, Kamilla Karthigesu

**Key ep6 scoring events** (from episode_feed.csv):
- Ozzy Lusth: Finds Twist +3, immunity by default +6
- Rizo Velovic: immunity by default +6
- Dee Valladares: wins individual immunity +6
- Christian Hubicki: wins individual immunity +6
- Stephenie LaGrossa: wins individual immunity +7 (bonus)
- Jonathan Young, Stephenie, Tiffany, Chrissy, Kamilla: reward participant +2/+3
- Merged Tribe survived a round (x3): +18 (applies to all survivors)

**ep6 NOT yet in events.csv or DB** — needs to be entered next session.

---

## Jimmy Winslow Rosters (ep6, confirmed)

**FJV starters**: Genevieve(OUT), Jonathan, Emily, Dee, Christian
**FJV bench**: Rick Devens, Ozzy, Charlie(OUT)

**Buffs starters**: Genevieve(OUT), Dee, Jonathan, Christian, Emily
**Buffs bench**: Rick, Charlie(OUT), Ozzy

Post-ep6: Genevieve eliminated, need to move someone up.
Options: Rick Devens or Ozzy Lusth for ep7.
Rick = safer, steadier. Ozzy = volatile, individual immunity threat.

---

## All Manager Rosters (ep6 current, from starters.csv)

### FJV Survivor Heads League
**Austin Dickman** starters: Christian, Rizo, Genevieve(OUT), Joe Hunter, Kamilla(OUT) | bench: Charlie(OUT), Mike(OUT), Cirie
**Alec Hartman** starters: Christian, Stephenie, Colby(OUT), Joe Hunter, Emily | bench: Charlie(OUT), Angelina(OUT), Genevieve(OUT)
**Kaitlynn Durham** starters: Christian, Cirie, Kamilla(OUT), Genevieve(OUT), Ozzy | bench: Dee, Rick, Tiffany
**Sidney** starters: Angelina(OUT), Kamilla(OUT), Cirie, Mike(OUT), Jenna(OUT) | bench: Emily, Christian, Dee

### In the Buffs League
**Lindsay Beaty** starters: Coach, Stephenie, Jonathan, Tiffany, Ozzy | bench: Q(OUT), Angelina(OUT), Emily
**Lo** starters: Aubry, Jonathan, Dee, Rick, Ozzy | bench: Mike(OUT), Cirie, Christian
**Natalie Bailey** starters: Jonathan, Dee, Rick, Ozzy, Aubry | bench: Christian, Cirie, Chrissy
**Joe** starters: Jonathan, Stephenie, Joe Hunter, Ozzy, Tiffany | bench: Christian, Emily, Rick
**The Merpenters** starters: Jonathan, Christian, Tiffany, Joe Hunter, Rizo | bench: Mike(OUT), Rick, Emily
**Chris Roth** starters: Ozzy, Colby(OUT), Aubry, Dee, Rizo | bench: Mike(OUT), Cirie, Stephenie
**rachel fagan** starters: Dee, Jonathan, Rizo, Joe Hunter, Ozzy | bench: Cirie, Stephenie, Christian
**Amy** starters: Colby(OUT), Rick, Genevieve(OUT), Kamilla(OUT), Joe Hunter | bench: Mike(OUT), Charlie(OUT), Christian

---

## S50 Game State (after ep6)

**Eliminated**: Jenna Lewis (ep1), Kyle Fraser (ep1 medevac), Savannah Louie (ep2),
Q Burdette (ep3), Mike White (ep4), Charlie Davis (ep5), Angelina Keeley (ep5),
Colby Donaldson (ep6), Genevieve Mushaluk (ep6), Kamilla Karthigesu (ep6)

**Remaining 14 players** (post-merge):
Aubry Bracco, Benjamin "Coach" Wade, Chrissy Hofbeck, Christian Hubicki,
Cirie Fields, Dee Valladares, Emily Flippen, Joe Hunter, Jonathan Young,
Oscar "Ozzy" Lusth, Rick Devens, Rizo Velovic, Stephenie LaGrossa, Tiffany Ervin

**Merge tribe**: All 14 playing together now. Post-merge scoring = +6 survived per ep.

---

## Key File Locations

**Local Mac**: ~/Documents/Projects/DataScience/survivor-fantasy
**Local Windows**: C:\Users\james\Projects\DataScience\Repositories\survivor-fantasy
**Repo**: github.com/James-Winslow/survivor-fantasy

**Data files** (gitignored — do NOT commit):
- `data/season50/events.csv` — manual weekly entry, through ep5
- `data/season50/rosters.csv` — 14 manager×league combinations
- `data/season50/starters.csv` — ep6 captured, eps 1-5 still needed
- `data/season50/episode_feed.csv` — 64 scoring events scraped from tc.com
- `data/season50/portrait_urls.csv` — correct image URLs for 18 contestants
- `data/season50/portraits/` — 18 downloaded portrait JPGs
- `data/season50/raw_html/` — scraped episode HTML (ep1-6)
- `data/survivor.duckdb` — rebuild per machine

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

## Weekly Pipeline

```bash
# Mac
sfenv   # or: cd project && source .venv/bin/activate
python status.py   # check what needs doing

# Add ep rows to data/season50/events.csv
# Add episode to EPISODES list in ingest_s50.py
python src/survivor_fantasy/pipeline/ingest_s50.py
python src/survivor_fantasy/pipeline/scorer.py
python src/survivor_fantasy/pipeline/publish.py
git add docs/buffs.html docs/fjv.html src/survivor_fantasy/pipeline/ingest_s50.py
git commit -m "epN scores: [who was voted out]"
git push

# Windows: use python not python3, no venv needed
```

**Before each episode** — collect starters via console script on tc.com:
```javascript
const results = {};
let currentManager = '';
document.querySelectorAll('tr, td, div').forEach(el => {
    const managerLink = el.querySelector && el.querySelector('a[href*="/players/"]');
    if (managerLink) currentManager = managerLink.textContent.trim();
    const onclick = el.getAttribute('onclick') || '';
    const dataSrc = el.getAttribute('data-src') || '';
    const style = el.getAttribute('style') || '';
    const combined = onclick + dataSrc + style;
    const m = combined.match(/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/);
    if (m && currentManager) {
        if (!results[currentManager]) results[currentManager] = [];
        const prefix = m[1].substring(0,8);
        if (!results[currentManager].includes(prefix)) results[currentManager].push(prefix);
    }
});
copy(JSON.stringify(results, null, 2));
console.log(Object.keys(results));
```

Then run:
```powershell
python scripts\batch_starters.py --episode 7 --league FJV
python scripts\batch_starters.py --episode 7 --league Buffs
```

---

## Immediate Next Steps

1. **Enter ep6 events.csv data** — 3 boots (Colby, Genevieve, Kamilla), immunities,
   reward participants, merge survived points. Reference episode_feed.csv for events.
2. **Add ep6 to EPISODES list** in ingest_s50.py:
   ```python
   (6, 'The Blood Moon', '2026-04-01', True, 17, 14),
   ```
   `is_merge=True`, starts 17, ends 14 (3 eliminated)
3. **Run pipeline and push dashboard**
4. **Decide ep7 bench** for Jimmy — Rick or Ozzy replaces Genevieve

---

## Backlog — Prioritized

### High (correctness)
1. **Active/bench scoring** — scorer needs `WHERE is_active = TRUE` filter
   - starters.csv loaded into league_rosters.is_active in ingest_s50.py
   - ep6 starters.csv done, eps 1-5 still needed retroactively
2. **Missing scoring events** — compare episode_feed.csv vs events.csv:
   - Journey participants (+1 each) — eps 1, 2, 4
   - Boomerang idol gifted/received — eps 1, 2, 4
   - Extra votes earned — ep1
   - Savannah's advantage — ep1
   - Rick's fake idol — ep2
   - Voted out events for Charlie/Angelina/Colby/Genevieve/Kamilla
3. **Retroactive starters.csv** for eps 1-5 — episode tabs on tc.com still accessible
   - Fetch via scrape_episodes.py (cookies still valid?) or console script per ep tab

### Medium (architecture)
4. **season_state table in schema.py** — currently inline in ingest_s50.py
5. **league_players DDL** stale in schema.py — has old UNIQUE(name) constraint
6. **Remove confessional skip logic** — season_state is now the authority

### Lower (features)
7. **Scoring explainer UI** in dashboard — per-event breakdown per survivor
8. **Bench impact visualization** — show benched players' would-be points
9. **Get remaining 6 portraits** — Angelina, Cirie, Emily, Jenna, Joe, Charlie
   via logged-in fetch of /contestants page
10. **Survivor optimizer** — Phase 3, post-season

---

## Architecture Decisions (locked)

| Decision | Choice | Rationale |
|---|---|---|
| Elimination authority | `season_state` table | Direct from `still_in_game=0` |
| episode_id scheme | season_id × 1000 + episode_num | S50 ep6 = 50006 |
| Dashboard data | JSON embedded inline in HTML | No CORS issues |
| League separation | `league_players.league_name` | Jimmy appears twice |
| Mac setup | bootstrap_s50.py minimal DB | Full historical DB on Windows only |
| Scoring scope | All 8 score (pending fix) | is_starter implementation in progress |
| Elimination detection | confessionals NOT used | season_state is sole authority |

---

## Scraping Infrastructure (new this session)

**Working console script** — extracts all manager rosters from league overview page.
Run on: `tribal-council.com/league/[league-uuid]`

**Episode URLs**:
- Ep1: tribal-council.com/episodes/b902d8e2-38cb-4af7-a4f2-b7ff1ec13074
- Ep2: tribal-council.com/episodes/60a6226b-2001-46ab-b400-e68e0cc5d842
- Ep3: tribal-council.com/episodes/94982834-0c48-4218-a12d-ddbcd2689935
- Ep4: tribal-council.com/episodes/b9def262-1aa0-43a9-9d4e-ef7c19b6901f
- Ep5: tribal-council.com/episodes/d98b0fec-8151-45d9-b47e-46b0cf51851c
- Ep6: tribal-council.com/episodes/current

**League URLs**:
- FJV: tribal-council.com/league/d6875609-2dee-4d1f-b6e5-dff95e8ae63f
- Buffs: tribal-council.com/league/5e332cfb-e13e-4c45-b117-49e25abe9cac

**Scripts added this session**:
- `scripts/scrape_episodes.py` — fetches episode pages with cookies → raw HTML
- `scripts/parse_episodes.py` — parses raw HTML → episode_feed.csv + portrait_urls.csv
- `scripts/download_portraits.py` — downloads portrait JPGs using correct URLs
- `scripts/batch_starters.py` — converts console script JSON → starters.csv rows
- `scripts/fix_starters.py` — one-time cleanup for ep6 starters.csv errors
- `scripts/update_starters.py` — interactive single-manager starters entry
- `status.py` — session orientation, shows what needs doing
- `WEEKLY.md` — Wednesday checklist with all commands

**Portrait image URL pattern**:
Contestant UUID (in onclick) ≠ Image UUID (in src).
Correct URLs are in `data/season50/portrait_urls.csv`.
18 of 24 portraits downloaded. Missing: Angelina, Cirie, Emily, Jenna, Joe, Charlie.
