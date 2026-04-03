"""
pipeline/publish.py

Generates self-contained HTML dashboards with full scoring analytics:
- Standings with episode delta
- Points over time chart
- Episode breakdown table
- Roster cards with per-event scoring explainer
- Hot/cold indicator per survivor
- Bench opportunity cost (when starters.csv is available)

Output: docs/buffs.html, docs/fjv.html
"""

import json
from pathlib import Path
from survivor_fantasy.db.connect import get_connection, load_config

SEASON_ID  = 50
OUTPUT_DIR = Path("docs")

LEAGUE_CONFIGS = [
    {
        "league_name": "In the Buffs League",
        "short_name":  "In the Buffs",
        "filename":    "buffs.html",
        "other_file":  "fjv.html",
        "other_short": "FJV Heads",
    },
    {
        "league_name": "FJV Survivor Heads League",
        "short_name":  "FJV Heads",
        "filename":    "fjv.html",
        "other_file":  "buffs.html",
        "other_short": "In the Buffs",
    },
]

# Human-readable labels for each event type
EVENT_LABELS = {
    "survived_pre_merge":              ("⚔", "Survived",        "pre"),
    "survived_post_merge":             ("⚔", "Survived",        "post"),
    "team_immunity":                   ("🛡", "Team immunity",   None),
    "team_immunity_first_place_bonus": ("🛡", "Immunity bonus",  None),
    "reward_participant":              ("🍗", "Reward",          None),
    "wins_individual_immunity":        ("🏆", "Ind. immunity",   None),
    "wins_individual_reward":          ("🎁", "Ind. reward",     None),
    "gets_idol_clue":                  ("🗺", "Idol clue",       None),
    "finds_hidden_idol":               ("💎", "Found idol",      None),
    "receives_boomerang_idol":         ("🪃", "Boomerang idol",  None),
    "plays_idol_successfully":         ("💎", "Played idol",     None),
    "voted_out_holding_idol":          ("💀", "Voted out+idol",  None),
    "loses_vote":                      ("🚫", "Lost vote",       None),
    "player_quits":                    ("🚪", "Quit",            None),
    "medical_removal":                 ("🏥", "Medevac",         None),
    "earns_extra_vote":                ("🗳", "Extra vote",      None),
    "makes_fake_idol":                 ("🎭", "Fake idol",       None),
    "participates_in_summit":          ("🚣", "Journey",         None),
    "finds_twist":                     ("🌀", "Found twist",     None),
    "jury_vote":                       ("⚖", "Jury vote",       None),
    "sole_survivor":                   ("👑", "Sole Survivor",   None),
    "voted_out":                       ("🔥", "Voted out",       None),
}


