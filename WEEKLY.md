# Weekly Workflow — Every Wednesday After the Episode

This is the checklist you run through every week. Start here.

---

## Step 0 — Orient yourself (30 seconds)

```bash
# Mac
sfenv                        # navigate to project + activate venv
python status.py             # shows exactly what's missing

# Windows
cd C:\Users\james\Projects\DataScience\Repositories\survivor-fantasy
python status.py
```

`status.py` will tell you what episode we're on, whether events.csv is current,
whether starters.csv is current, and whether the dashboard needs pushing.

---

## Step 1 — Collect bench/starter data BEFORE the episode airs (~5:00pm MT)

Rosters lock around 5pm MT. Do this before then.

On tribal-council.com, go to each manager's league page. Open DevTools Console (F12) and run:

```javascript
const avatars = [...document.querySelectorAll('.contestant-avatar-img-inline')];
const ids = avatars.map(a => {
  const s = a.getAttribute('onclick') || a.getAttribute('src') || '';
  const m = s.match(/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})/);
  return m ? m[1].substring(0,8) : null;
}).filter(Boolean);
copy(JSON.stringify({starters: ids.slice(0,5), bench: ids.slice(5)}));
```

Then run `python scripts/update_starters.py` and paste the output when prompted.
This appends the correct rows to `data/season50/starters.csv`.

---

## Step 2 — Enter episode data AFTER the episode airs

Open `data/season50/events.csv` and add one row per player for the new episode.

**Field reference (in order):**

| Field | Notes |
|---|---|
| season | Always 50 |
| episode | Episode number |
| player_name | Must match name map exactly (see below) |
| still_in_game | 1=alive, 0=eliminated this episode |
| tribe_name | Current tribe name |
| merge_status | pre / post |
| attended_tc | 1 if tribe went to TC |
| voted_out | 1 if this player was voted out |
| votes_received | Number of votes received at TC |
| had_individual_immunity | 1 if wore immunity necklace |
| tribe_won_immunity | 1 if tribe won immunity challenge |
| tribe_immunity_place | 1=first, 2=second, 3=lost (0 if individual) |
| reward_participant | 1 if participated in reward |
| won_individual_reward | 1 if won individual reward |
| found_idol_clue | 1 if found clue or boomerang idol |
| found_hidden_idol | 1 if found hidden immunity idol |
| played_idol | 1 if played idol at TC |
| played_idol_for | Name of player idol was played for |
| voted_out_holding_idol | 1 if left game with unplayed idol |
| lost_vote | 1 if lost their vote |
| quit | 1 if quit voluntarily |
| medevac | 1 if medically evacuated |
| received_jury_vote | 1 if received a jury vote (finale only) |
| sole_survivor | 1 if won the game |
| confessional_count | Number of confessionals this episode |

**Player name map (events.csv → DB):**

| Use in events.csv | DB stores as |
|---|---|
| Benjamin "Coach" Wade | Benjamin Wade |
| Jenna Lewis-Dougherty | Jenna Lewis |
| Ozzy Lusth | Oscar Lusth |
| Stephenie LaGrossa Kendrick | Stephenie LaGrossa |
| Joseph "Joe" Hunter | Joe Hunter |
| Tiffany Ervin | Tiffany Nicole Ervin |

**Also update `ingest_s50.py`** — add the new episode to the EPISODES list:

```python
(6, 'The Blood Moon', '2026-04-01', True, 17, 16),
#   ^ep  ^title         ^air date    ^merge ^start ^end players
```

Set `is_merge=True` for the merge episode.

---

## Step 3 — Run the pipeline

```bash
# Mac
python src/survivor_fantasy/pipeline/ingest_s50.py
python src/survivor_fantasy/pipeline/scorer.py
python src/survivor_fantasy/pipeline/publish.py

# Windows
python src\survivor_fantasy\pipeline\ingest_s50.py
python src\survivor_fantasy\pipeline\scorer.py
python src\survivor_fantasy\pipeline\publish.py
```

Check the output for WARNINGs — common ones:
- `no episode_id for episode N` → forgot to add episode to EPISODES list
- `survivor×episode not on any roster` → eliminated player, expected
- `skipped N rows` → name mapping issue, check player names

---

## Step 4 — Verify locally

```bash
# Mac
open docs/buffs.html
open docs/fjv.html

# Windows
start docs\buffs.html
start docs\fjv.html
```

Check: standings look right, eliminated players show OUT, episode count is correct.

---

## Step 5 — Push to GitHub Pages

```bash
git add docs/buffs.html docs/fjv.html src/survivor_fantasy/pipeline/ingest_s50.py
git commit -m "ep6 scores: [who was voted out]"
git push
```

Dashboard is live at GitHub Pages within ~1 minute.

---

## Step 6 — Sync data files between machines (if needed)

`data/` is gitignored — files don't sync automatically. If you worked on one machine
and need the data on the other, manually copy:

- `data/season50/events.csv`
- `data/season50/rosters.csv`
- `data/season50/starters.csv`

Options: AirDrop, email to yourself, USB, or shared cloud folder.

**Quick check**: run `python status.py` on the second machine after copying — it will
confirm all files are present and current.

---

## Known scoring gaps (not yet implemented)

These events happen in the show but aren't fully scored yet:

- **Journey/summit participation** (+1 per player) — not in events.csv
- **Boomerang idol gifted** (+1) — using `found_idol_clue` as proxy (wrong)
- **Boomerang idol received** (+3) — missing entirely
- **Extra vote earned** (+3) — missing
- **Active/bench filtering** — all 8 picks score, should be 5 starters only

These will be fixed progressively. The disclaimer banner on the dashboard notes this.

---

## Tribal-council.com scoring rules (reference)

| Event | Points |
|---|---|
| Survived pre-merge | +3 |
| Survived post-merge | +6 |
| Team immunity win | +2 (+1 bonus for 1st of 3) |
| Wins individual immunity | +6 |
| Reward participant | +2 (+1 bonus for 1st of 3) |
| Wins individual reward | +4 |
| Finds hidden idol | +3 |
| Gets idol clue / boomerang | +1 |
| Plays idol successfully | +6 |
| Voted out holding idol | -6 |
| Loses vote | -3 |
| Player quits | -8 |
| Medical removal | +8 |
| Jury vote received | +10 |
| Sole Survivor | +20 |
| Gifts boomerang idol | +1 |
| Receives boomerang idol | +3 |
| Earns extra vote | +3 |
| Plays extra vote | +6 |
| Shot in the Dark (immunity) | +6 |
| Participates in summit | +1 |