def fetch_data(conn) -> dict:
    episodes = conn.execute("""
        SELECT episode_id, episode_num, title, air_date
        FROM episodes WHERE season_id = ?
        ORDER BY episode_num
    """, [SEASON_ID]).fetchall()

    episode_ids  = [e[0] for e in episodes]
    latest_ep_id = episode_ids[-1] if episode_ids else None
    ep_num_map   = {e[0]: e[1] for e in episodes}  # episode_id -> episode_num

    data = {"episodes": [], "leagues": {}}
    data["episodes"] = [
        {"episode_id": e[0], "episode_num": e[1], "title": e[2], "air_date": str(e[3])}
        for e in episodes
    ]

    for cfg in LEAGUE_CONFIGS:
        league_name = cfg["league_name"]

        # ── Standings ─────────────────────────────────────────────────────────
        standings = conn.execute("""
            SELECT lp.name, ls.cumulative_pts, ls.episode_pts, ls.rank
            FROM league_standings ls
            JOIN league_players lp ON ls.league_player_id = lp.league_player_id
            WHERE ls.season_id = ? AND ls.episode_id = ? AND lp.league_name = ?
            ORDER BY ls.rank
        """, [SEASON_ID, latest_ep_id, league_name]).fetchall()

        # ── History ───────────────────────────────────────────────────────────
        history_rows = conn.execute("""
            SELECT lp.name, ls.episode_id, ls.cumulative_pts, ls.episode_pts
            FROM league_standings ls
            JOIN league_players lp ON ls.league_player_id = lp.league_player_id
            WHERE ls.season_id = ? AND lp.league_name = ?
            ORDER BY lp.name, ls.episode_id
        """, [SEASON_ID, league_name]).fetchall()

        managers_history = {}
        for name, ep_id, cum_pts, ep_pts in history_rows:
            if name not in managers_history:
                managers_history[name] = {"manager": name, "points_by_episode": []}
            managers_history[name]["points_by_episode"].append({
                "episode_id": ep_id,
                "episode_num": ep_num_map.get(ep_id, 0),
                "cumulative_pts": cum_pts,
                "episode_pts": ep_pts
            })

        # ── Elimination detection ─────────────────────────────────────────────
        try:
            eliminated_ids = set(r[0] for r in conn.execute("""
                SELECT value FROM season_state
                WHERE season_id = ? AND key = 'eliminated'
            """, [SEASON_ID]).fetchall())
        except Exception:
            eliminated_ids = set()

        # ── Per-survivor event breakdown ──────────────────────────────────────
        # One row per (manager, survivor, episode, event_type)
        event_rows = conn.execute("""
            SELECT
                lp.name            AS manager,
                pl.full_name       AS survivor,
                pl.player_id,
                es.episode_id,
                es.event_type,
                es.pts,
                es.event_description
            FROM league_rosters lr
            JOIN league_players lp ON lr.league_player_id = lp.league_player_id
            JOIN players pl        ON lr.survivor_player_id = pl.player_id
            JOIN episode_scores es
                ON  es.league_player_id   = lr.league_player_id
                AND es.survivor_player_id = lr.survivor_player_id
                AND es.season_id          = lr.season_id
            WHERE lr.season_id   = ?
              AND lr.episode_id  = ?
              AND lp.league_name = ?
              AND lr.is_active   = true
              AND es.pts        != 0
              AND es.league_player_id IN (
                  SELECT league_player_id FROM league_players
                  WHERE league_name = ?
              )
            ORDER BY lp.name, pl.full_name, es.episode_id, es.pts DESC
        """, [SEASON_ID, latest_ep_id, league_name, league_name]).fetchall()

        # ── Roster totals ─────────────────────────────────────────────────────
        roster_rows = conn.execute("""
            SELECT
                lp.name,
                pl.full_name,
                COALESCE(SUM(es.pts), 0) AS total_pts,
                pl.player_id
            FROM league_rosters lr
            JOIN league_players lp ON lr.league_player_id = lp.league_player_id
            JOIN players pl        ON lr.survivor_player_id = pl.player_id
            LEFT JOIN episode_scores es
                ON  es.league_player_id   = lr.league_player_id
                AND es.survivor_player_id = lr.survivor_player_id
                AND es.season_id          = lr.season_id
            WHERE lr.season_id   = ?
              AND lr.episode_id  = ?
              AND lp.league_name = ?
              AND lr.is_active   = true
            GROUP BY lp.name, pl.full_name, pl.player_id
            ORDER BY lp.name, total_pts DESC
        """, [SEASON_ID, latest_ep_id, league_name]).fetchall()

        # ── Build event breakdown per manager/survivor/episode ────────────────
        # Structure: breakdown[manager][player_id][episode_num] = [events]
        breakdown = {}
        for manager, survivor, player_id, ep_id, event_type, pts, desc in event_rows:
            ep_num = ep_num_map.get(ep_id, 0)
            if manager not in breakdown:
                breakdown[manager] = {}
            if player_id not in breakdown[manager]:
                breakdown[manager][player_id] = {}
            if ep_num not in breakdown[manager][player_id]:
                breakdown[manager][player_id][ep_num] = []

            label_info = EVENT_LABELS.get(event_type, ("•", event_type, None))
            breakdown[manager][player_id][ep_num].append({
                "event_type": event_type,
                "pts":        pts,
                "icon":       label_info[0],
                "label":      label_info[1],
            })

        # ── Compute hot/cold: last ep pts vs average ──────────────────────────
        # hot_cold[manager][player_id] = {last_ep_pts, avg_pts, trend}
        hot_cold = {}
        for manager, survivor, player_id, ep_id, event_type, pts, desc in event_rows:
            ep_num = ep_num_map.get(ep_id, 0)
            if manager not in hot_cold:
                hot_cold[manager] = {}
            if player_id not in hot_cold[manager]:
                hot_cold[manager][player_id] = {}
            ep_key = ep_num
            if ep_key not in hot_cold[manager][player_id]:
                hot_cold[manager][player_id][ep_key] = 0
            hot_cold[manager][player_id][ep_key] += pts

        # Compute trend for each survivor
        trends = {}
        latest_ep_num = ep_num_map.get(latest_ep_id, 0)
        for manager, survivors in hot_cold.items():
            if manager not in trends:
                trends[manager] = {}
            for player_id, ep_pts in survivors.items():
                if not ep_pts:
                    continue
                pts_list = [ep_pts.get(ep, 0) for ep in sorted(ep_pts.keys())]
                last_pts = ep_pts.get(latest_ep_num, 0)
                avg_pts  = sum(pts_list) / len(pts_list) if pts_list else 0
                if last_pts > avg_pts * 1.3:
                    trend = "hot"
                elif last_pts < avg_pts * 0.6 and avg_pts > 3:
                    trend = "cold"
                else:
                    trend = "normal"
                trends[manager][player_id] = {
                    "last_ep_pts": last_pts,
                    "avg_pts":     round(avg_pts, 1),
                    "trend":       trend,
                }

        # ── Assemble roster cards ─────────────────────────────────────────────
        managers_rosters = {}
        for manager, survivor, total_pts, player_id in roster_rows:
            if manager not in managers_rosters:
                managers_rosters[manager] = {"manager": manager, "survivors": []}

            # Per-episode breakdown for this survivor
            sv_breakdown = []
            mgr_breakdown = breakdown.get(manager, {})
            sv_ep_breakdown = mgr_breakdown.get(player_id, {})
            for ep_num in sorted(sv_ep_breakdown.keys()):
                ep_events = sv_ep_breakdown[ep_num]
                ep_total  = sum(e["pts"] for e in ep_events)
                sv_breakdown.append({
                    "episode_num": ep_num,
                    "pts":         ep_total,
                    "events":      ep_events,
                })

            trend_info = trends.get(manager, {}).get(player_id, {
                "last_ep_pts": 0, "avg_pts": 0, "trend": "normal"
            })

            managers_rosters[manager]["survivors"].append({
                "name":         survivor,
                "player_id":    player_id,
                "total_pts":    total_pts,
                "eliminated":   player_id in eliminated_ids,
                "breakdown":    sv_breakdown,
                "last_ep_pts":  trend_info["last_ep_pts"],
                "avg_pts":      trend_info["avg_pts"],
                "trend":        trend_info["trend"],
            })

        data["leagues"][league_name] = {
            "standings": [
                {"rank": r, "manager": n, "cumulative_pts": c, "episode_pts": e}
                for n, c, e, r in standings
            ],
            "history":  list(managers_history.values()),
            "rosters":  list(managers_rosters.values()),
        }

    return data


HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — Survivor 50 Fantasy</title>
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Source+Sans+3:wght@300;400;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {{
  --bg:        #0B2E2E;
  --surface:   #123F3F;
  --surface2:  #0F3535;
  --border:    #2A4A4A;
  --text:      #E8E3D9;
  --text-mute: #B8B1A3;
  --stone:     #5F6F73;
  --gold:      #D4AF37;
  --gold-dim:  rgba(212,175,55,0.12);
  --ember:     #E4572E;
  --lagoon:    #2E86AB;
  --palm:      #3FA34D;
  --purple:    #7A3E9D;
  --gold-glow: rgba(212,175,55,0.15);
  --hot:       #E4572E;
  --cold:      #2E86AB;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  background: var(--bg);
  color: var(--text);
  font-family: 'Source Sans 3', sans-serif;
  min-height: 100vh;
  line-height: 1.5;
}}

/* ── Header ── */
header {{
  background: var(--surface2);
  border-bottom: 1px solid var(--border);
  padding: 20px 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 100;
}}
.header-left h1 {{
  font-family: 'Cinzel', serif;
  font-size: 1.4rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--gold);
}}
.header-left .subtitle {{
  font-family: 'DM Mono', monospace;
  font-size: 0.65rem;
  color: var(--stone);
  letter-spacing: 0.15em;
  text-transform: uppercase;
  margin-top: 3px;
}}
.nav-pills {{ display: flex; gap: 10px; }}
.nav-pill {{
  font-family: 'DM Mono', monospace;
  font-size: 0.65rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 7px 18px;
  border-radius: 100px;
  text-decoration: none;
  border: 1px solid;
  transition: all 0.2s;
}}
.nav-pill.active {{ background: var(--gold); color: var(--bg); border-color: var(--gold); font-weight: 500; }}
.nav-pill.inactive {{ color: var(--stone); border-color: var(--border); }}
.nav-pill.inactive:hover {{ color: var(--text); border-color: var(--stone); }}

/* ── Bars ── */
.episode-bar {{
  background: linear-gradient(90deg, var(--ember) 0%, #C0391F 100%);
  color: #fff;
  text-align: center;
  padding: 7px;
  font-family: 'DM Mono', monospace;
  font-size: 0.68rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}}
.disclaimer-bar {{
  background: rgba(212,175,55,0.08);
  border-bottom: 1px solid rgba(212,175,55,0.25);
  color: var(--text-mute);
  text-align: center;
  padding: 9px 24px;
  font-family: 'DM Mono', monospace;
  font-size: 0.65rem;
  letter-spacing: 0.06em;
  line-height: 1.5;
}}

/* ── Main layout ── */
main {{
  max-width: 1200px;
  margin: 0 auto;
  padding: 44px 24px 80px;
  display: flex;
  flex-direction: column;
  gap: 52px;
}}
.section-header {{
  display: flex;
  align-items: baseline;
  gap: 14px;
  margin-bottom: 20px;
}}
.section-title {{
  font-family: 'Cinzel', serif;
  font-size: 1.2rem;
  font-weight: 600;
  color: var(--gold);
  letter-spacing: 0.05em;
}}
.section-tag {{
  font-family: 'DM Mono', monospace;
  font-size: 0.62rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--stone);
}}

/* ── Leaderboard ── */
.leaderboard {{ display: flex; flex-direction: column; gap: 6px; }}
.lb-row {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px 20px;
  display: grid;
  grid-template-columns: 40px 1fr auto auto auto;
  align-items: center;
  gap: 16px;
  transition: all 0.18s;
  animation: slideIn 0.4s ease both;
}}
.lb-row:hover {{ border-color: var(--gold); background: var(--gold-dim); transform: translateX(3px); }}
.lb-row.rank-1 {{ border-left: 3px solid var(--gold); }}
.lb-row.rank-2 {{ border-left: 3px solid var(--stone); }}
.lb-row.rank-3 {{ border-left: 3px solid #C9956A; }}
.lb-rank {{ font-family: 'DM Mono', monospace; font-size: 0.8rem; color: var(--stone); text-align: center; }}
.lb-rank.gold {{ color: var(--gold); font-weight: 500; }}
.lb-rank.silver {{ color: #AAA; }}
.lb-rank.bronze {{ color: #C9956A; }}
.lb-name {{ font-size: 0.95rem; font-weight: 600; color: var(--text); }}
.lb-ep-pts {{ font-family: 'DM Mono', monospace; font-size: 0.7rem; color: var(--stone); }}
.lb-ep-badge {{
  font-family: 'DM Mono', monospace;
  font-size: 0.65rem;
  padding: 3px 8px;
  border-radius: 4px;
  background: rgba(63,163,77,0.15);
  color: var(--palm);
  border: 1px solid rgba(63,163,77,0.3);
}}
.lb-total {{ font-family: 'DM Mono', monospace; font-size: 1.05rem; font-weight: 500; color: var(--gold); min-width: 72px; text-align: right; }}

/* ── Chart ── */
.chart-wrap {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 28px;
}}
#historyChart {{ width: 100%; height: 320px; }}

/* ── Breakdown table ── */
.breakdown-wrap {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
}}
table.breakdown {{ width: 100%; border-collapse: collapse; font-size: 0.87rem; }}
table.breakdown th {{
  font-family: 'DM Mono', monospace;
  font-size: 0.62rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--stone);
  text-align: left;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  background: var(--surface2);
}}
table.breakdown td {{ padding: 11px 16px; border-bottom: 1px solid var(--border); color: var(--text-mute); }}
table.breakdown tr:last-child td {{ border-bottom: none; }}
table.breakdown tr:hover td {{ background: var(--gold-dim); color: var(--text); }}
.td-manager {{ font-weight: 600; color: var(--text); }}
.td-pts {{ font-family: 'DM Mono', monospace; text-align: right; }}
.pts-pos {{ color: var(--palm); }}
.pts-neg {{ color: var(--ember); }}
.pts-total {{ color: var(--gold); font-weight: 500; }}

/* ── Roster grid ── */
.roster-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}}

/* ── Roster card ── */
.roster-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  animation: fadeUp 0.45s ease both;
  transition: border-color 0.2s;
}}
.roster-card:hover {{ border-color: var(--gold); }}
.rc-header {{
  padding: 14px 16px;
  background: rgba(0,0,0,0.25);
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: center;
}}
.rc-name {{ font-family: 'Cinzel', serif; font-size: 0.9rem; font-weight: 600; color: var(--gold); letter-spacing: 0.04em; }}
.rc-total {{ font-family: 'DM Mono', monospace; font-size: 0.75rem; color: var(--text-mute); }}

/* ── Survivor row ── */
.sv-row {{
  border-bottom: 1px solid var(--border);
  transition: background 0.15s;
}}
.sv-row:last-child {{ border-bottom: none; }}
.sv-row:hover {{ background: var(--gold-dim); }}
.sv-row.eliminated {{ opacity: 0.45; }}
.sv-row.eliminated .sv-name {{ text-decoration: line-through; text-decoration-color: var(--ember); color: var(--stone); }}

/* Survivor summary line */
.sv-summary {{
  padding: 10px 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}}
.sv-name {{ flex: 1; font-size: 0.87rem; color: var(--text); font-weight: 400; }}
.eliminated-badge {{
  font-family: 'DM Mono', monospace;
  font-size: 0.52rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--ember);
  border: 1px solid var(--ember);
  padding: 1px 5px;
  border-radius: 3px;
  opacity: 0.8;
}}
.trend-badge {{
  font-size: 0.7rem;
  width: 18px;
  text-align: center;
  flex-shrink: 0;
}}
.sv-pts-total {{
  font-family: 'DM Mono', monospace;
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--gold);
  flex-shrink: 0;
  min-width: 48px;
  text-align: right;
}}
.sv-pts-total.zero {{ color: var(--stone); }}
.expand-arrow {{
  font-size: 0.6rem;
  color: var(--stone);
  margin-left: 4px;
  transition: transform 0.2s;
  flex-shrink: 0;
}}
.sv-row.open .expand-arrow {{ transform: rotate(180deg); }}

/* Scoring explainer panel */
.sv-explainer {{
  display: none;
  padding: 0 16px 12px 16px;
  border-top: 1px solid var(--border);
  background: rgba(0,0,0,0.15);
}}
.sv-row.open .sv-explainer {{ display: block; }}

.ep-block {{ margin-top: 8px; }}
.ep-label {{
  font-family: 'DM Mono', monospace;
  font-size: 0.6rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--stone);
  margin-bottom: 3px;
}}
.ep-events {{ display: flex; flex-direction: column; gap: 2px; }}
.ep-event {{
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.78rem;
  padding: 2px 0;
}}
.ep-event-icon {{ font-size: 0.8rem; width: 18px; text-align: center; flex-shrink: 0; }}
.ep-event-label {{ flex: 1; color: var(--text-mute); }}
.ep-event-pts {{
  font-family: 'DM Mono', monospace;
  font-size: 0.75rem;
  font-weight: 500;
  min-width: 36px;
  text-align: right;
}}
.ep-event-pts.pos {{ color: var(--palm); }}
.ep-event-pts.neg {{ color: var(--ember); }}
.ep-total {{
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  padding-top: 4px;
  border-top: 1px solid var(--border);
  font-family: 'DM Mono', monospace;
  font-size: 0.72rem;
  color: var(--gold);
}}

/* Hot/cold legend */
.hc-legend {{
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
  font-family: 'DM Mono', monospace;
  font-size: 0.6rem;
  color: var(--stone);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}}

/* ── Animations ── */
@keyframes slideIn {{ from {{ opacity:0; transform:translateX(-10px); }} to {{ opacity:1; transform:translateX(0); }} }}
@keyframes fadeUp  {{ from {{ opacity:0; transform:translateY(8px);  }} to {{ opacity:1; transform:translateY(0);  }} }}

/* ── Footer ── */
footer {{
  text-align: center;
  padding: 20px;
  font-family: 'DM Mono', monospace;
  font-size: 0.62rem;
  color: var(--stone);
  letter-spacing: 0.08em;
  border-top: 1px solid var(--border);
}}
</style>
</head>
<body>

<header>
  <div class="header-left">
    <h1>{title}</h1>
    <div class="subtitle">Survivor 50 · Fantasy Dashboard</div>
  </div>
  <div class="nav-pills">
    <a href="{this_file}" class="nav-pill active">{short_name}</a>
    <a href="{other_file}" class="nav-pill inactive">{other_short}</a>
  </div>
</header>

<div class="episode-bar" id="episodeBar">Loading...</div>
<div class="disclaimer-bar">
  ⚠ Scores reflect all 8 roster picks per manager. Active/bench filtering (5 starters score, 3 bench do not) coming soon.
</div>

<main>
  <section>
    <div class="section-header">
      <span class="section-title">Standings</span>
      <span class="section-tag">After latest episode</span>
    </div>
    <div class="leaderboard" id="leaderboard"></div>
  </section>

  <section>
    <div class="section-header">
      <span class="section-title">Points Over Time</span>
      <span class="section-tag">Cumulative by episode</span>
    </div>
    <div class="chart-wrap">
      <canvas id="historyChart"></canvas>
    </div>
  </section>

  <section>
    <div class="section-header">
      <span class="section-title">Episode Breakdown</span>
      <span class="section-tag">Points per episode per manager</span>
    </div>
    <div class="breakdown-wrap">
      <table class="breakdown">
        <thead id="bkHead"></thead>
        <tbody id="bkBody"></tbody>
      </table>
    </div>
  </section>

  <section>
    <div class="section-header">
      <span class="section-title">Rosters</span>
      <span class="section-tag">Click any survivor to see scoring breakdown · 🔥 hot last ep · 🧊 cold last ep</span>
    </div>
    <div class="roster-grid" id="rosterGrid"></div>
  </section>
</main>

<footer>Survivor 50 Fantasy · Updated after each episode · survivor-fantasy pipeline</footer>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<script>
const ALL_DATA = {json_data};
const LEAGUE   = "{league_name}";

const COLORS = [
  '#D4AF37','#2E86AB','#3FA34D','#E4572E','#7A3E9D',
  '#E8B86D','#5BC0EB','#9BC53D','#FA8C16','#C084FC'
];

function init() {{
  const episodes   = ALL_DATA.episodes || [];
  const leagueData = ALL_DATA.leagues?.[LEAGUE] || {{}};
  const standings  = leagueData.standings || [];
  const history    = leagueData.history   || [];
  const rosters    = leagueData.rosters   || [];
  const latestEp   = episodes[episodes.length - 1];

  document.getElementById('episodeBar').textContent = latestEp
    ? `Through Episode ${{latestEp.episode_num}}: "${{latestEp.title}}"`
    : 'Survivor 50';

  renderLeaderboard(standings);
  renderChart(history, episodes);
  renderBreakdown(history, episodes, standings);
  renderRosters(rosters, standings, episodes);
}}

// ── Leaderboard ──────────────────────────────────────────────────────────────
function renderLeaderboard(standings) {{
  const rankClass = r => r===1?'gold':r===2?'silver':r===3?'bronze':'';
  document.getElementById('leaderboard').innerHTML = standings.map((s,i) => `
    <div class="lb-row rank-${{s.rank}}" style="animation-delay:${{i*0.05}}s">
      <div class="lb-rank ${{rankClass(s.rank)}}">${{s.rank}}</div>
      <div class="lb-name">${{s.manager}}</div>
      <div class="lb-ep-pts">+${{s.episode_pts}} this ep</div>
      <div class="lb-ep-badge">+${{s.episode_pts}}</div>
      <div class="lb-total">${{s.cumulative_pts}} pts</div>
    </div>
  `).join('');
}}

// ── Chart ────────────────────────────────────────────────────────────────────
function renderChart(history, episodes) {{
  const labels   = episodes.map(e => `Ep ${{e.episode_num}}`);
  const datasets = history.map((m,i) => ({{
    label: m.manager,
    data:  m.points_by_episode.map(p => p.cumulative_pts),
    borderColor: COLORS[i % COLORS.length],
    backgroundColor: 'transparent',
    borderWidth: 2.5,
    pointRadius: 5,
    pointHoverRadius: 7,
    tension: 0.35,
  }}));
  new Chart(document.getElementById('historyChart'), {{
    type: 'line',
    data: {{ labels, datasets }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{ labels: {{ font: {{ family:'DM Mono',size:11 }}, color:'#B8B1A3', boxWidth:14 }} }},
        tooltip: {{
          backgroundColor: '#0B2E2E',
          borderColor: '#2A4A4A',
          borderWidth: 1,
          titleFont: {{ family:'DM Mono',size:11 }},
          bodyFont:  {{ family:'DM Mono',size:11 }},
          padding: 10,
          callbacks: {{
            afterBody: ctx => {{
              const ep   = ctx[0].dataIndex;
              const mgr  = ctx[0].dataset.label;
              const mgrData = history.find(h => h.manager === mgr);
              const epData  = mgrData?.points_by_episode[ep];
              return epData ? [`+${{epData.episode_pts}} this episode`] : [];
            }}
          }}
        }}
      }},
      scales: {{
        x: {{ grid: {{ color:'#1A4A4A' }}, ticks: {{ font: {{ family:'DM Mono',size:11 }}, color:'#5F6F73' }} }},
        y: {{ grid: {{ color:'#1A4A4A' }}, ticks: {{ font: {{ family:'DM Mono',size:11 }}, color:'#5F6F73' }} }}
      }}
    }}
  }});
}}

// ── Episode breakdown table ──────────────────────────────────────────────────
function renderBreakdown(history, episodes, standings) {{
  const rankMap = {{}};
  standings.forEach(s => rankMap[s.manager] = s.rank);
  const sorted = [...history].sort((a,b) => (rankMap[a.manager]||99) - (rankMap[b.manager]||99));

  document.getElementById('bkHead').innerHTML = `<tr>
    <th>Manager</th>
    ${{episodes.map(e => `<th style="text-align:right">Ep ${{e.episode_num}}</th>`).join('')}}
    <th style="text-align:right">Total</th>
  </tr>`;

  document.getElementById('bkBody').innerHTML = sorted.map(m => {{
    const total = m.points_by_episode.reduce((s,p) => s + p.episode_pts, 0);
    const cells = episodes.map((e,i) => {{
      const pts = m.points_by_episode[i]?.episode_pts;
      const val = pts !== undefined ? pts : '—';
      const cls = typeof pts === 'number' ? (pts >= 0 ? 'pts-pos' : 'pts-neg') : '';
      return `<td class="td-pts ${{cls}}" style="text-align:right">${{val}}</td>`;
    }}).join('');
    return `<tr>
      <td class="td-manager">${{m.manager}}</td>
      ${{cells}}
      <td class="td-pts pts-total" style="text-align:right;font-weight:600">${{total}}</td>
    </tr>`;
  }}).join('');
}}

// ── Roster cards with scoring explainer ─────────────────────────────────────
function renderRosters(rosters, standings, episodes) {{
  const rankMap = {{}};
  standings.forEach(s => rankMap[s.manager] = s.rank);
  const sorted = [...rosters].sort((a,b) => (rankMap[a.manager]||99) - (rankMap[b.manager]||99));

  document.getElementById('rosterGrid').innerHTML = sorted.map((m, cardIdx) => {{
    const total = standings.find(s => s.manager === m.manager)?.cumulative_pts || 0;
    const latestEpNum = episodes[episodes.length-1]?.episode_num || 0;

    const survivors = m.survivors.map((s, svIdx) => {{
      const trendIcon = s.trend === 'hot' ? '🔥' : s.trend === 'cold' ? '🧊' : '';
      const trendTitle = s.trend === 'hot'
        ? `Hot: ${{s.last_ep_pts}} pts last ep vs ${{s.avg_pts}} avg`
        : s.trend === 'cold'
        ? `Cold: ${{s.last_ep_pts}} pts last ep vs ${{s.avg_pts}} avg`
        : `${{s.last_ep_pts}} pts last ep · ${{s.avg_pts}} avg`;

      const rowId = `sv-${{cardIdx}}-${{svIdx}}`;

      // Build per-episode breakdown HTML
      let explainerHtml = '';
      if (s.breakdown && s.breakdown.length > 0) {{
        explainerHtml = s.breakdown.map(ep => {{
          const eventsHtml = ep.events.map(ev => `
            <div class="ep-event">
              <span class="ep-event-icon">${{ev.icon}}</span>
              <span class="ep-event-label">${{ev.label}}</span>
              <span class="ep-event-pts ${{ev.pts >= 0 ? 'pos' : 'neg'}}">${{ev.pts >= 0 ? '+' : ''}}${{ev.pts}}</span>
            </div>
          `).join('');
          return `
            <div class="ep-block">
              <div class="ep-label">Episode ${{ep.episode_num}}</div>
              <div class="ep-events">${{eventsHtml}}</div>
              <div class="ep-total">
                <span>Ep ${{ep.episode_num}} total</span>
                <span>${{ep.pts >= 0 ? '+' : ''}}${{ep.pts}} pts</span>
              </div>
            </div>
          `;
        }}).join('');
      }} else {{
        explainerHtml = '<div style="color:var(--stone);font-size:0.75rem;padding:8px 0;">No scoring events</div>';
      }}

      const ptsDisplay = s.total_pts > 0 ? s.total_pts + ' pts' : '—';

      return `
        <div class="sv-row${{s.eliminated ? ' eliminated' : ''}}" id="${{rowId}}" onclick="toggleExplainer('${{rowId}}')">
          <div class="sv-summary">
            <span class="sv-name">
              ${{s.name}}
              ${{s.eliminated ? '<span class="eliminated-badge">out</span>' : ''}}
            </span>
            ${{trendIcon ? `<span class="trend-badge" title="${{trendTitle}}">${{trendIcon}}</span>` : ''}}
            <span class="sv-pts-total ${{s.total_pts === 0 ? 'zero' : ''}}">${{ptsDisplay}}</span>
            <span class="expand-arrow">▾</span>
          </div>
          <div class="sv-explainer">
            ${{explainerHtml}}
          </div>
        </div>
      `;
    }}).join('');

    return `
      <div class="roster-card" style="animation-delay:${{cardIdx*0.06}}s">
        <div class="rc-header">
          <span class="rc-name">${{m.manager}}</span>
          <span class="rc-total">${{total}} pts total</span>
        </div>
        ${{survivors}}
      </div>
    `;
  }}).join('');
}}

// ── Toggle explainer panel ───────────────────────────────────────────────────
function toggleExplainer(rowId) {{
  const row = document.getElementById(rowId);
  if (row) row.classList.toggle('open');
}}

init();
</script>
</body>
</html>'''


def build_page(cfg: dict, data: dict) -> str:
    league_name = cfg["league_name"]
    json_data   = json.dumps(data, ensure_ascii=False)
    return HTML_TEMPLATE.format(
        title=cfg["league_name"],
        short_name=cfg["short_name"],
        this_file=cfg["filename"],
        other_file=cfg["other_file"],
        other_short=cfg["other_short"],
        league_name=league_name,
        json_data=json_data,
    )


def main():
    config = load_config()
    conn   = get_connection()
    print("Connected to DB")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data = fetch_data(conn)
    conn.close()

    for cfg in LEAGUE_CONFIGS:
        html = build_page(cfg, data)
        path = OUTPUT_DIR / cfg["filename"]
        path.write_text(html, encoding='utf-8')
        print(f"  Wrote {path}  ({len(html):,} bytes)")

    print("Done.")


if __name__ == "__main__":
    main()
