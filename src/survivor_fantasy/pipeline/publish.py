"""
pipeline/publish.py - Survivor 50 Fantasy Dashboard
Flow: Standings → This Week's Chart → Rosters (bench decision) → Modal (deep dive)
"""

import json
import csv
from pathlib import Path
from survivor_fantasy.db.connect import get_connection, load_config

SEASON_ID    = 50
OUTPUT_DIR   = Path("docs")
STARTERS_CSV = Path("data/season50/starters.csv")

LEAGUE_CONFIGS = [
    {"league_name": "In the Buffs League",      "short_name": "In the Buffs",
     "filename": "buffs.html", "other_file": "fjv.html",  "other_short": "FJV Heads"},
    {"league_name": "FJV Survivor Heads League", "short_name": "FJV Heads",
     "filename": "fjv.html",  "other_file": "buffs.html", "other_short": "In the Buffs"},
]

EVENT_LABELS = {
    "survived_pre_merge":              ("⚔", "Survived (pre-merge)"),
    "survived_post_merge":             ("⚔", "Survived (post-merge)"),
    "team_immunity":                   ("🛡", "Team immunity"),
    "team_immunity_first_place_bonus": ("🛡", "Immunity 1st place bonus"),
    "reward_participant":              ("🍗", "Reward"),
    "reward_first_place_bonus":        ("🍗", "Reward 1st place bonus"),
    "wins_individual_immunity":        ("🏆", "Individual immunity"),
    "wins_individual_reward":          ("🎁", "Individual reward"),
    "gets_idol_clue":                  ("🗺", "Found boomerang idol"),
    "finds_hidden_idol":               ("💎", "Found hidden idol"),
    "receives_boomerang_idol":         ("🪃", "Received boomerang idol"),
    "plays_idol_successfully":         ("💎", "Played idol successfully"),
    "voted_out_holding_idol":          ("💀", "Voted out with idol"),
    "loses_vote":                      ("🚫", "Lost vote"),
    "player_quits":                    ("🚪", "Quit"),
    "medical_removal":                 ("🏥", "Medical evacuation"),
    "earns_extra_vote":                ("🗳", "Earned extra vote"),
    "makes_fake_idol":                 ("🎭", "Made fake idol"),
    "participates_in_summit":          ("🚣", "Journey/summit"),
    "finds_twist":                     ("🌀", "Found twist"),
    "jury_vote":                       ("⚖",  "Jury vote"),
    "sole_survivor":                   ("👑", "Sole Survivor"),
    "voted_out":                       ("🔥", "Voted out"),
}


def load_starters():
    starters = {}
    if not STARTERS_CSV.exists():
        return starters
    for row in csv.DictReader(STARTERS_CSV.open(encoding='utf-8')):
        key = (row['manager'], int(row['episode']), row['player_uuid'][:8])
        starters[key] = row['is_starter'] == '1'
    return starters


def fetch_data(conn) -> dict:
    episodes = conn.execute("""
        SELECT episode_id, episode_num, title, air_date
        FROM episodes WHERE season_id = ? ORDER BY episode_num
    """, [SEASON_ID]).fetchall()

    episode_ids   = [e[0] for e in episodes]
    latest_ep_id  = episode_ids[-1] if episode_ids else None
    prev_ep_id    = episode_ids[-2] if len(episode_ids) >= 2 else None
    ep_num_map    = {e[0]: e[1] for e in episodes}
    latest_ep_num = ep_num_map.get(latest_ep_id, 0)
    starters      = load_starters()
    has_starters  = bool(starters)

    data = {
        "episodes": [
            {"episode_id": e[0], "episode_num": e[1], "title": e[2], "air_date": str(e[3])}
            for e in episodes
        ],
        "has_starters": has_starters,
        "leagues": {}
    }

    for cfg in LEAGUE_CONFIGS:
        league_name = cfg["league_name"]

        # Current standings
        standings = conn.execute("""
            SELECT lp.name, ls.cumulative_pts, ls.episode_pts, ls.rank
            FROM league_standings ls
            JOIN league_players lp ON ls.league_player_id = lp.league_player_id
            WHERE ls.season_id = ? AND ls.episode_id = ? AND lp.league_name = ?
            ORDER BY ls.rank
        """, [SEASON_ID, latest_ep_id, league_name]).fetchall()

        # Previous episode standings for rank change
        prev_ranks = {}
        if prev_ep_id:
            prev_rows = conn.execute("""
                SELECT lp.name, ls.rank
                FROM league_standings ls
                JOIN league_players lp ON ls.league_player_id = lp.league_player_id
                WHERE ls.season_id = ? AND ls.episode_id = ? AND lp.league_name = ?
            """, [SEASON_ID, prev_ep_id, league_name]).fetchall()
            prev_ranks = {name: rank for name, rank in prev_rows}

        # History
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
                "episode_id": ep_id, "episode_num": ep_num_map.get(ep_id, 0),
                "cumulative_pts": cum_pts, "episode_pts": ep_pts
            })

        # Elimination detection
        try:
            eliminated_ids = set(r[0] for r in conn.execute("""
                SELECT value FROM season_state WHERE season_id = ? AND key = 'eliminated'
            """, [SEASON_ID]).fetchall())
        except Exception:
            eliminated_ids = set()

        # Per-survivor scoring events
        event_rows = conn.execute("""
            SELECT lp.name, pl.full_name, pl.player_id, es.episode_id, es.event_type, es.pts
            FROM league_rosters lr
            JOIN league_players lp ON lr.league_player_id = lp.league_player_id
            JOIN players pl        ON lr.survivor_player_id = pl.player_id
            JOIN episode_scores es
                ON  es.league_player_id   = lr.league_player_id
                AND es.survivor_player_id = lr.survivor_player_id
                AND es.season_id          = lr.season_id
            WHERE lr.season_id = ? AND lr.episode_id = ? AND lp.league_name = ?
              AND lr.is_active = true AND es.pts != 0
              AND es.league_player_id IN (
                  SELECT league_player_id FROM league_players WHERE league_name = ?
              )
            ORDER BY lp.name, pl.full_name, es.episode_id, es.pts DESC
        """, [SEASON_ID, latest_ep_id, league_name, league_name]).fetchall()

        # Roster totals
        roster_rows = conn.execute("""
            SELECT lp.name, pl.full_name, COALESCE(SUM(es.pts), 0) AS total_pts, pl.player_id
            FROM league_rosters lr
            JOIN league_players lp ON lr.league_player_id = lp.league_player_id
            JOIN players pl        ON lr.survivor_player_id = pl.player_id
            LEFT JOIN episode_scores es
                ON  es.league_player_id   = lr.league_player_id
                AND es.survivor_player_id = lr.survivor_player_id
                AND es.season_id          = lr.season_id
            WHERE lr.season_id = ? AND lr.episode_id = ? AND lp.league_name = ?
              AND lr.is_active = true
            GROUP BY lp.name, pl.full_name, pl.player_id
            ORDER BY lp.name, total_pts DESC
        """, [SEASON_ID, latest_ep_id, league_name]).fetchall()

        # Build breakdown and episode pts map
        breakdown  = {}
        ep_pts_map = {}
        for manager, survivor, player_id, ep_id, event_type, pts in event_rows:
            ep_num = ep_num_map.get(ep_id, 0)
            breakdown.setdefault(manager, {}).setdefault(player_id, {}).setdefault(ep_num, [])
            lbl = EVENT_LABELS.get(event_type, ("•", event_type))
            breakdown[manager][player_id][ep_num].append(
                {"event_type": event_type, "pts": pts, "icon": lbl[0], "label": lbl[1]}
            )
            ep_pts_map.setdefault(manager, {}).setdefault(player_id, {})
            ep_pts_map[manager][player_id][ep_num] = \
                ep_pts_map[manager][player_id].get(ep_num, 0) + pts

        # Compute trends (hot/cold) and find league best-this-week survivor
        trends = {}
        best_this_week = {"manager": None, "survivor": None, "pts": -1}

        for manager, survivors in ep_pts_map.items():
            trends[manager] = {}
            for player_id, ep_pts in survivors.items():
                pts_list = [ep_pts.get(ep, 0) for ep in sorted(ep_pts)]
                last_pts = ep_pts.get(latest_ep_num, 0)
                avg_pts  = sum(pts_list) / len(pts_list) if pts_list else 0
                trend = ("hot"  if last_pts > avg_pts * 1.3 else
                         "cold" if last_pts < avg_pts * 0.6 and avg_pts > 3 else
                         "normal")
                trends[manager][player_id] = {
                    "last_ep_pts": last_pts, "avg_pts": round(avg_pts, 1), "trend": trend
                }
                # Track league best this week (non-eliminated only)
                if last_pts > best_this_week["pts"] and player_id not in eliminated_ids:
                    best_this_week = {"manager": manager, "player_id": player_id, "pts": last_pts}

        # Assemble rosters — sort survivors by last_ep_pts desc (bench decision order)
        managers_rosters = {}
        for manager, survivor, total_pts, player_id in roster_rows:
            if manager not in managers_rosters:
                managers_rosters[manager] = {
                    "manager": manager, "survivors": [], "bench_cost": 0
                }
            sv_ep_bd     = breakdown.get(manager, {}).get(player_id, {})
            sv_breakdown = []
            sparkline    = []
            for ep_num in sorted(sv_ep_bd.keys()):
                ep_events = sv_ep_bd[ep_num]
                ep_total  = sum(e["pts"] for e in ep_events)
                sv_breakdown.append({"episode_num": ep_num, "pts": ep_total, "events": ep_events})
                sparkline.append({"ep": ep_num, "pts": ep_total})

            trend_info   = trends.get(manager, {}).get(player_id,
                           {"last_ep_pts": 0, "avg_pts": 0, "trend": "normal"})
            uuid_prefix  = player_id.split('_')[0][:8] if '_' in player_id else player_id[:8]
            starter_by_ep = {}
            if has_starters:
                for ep_n in range(1, latest_ep_num + 1):
                    key = (manager, ep_n, uuid_prefix)
                    if key in starters:
                        starter_by_ep[ep_n] = starters[key]

            is_best = (
                player_id == best_this_week.get("player_id") and
                manager   == best_this_week.get("manager")
            )

            managers_rosters[manager]["survivors"].append({
                "name":          survivor,
                "player_id":     player_id,
                "uuid":          uuid_prefix,
                "total_pts":     total_pts,
                "eliminated":    player_id in eliminated_ids,
                "breakdown":     sv_breakdown,
                "sparkline":     sparkline,
                "last_ep_pts":   trend_info["last_ep_pts"],
                "avg_pts":       trend_info["avg_pts"],
                "trend":         trend_info["trend"],
                "starter_by_ep": starter_by_ep,
                "best_this_week": is_best,
            })

        # Sort each manager's survivors: alive hot→normal→cold, then eliminated
        for mgr_data in managers_rosters.values():
            def sort_key(s):
                if s["eliminated"]: return (2, -s["total_pts"])
                trend_order = {"hot": 0, "normal": 1, "cold": 2}
                return (0, trend_order.get(s["trend"], 1), -s["last_ep_pts"])
            mgr_data["survivors"].sort(key=sort_key)

        # Bench cost
        if has_starters:
            for mgr_data in managers_rosters.values():
                bench_cost = 0
                for sv in mgr_data["survivors"]:
                    for ep_info in sv["breakdown"]:
                        ep_n = ep_info["episode_num"]
                        if sv["starter_by_ep"].get(ep_n) is False:
                            bench_cost += ep_info["pts"]
                mgr_data["bench_cost"] = bench_cost

        # Build standings with rank change
        standings_out = []
        for name, cum_pts, ep_pts, rank in standings:
            prev_rank   = prev_ranks.get(name)
            rank_change = (prev_rank - rank) if prev_rank else 0
            standings_out.append({
                "rank": rank, "manager": name,
                "cumulative_pts": cum_pts, "episode_pts": ep_pts,
                "rank_change": rank_change,
            })

        data["leagues"][league_name] = {
            "standings":      standings_out,
            "history":        list(managers_history.values()),
            "rosters":        list(managers_rosters.values()),
            "best_this_week": best_this_week,
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
:root{{
  --bg:#0B2E2E; --surface:#123F3F; --surface2:#0F3535; --border:#2A4A4A;
  --text:#E8E3D9; --mute:#B8B1A3; --stone:#5F6F73;
  --gold:#D4AF37; --gold-dim:rgba(212,175,55,0.12); --gold-border:rgba(212,175,55,0.25);
  --ember:#E4572E; --palm:#3FA34D; --lagoon:#2E86AB;
}}
*{{margin:0;padding:0;box-sizing:border-box;}}
html{{scroll-behavior:smooth;}}
body{{background:var(--bg);color:var(--text);font-family:'Source Sans 3',sans-serif;min-height:100vh;line-height:1.5;}}

/* ── Header ── */
header{{
  background:var(--surface2);border-bottom:1px solid var(--border);
  padding:16px 32px;display:flex;align-items:center;justify-content:space-between;
  position:sticky;top:0;z-index:200;
}}
.h-title{{font-family:'Cinzel',serif;font-size:1.3rem;font-weight:600;color:var(--gold);letter-spacing:0.04em;}}
.h-sub{{font-family:'DM Mono',monospace;font-size:0.58rem;color:var(--stone);letter-spacing:0.14em;text-transform:uppercase;margin-top:2px;}}
.nav-pills{{display:flex;gap:8px;}}
.nav-pill{{font-family:'DM Mono',monospace;font-size:0.6rem;letter-spacing:0.1em;text-transform:uppercase;padding:6px 14px;border-radius:100px;text-decoration:none;border:1px solid;transition:all 0.2s;}}
.nav-pill.active{{background:var(--gold);color:var(--bg);border-color:var(--gold);font-weight:500;}}
.nav-pill.inactive{{color:var(--stone);border-color:var(--border);}}
.nav-pill.inactive:hover{{color:var(--text);border-color:var(--stone);}}

/* ── Episode banner ── */
.ep-bar{{
  background:linear-gradient(90deg,#8B0000,var(--ember));
  color:#fff;text-align:center;padding:8px 16px;
  font-family:'DM Mono',monospace;font-size:0.68rem;letter-spacing:0.14em;text-transform:uppercase;
}}
.disc-bar{{
  background:rgba(212,175,55,0.07);border-bottom:1px solid var(--gold-border);
  color:var(--stone);text-align:center;padding:6px 24px;
  font-family:'DM Mono',monospace;font-size:0.6rem;letter-spacing:0.06em;
}}

/* ── Layout ── */
main{{max-width:1200px;margin:0 auto;padding:36px 20px 80px;display:flex;flex-direction:column;gap:48px;}}
.sec-title{{font-family:'Cinzel',serif;font-size:1.1rem;font-weight:600;color:var(--gold);letter-spacing:0.05em;margin-bottom:4px;}}
.sec-sub{{font-family:'DM Mono',monospace;font-size:0.58rem;text-transform:uppercase;letter-spacing:0.1em;color:var(--stone);margin-bottom:16px;}}

/* ── Standings ── */
.lb{{display:flex;flex-direction:column;gap:4px;}}
.lb-row{{
  background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:11px 16px;display:grid;
  grid-template-columns:32px 1fr auto auto auto;
  align-items:center;gap:10px;
  cursor:pointer;transition:all 0.15s;animation:slideIn 0.35s ease both;
}}
.lb-row:hover{{border-color:var(--gold-border);background:var(--gold-dim);transform:translateX(2px);}}
.lb-row.r1{{border-left:3px solid var(--gold);}}
.lb-row.r2{{border-left:3px solid #888;}}
.lb-row.r3{{border-left:3px solid #C9956A;}}
.lb-rank{{font-family:'DM Mono',monospace;font-size:0.75rem;text-align:center;}}
.lb-rank.g{{color:var(--gold);}} .lb-rank.s{{color:#AAA;}} .lb-rank.b{{color:#C9956A;}} .lb-rank.n{{color:var(--stone);}}
.lb-name{{font-size:0.9rem;font-weight:600;}}
.lb-change{{font-family:'DM Mono',monospace;font-size:0.65rem;min-width:24px;text-align:center;}}
.lb-change.up{{color:var(--palm);}} .lb-change.dn{{color:var(--ember);}} .lb-change.same{{color:var(--stone);}}
.lb-ep{{
  font-family:'DM Mono',monospace;font-size:0.65rem;
  background:rgba(63,163,77,0.1);color:var(--palm);
  border:1px solid rgba(63,163,77,0.22);border-radius:4px;
  padding:2px 8px;text-align:center;white-space:nowrap;
}}
.lb-total{{font-family:'DM Mono',monospace;font-size:0.95rem;font-weight:500;color:var(--gold);text-align:right;min-width:64px;}}

/* ── Chart ── */
.chart-card{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:20px 24px;}}
.chart-controls{{display:flex;align-items:center;gap:8px;margin-bottom:16px;flex-wrap:wrap;}}
.chart-tab{{
  font-family:'DM Mono',monospace;font-size:0.6rem;text-transform:uppercase;
  letter-spacing:0.08em;padding:4px 12px;border-radius:4px;
  border:1px solid var(--border);color:var(--stone);cursor:pointer;
  background:transparent;transition:all 0.15s;
}}
.chart-tab.on{{background:var(--gold-dim);border-color:var(--gold-border);color:var(--gold);}}
.chart-tab:hover:not(.on){{color:var(--text);border-color:var(--stone);}}
.chart-note{{font-family:'DM Mono',monospace;font-size:0.58rem;color:var(--stone);margin-left:auto;}}
.chart-box{{position:relative;height:280px;width:100%;}}

/* ── Rosters ── */
.roster-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px;align-items:start;}}

/* Card */
.rc{{
  background:var(--surface);border:1px solid var(--border);
  border-radius:10px;overflow:hidden;
  animation:fadeUp 0.35s ease both;transition:border-color 0.15s;
}}
.rc:hover{{border-color:var(--gold-border);}}
.rc-head{{
  padding:11px 14px;background:rgba(0,0,0,0.2);
  border-bottom:1px solid var(--border);
  display:flex;justify-content:space-between;align-items:center;
  cursor:pointer;
}}
.rc-head:hover .rc-mgr{{color:#fff;}}
.rc-mgr{{font-family:'Cinzel',serif;font-size:0.85rem;font-weight:600;color:var(--gold);transition:color 0.15s;}}
.rc-total{{font-family:'DM Mono',monospace;font-size:0.7rem;color:var(--mute);}}

/* Survivor rows */
.sv{{border-bottom:1px solid var(--border);transition:background 0.1s;}}
.sv:last-of-type{{border-bottom:none;}}
.sv:hover{{background:rgba(212,175,55,0.04);}}
.sv.elim{{opacity:0.38;}}
.sv.elim .sv-name{{text-decoration:line-through;text-decoration-color:var(--ember);color:var(--stone);}}

.sv-row{{
  padding:8px 14px;display:grid;
  grid-template-columns:1fr auto auto auto auto;
  align-items:center;gap:7px;cursor:pointer;user-select:none;
}}
.sv-name{{font-size:0.83rem;color:var(--text);}}
.elim-pill{{font-family:'DM Mono',monospace;font-size:0.48rem;text-transform:uppercase;color:var(--ember);border:1px solid var(--ember);padding:1px 4px;border-radius:3px;}}
.best-pill{{font-family:'DM Mono',monospace;font-size:0.48rem;text-transform:uppercase;color:var(--gold);border:1px solid var(--gold-border);padding:1px 4px;border-radius:3px;background:var(--gold-dim);}}
.trend-ico{{font-size:0.7rem;width:14px;text-align:center;flex-shrink:0;}}
.sparks{{display:flex;align-items:flex-end;gap:2px;height:16px;flex-shrink:0;}}
.spark{{width:4px;border-radius:1px 1px 0 0;min-height:2px;}}
.sv-ep-pts{{
  font-family:'DM Mono',monospace;font-size:0.7rem;
  color:var(--mute);min-width:36px;text-align:right;flex-shrink:0;
}}
.sv-total{{font-family:'DM Mono',monospace;font-size:0.78rem;font-weight:500;color:var(--gold);min-width:42px;text-align:right;flex-shrink:0;}}
.sv-total.zero{{color:var(--stone);}}
.sv-arrow{{font-size:0.52rem;color:var(--stone);transition:transform 0.15s;flex-shrink:0;}}
.sv.open .sv-arrow{{transform:rotate(180deg);}}

/* Column headers inside card */
.sv-col-heads{{
  display:grid;grid-template-columns:1fr auto auto auto auto;
  gap:7px;padding:4px 14px;
  font-family:'DM Mono',monospace;font-size:0.52rem;
  text-transform:uppercase;letter-spacing:0.08em;color:var(--stone);
  border-bottom:1px solid var(--border);background:rgba(0,0,0,0.1);
}}

/* Explainer */
.sv-panel{{
  display:none;padding:0 14px 10px;
  border-top:1px solid var(--border);background:rgba(0,0,0,0.1);
  max-height:260px;overflow-y:auto;
  scrollbar-width:thin;scrollbar-color:var(--border) transparent;
}}
.sv.open .sv-panel{{display:block;}}
.ep-sec{{margin-top:8px;}}
.ep-hd{{
  font-family:'DM Mono',monospace;font-size:0.56rem;text-transform:uppercase;
  letter-spacing:0.1em;color:var(--stone);margin-bottom:3px;
  display:flex;justify-content:space-between;
}}
.ep-hd span:last-child{{color:var(--gold);}}
.ev{{display:flex;align-items:center;gap:7px;padding:1px 0;font-size:0.75rem;}}
.ev-ico{{font-size:0.75rem;width:14px;text-align:center;flex-shrink:0;}}
.ev-lbl{{flex:1;color:var(--mute);}}
.ev-pts{{font-family:'DM Mono',monospace;font-size:0.7rem;font-weight:500;min-width:28px;text-align:right;}}
.pos{{color:var(--palm);}} .neg{{color:var(--ember);}}

/* Bench cost */
.bench-row{{
  padding:8px 14px;font-family:'DM Mono',monospace;font-size:0.6rem;
  color:var(--stone);display:flex;justify-content:space-between;
  background:rgba(46,134,171,0.07);border-top:1px solid var(--border);
}}
.bench-row span:last-child{{color:var(--lagoon);font-weight:500;}}

/* ── Manager Modal ── */
.backdrop{{
  display:none;position:fixed;inset:0;background:rgba(0,0,0,0.8);
  z-index:400;align-items:center;justify-content:center;padding:16px;
}}
.backdrop.open{{display:flex;}}
.modal{{
  background:var(--surface2);border:1px solid var(--border);border-radius:12px;
  width:100%;max-width:680px;max-height:90vh;overflow:hidden;
  display:flex;flex-direction:column;animation:fadeUp 0.2s ease;
}}
.modal-hd{{
  padding:16px 20px;border-bottom:1px solid var(--border);
  background:rgba(0,0,0,0.2);display:flex;justify-content:space-between;align-items:center;
}}
.modal-title{{font-family:'Cinzel',serif;font-size:1.05rem;font-weight:600;color:var(--gold);}}
.modal-x{{background:none;border:none;color:var(--stone);font-size:1.3rem;cursor:pointer;padding:0 4px;line-height:1;}}
.modal-x:hover{{color:var(--text);}}
.modal-body{{overflow-y:auto;padding:18px 20px;flex:1;}}

/* Modal stats */
.m-stats{{display:flex;gap:20px;margin-bottom:18px;padding-bottom:16px;border-bottom:1px solid var(--border);flex-wrap:wrap;}}
.m-stat-val{{font-family:'DM Mono',monospace;font-size:1.3rem;font-weight:500;color:var(--gold);display:block;}}
.m-stat-lbl{{font-family:'DM Mono',monospace;font-size:0.56rem;text-transform:uppercase;letter-spacing:0.1em;color:var(--stone);}}

/* Modal ep trend */
.m-trend{{
  font-family:'DM Mono',monospace;font-size:0.68rem;color:var(--mute);
  margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid var(--border);
  display:flex;flex-wrap:wrap;gap:8px;
}}
.m-ep-chip{{
  padding:3px 8px;border-radius:4px;background:rgba(255,255,255,0.04);
  border:1px solid var(--border);
}}
.m-ep-chip.best{{background:var(--gold-dim);border-color:var(--gold-border);color:var(--gold);}}

/* Modal survivor bars */
.m-lbl{{font-family:'DM Mono',monospace;font-size:0.58rem;text-transform:uppercase;letter-spacing:0.1em;color:var(--stone);margin-bottom:8px;}}
.m-sv{{display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid var(--border);}}
.m-sv:last-child{{border-bottom:none;}}
.m-sv-name{{font-size:0.85rem;min-width:130px;color:var(--text);}}
.m-sv-name.elim{{text-decoration:line-through;color:var(--stone);}}
.m-sv-track{{flex:1;background:rgba(255,255,255,0.04);border-radius:3px;height:5px;}}
.m-sv-fill{{height:100%;border-radius:3px;background:var(--gold);}}
.m-sv-pts{{font-family:'DM Mono',monospace;font-size:0.75rem;color:var(--gold);min-width:48px;text-align:right;}}

/* Modal league compare */
.m-vs{{display:flex;align-items:center;gap:10px;padding:5px 0;}}
.m-vs-name{{font-size:0.82rem;min-width:110px;color:var(--mute);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.m-vs-name.you{{color:var(--gold);font-weight:600;}}
.m-vs-track{{flex:1;background:rgba(255,255,255,0.04);border-radius:3px;height:5px;}}
.m-vs-fill{{height:100%;border-radius:3px;background:var(--lagoon);}}
.m-vs-fill.you{{background:var(--gold);}}
.m-vs-pts{{font-family:'DM Mono',monospace;font-size:0.72rem;color:var(--mute);min-width:48px;text-align:right;}}

/* ── Mobile ── */
@media(max-width:640px){{
  header{{padding:12px 16px;}}
  .h-title{{font-size:1.05rem;}}
  main{{padding:24px 12px 60px;gap:36px;}}
  .lb-row{{grid-template-columns:28px 1fr auto auto;gap:6px;}}
  .lb-change{{display:none;}}
  .roster-grid{{grid-template-columns:1fr;}}
  .modal{{max-height:95vh;border-radius:12px 12px 0 0;}}
  .backdrop{{align-items:flex-end;padding:0;}}
  .m-stats{{gap:14px;}}
}}

/* ── Animations ── */
@keyframes slideIn{{from{{opacity:0;transform:translateX(-6px)}}to{{opacity:1;transform:translateX(0)}}}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:translateY(0)}}}}

footer{{text-align:center;padding:18px;font-family:'DM Mono',monospace;font-size:0.58rem;color:var(--stone);letter-spacing:0.08em;border-top:1px solid var(--border);}}
</style>
</head>
<body>

<header>
  <div>
    <div class="h-title">{title}</div>
    <div class="h-sub">Survivor 50 · Fantasy Dashboard</div>
  </div>
  <div class="nav-pills">
    <a href="{this_file}" class="nav-pill active">{short_name}</a>
    <a href="{other_file}" class="nav-pill inactive">{other_short}</a>
  </div>
</header>

<div class="ep-bar" id="epBar">Loading...</div>
<div class="disc-bar">⚠ All 8 picks scoring · Active/bench filtering coming soon</div>

<main>

  <!-- 1. STANDINGS — who's winning, who moved -->
  <section>
    <div class="sec-title">Standings</div>
    <div class="sec-sub">Click any manager to see their full breakdown · ↑↓ = rank change this episode</div>
    <div class="lb" id="lb"></div>
  </section>

  <!-- 2. THIS WEEK — who had the big episode -->
  <section>
    <div class="sec-title">This Week</div>
    <div class="sec-sub">Points scored this episode · who won the week · toggle for season view</div>
    <div class="chart-card">
      <div class="chart-controls">
        <button class="chart-tab on"  onclick="setMode('episode',this)">This Episode</button>
        <button class="chart-tab"     onclick="setMode('cumulative',this)">Season Total</button>
        <span class="chart-note" id="chartNote"></span>
      </div>
      <div class="chart-box"><canvas id="chartCanvas"></canvas></div>
    </div>
  </section>

  <!-- 3. ROSTERS — bench decision lives here -->
  <section>
    <div class="sec-title">Rosters</div>
    <div class="sec-sub">
      Sorted by last episode performance · 🔥 above average · 🧊 below average ·
      bars = episode-by-episode pts · click any survivor for full breakdown
    </div>
    <div class="roster-grid" id="rosterGrid"></div>
  </section>

</main>

<footer>Survivor 50 Fantasy · Updated after each episode</footer>

<!-- Manager modal -->
<div class="backdrop" id="backdrop" onclick="backdropClick(event)">
  <div class="modal">
    <div class="modal-hd">
      <span class="modal-title" id="mTitle"></span>
      <button class="modal-x" onclick="closeModal()">×</button>
    </div>
    <div class="modal-body" id="mBody"></div>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<script>
const ALL    = {json_data};
const LEAGUE = "{league_name}";
const COLORS = ['#D4AF37','#2E86AB','#3FA34D','#E4572E','#7A3E9D','#E8B86D','#5BC0EB','#9BC53D','#FA8C16','#C084FC'];

let chart    = null;
let chartMode = 'episode';

function ld()  {{ return ALL.leagues?.[LEAGUE] || {{}}; }}
function eps() {{ return ALL.episodes || []; }}

/* ── INIT ── */
function init() {{
  const latestEp = eps()[eps().length - 1];
  document.getElementById('epBar').textContent = latestEp
    ? `Episode ${{latestEp.episode_num}}: "${{latestEp.title}}" · Jury begins next episode`
    : 'Survivor 50';

  renderLB();
  renderChart();
  renderRosters();
}}

/* ── STANDINGS ── */
function renderLB() {{
  const standings = ld().standings || [];
  const latestNum = eps()[eps().length-1]?.episode_num || 0;
  const rc = r => r===1?'g':r===2?'s':r===3?'b':'n';
  document.getElementById('lb').innerHTML = standings.map((s,i) => {{
    const chg = s.rank_change;
    const chgHtml = chg > 0
      ? `<span class="lb-change up">↑${{chg}}</span>`
      : chg < 0
      ? `<span class="lb-change dn">↓${{Math.abs(chg)}}</span>`
      : `<span class="lb-change same">—</span>`;
    return `
      <div class="lb-row r${{s.rank}}" style="animation-delay:${{i*0.04}}s" onclick="openModal('${{s.manager}}')">
        <div class="lb-rank ${{rc(s.rank)}}">${{s.rank}}</div>
        <div class="lb-name">${{s.manager}}</div>
        ${{chgHtml}}
        <div class="lb-ep">+${{s.episode_pts}} ep${{latestNum}}</div>
        <div class="lb-total">${{s.cumulative_pts}}</div>
      </div>`;
  }}).join('');
}}

/* ── CHART ── */
function setMode(mode, btn) {{
  chartMode = mode;
  document.querySelectorAll('.chart-tab').forEach(t => t.classList.remove('on'));
  btn.classList.add('on');
  renderChart();
}}

function renderChart() {{
  if (chart) {{ chart.destroy(); chart = null; }}
  const history  = ld().history  || [];
  const standings = ld().standings || [];
  const rankMap  = {{}};
  standings.forEach(s => rankMap[s.manager] = s.rank);
  const sorted   = [...history].sort((a,b) => (rankMap[a.manager]||99)-(rankMap[b.manager]||99));
  const labels   = eps().map(e => `Ep ${{e.episode_num}}`);

  const datasets = sorted.map((m,i) => {{
    const data = chartMode === 'episode'
      ? m.points_by_episode.map(p => p.episode_pts)
      : m.points_by_episode.map(p => p.cumulative_pts);
    return {{
      label: m.manager, data,
      backgroundColor: COLORS[i % COLORS.length] + (chartMode==='episode'?'CC':''),
      borderColor:     COLORS[i % COLORS.length],
      borderWidth: chartMode==='episode' ? 1 : 2,
      borderRadius: chartMode==='episode' ? 3 : 0,
      pointRadius: chartMode==='cumulative' ? 3 : 0,
      tension: 0.3,
    }};
  }});

  // Chart note
  if (chartMode === 'episode') {{
    const epWinner = sorted.reduce((best,m) => {{
      const last = m.points_by_episode[m.points_by_episode.length-1]?.episode_pts || 0;
      return last > (best.pts||0) ? {{name:m.manager, pts:last}} : best;
    }}, {{}});
    document.getElementById('chartNote').textContent =
      epWinner.name ? `🏆 ${{epWinner.name}} won this episode with ${{epWinner.pts}} pts` : '';
  }} else {{
    document.getElementById('chartNote').textContent = '';
  }}

  chart = new Chart(document.getElementById('chartCanvas'), {{
    type: chartMode === 'episode' ? 'bar' : 'line',
    data: {{ labels, datasets }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{
        legend: {{ labels: {{ font:{{family:'DM Mono',size:10}}, color:'#B8B1A3', boxWidth:10, padding:12 }} }},
        tooltip: {{
          backgroundColor:'#0B2E2E', borderColor:'#2A4A4A', borderWidth:1,
          titleFont:{{family:'DM Mono',size:10}}, bodyFont:{{family:'DM Mono',size:10}}, padding:8,
        }}
      }},
      scales: {{
        x: {{ grid:{{color:'rgba(255,255,255,0.04)'}}, ticks:{{font:{{family:'DM Mono',size:9}},color:'#5F6F73'}},
              stacked: chartMode==='episode' }},
        y: {{ grid:{{color:'rgba(255,255,255,0.04)'}}, ticks:{{font:{{family:'DM Mono',size:9}},color:'#5F6F73'}},
              stacked: chartMode==='episode' }}
      }},
    }}
  }});
}}

/* ── ROSTERS ── */
function renderRosters() {{
  const rosters  = ld().rosters   || [];
  const standings = ld().standings || [];
  const btw      = ld().best_this_week || {{}};
  const rankMap  = {{}};
  standings.forEach(s => rankMap[s.manager] = s.rank);
  const sorted   = [...rosters].sort((a,b) => (rankMap[a.manager]||99)-(rankMap[b.manager]||99));
  const maxPts   = Math.max(...sorted.flatMap(m => m.survivors.flatMap(s => s.sparkline.map(sp=>sp.pts))), 1);

  document.getElementById('rosterGrid').innerHTML = sorted.map((m,ci) => {{
    const total     = standings.find(s=>s.manager===m.manager)?.cumulative_pts || 0;
    const epPts     = standings.find(s=>s.manager===m.manager)?.episode_pts || 0;
    const benchCost = m.bench_cost || 0;

    const svRows = m.survivors.map((s,si) => {{
      const id   = `sv-${{ci}}-${{si}}`;
      const icon = s.trend==='hot'?'🔥':s.trend==='cold'?'🧊':'';
      const tip  = `Last ep: ${{s.last_ep_pts}} pts · Season avg: ${{s.avg_pts}} pts/ep`;
      const sparkHtml = s.sparkline.map(sp => {{
        const h   = Math.max(2, Math.round((sp.pts/maxPts)*16));
        const col = sp.pts > s.avg_pts*1.2 ? '#D4AF37'
                  : sp.pts < s.avg_pts*0.5 ? '#2E86AB' : '#5F6F73';
        return `<div class="spark" style="height:${{h}}px;background:${{col}}" title="Ep${{sp.ep}}: +${{sp.pts}}"></div>`;
      }}).join('');

      const pills = [
        s.eliminated ? '<span class="elim-pill">out</span>' : '',
        s.best_this_week ? '<span class="best-pill">⭐ best this week</span>' : '',
      ].filter(Boolean).join('');

      const epSecs = s.breakdown.map(ep => {{
        const evs = ep.events.map(ev =>
          `<div class="ev">
            <span class="ev-ico">${{ev.icon}}</span>
            <span class="ev-lbl">${{ev.label}}</span>
            <span class="ev-pts ${{ev.pts>=0?'pos':'neg'}}">${{ev.pts>=0?'+':''}}${{ev.pts}}</span>
          </div>`).join('');
        return `<div class="ep-sec">
          <div class="ep-hd"><span>Episode ${{ep.episode_num}}</span><span>${{ep.pts>=0?'+':''}}${{ep.pts}}</span></div>
          ${{evs}}</div>`;
      }}).join('');

      const noData = s.breakdown.length===0
        ? '<div style="color:var(--stone);font-size:0.72rem;padding:8px 0">No individual scoring events</div>'
        : '';

      const lastPtsDisplay = s.last_ep_pts > 0 ? `+${{s.last_ep_pts}}` : '—';

      return `
        <div class="sv${{s.eliminated?' elim':''}}" id="${{id}}">
          <div class="sv-row" onclick="toggle('${{id}}')" title="${{tip}}">
            <span class="sv-name">${{s.name}} ${{pills}}</span>
            <span class="trend-ico">${{icon}}</span>
            <div class="sparks">${{sparkHtml}}</div>
            <span class="sv-ep-pts">${{lastPtsDisplay}}</span>
            <span class="sv-total${{s.total_pts===0?' zero':''}}">${{s.total_pts||'—'}}</span>
            <span class="sv-arrow">▾</span>
          </div>
          <div class="sv-panel">${{noData}}${{epSecs}}</div>
        </div>`;
    }}).join('');

    const colHeads = `
      <div class="sv-col-heads">
        <span>Survivor</span>
        <span></span>
        <span>Trend</span>
        <span style="text-align:right">Last ep</span>
        <span style="text-align:right">Total</span>
        <span></span>
      </div>`;

    const benchNote = benchCost > 0
      ? `<div class="bench-row"><span>Points left on bench this season</span><span>+${{benchCost}} pts</span></div>`
      : '';

    return `
      <div class="rc" style="animation-delay:${{ci*0.04}}s">
        <div class="rc-head" onclick="openModal('${{m.manager}}')">
          <span class="rc-mgr">${{m.manager}}</span>
          <span class="rc-total">${{total}} pts · +${{epPts}} this ep</span>
        </div>
        ${{colHeads}}
        ${{svRows}}
        ${{benchNote}}
      </div>`;
  }}).join('');
}}

/* ── TOGGLE SURVIVOR ── */
function toggle(id) {{
  document.getElementById(id)?.classList.toggle('open');
}}

/* ── MODAL ── */
function openModal(mgr) {{
  const standings = ld().standings || [];
  const rosters   = ld().rosters   || [];
  const history   = ld().history   || [];
  const m         = rosters.find(r => r.manager===mgr);
  const s         = standings.find(s => s.manager===mgr);
  const h         = history.find(h => h.manager===mgr);
  if (!m || !s) return;

  const maxSv  = Math.max(...m.survivors.map(sv=>sv.total_pts), 1);
  const maxTot = Math.max(...standings.map(st=>st.cumulative_pts), 1);

  // Best episode chip
  const bestEp = h?.points_by_episode.reduce((best,ep) =>
    ep.episode_pts > (best?.episode_pts||0) ? ep : best, null);

  const epChips = (h?.points_by_episode || []).map(ep => {{
    const isBest = ep.episode_num === bestEp?.episode_num;
    return `<span class="m-ep-chip${{isBest?' best':''}}">Ep${{ep.episode_num}}: +${{ep.episode_pts}}</span>`;
  }}).join('');

  const svRows = [...m.survivors]
    .sort((a,b) => b.total_pts - a.total_pts)
    .map(sv => {{
      const w = Math.round((sv.total_pts/maxSv)*160);
      const trend = sv.trend==='hot'?'🔥':sv.trend==='cold'?'🧊':'';
      return `<div class="m-sv">
        <span class="m-sv-name${{sv.eliminated?' elim':''}}">${{trend}} ${{sv.name}}</span>
        <div class="m-sv-track"><div class="m-sv-fill" style="width:${{w}}px"></div></div>
        <span class="m-sv-pts">${{sv.total_pts}} pts</span>
      </div>`;
    }}).join('');

  const vsRows = [...standings]
    .sort((a,b) => b.cumulative_pts - a.cumulative_pts)
    .map(st => {{
      const w     = Math.round((st.cumulative_pts/maxTot)*180);
      const isYou = st.manager === mgr;
      return `<div class="m-vs">
        <span class="m-vs-name${{isYou?' you':''}}">${{st.manager}}</span>
        <div class="m-vs-track"><div class="m-vs-fill${{isYou?' you':''}}" style="width:${{w}}px"></div></div>
        <span class="m-vs-pts">${{st.cumulative_pts}}</span>
      </div>`;
    }}).join('');

  const alive = m.survivors.filter(sv=>!sv.eliminated).length;

  document.getElementById('mTitle').textContent = mgr;
  document.getElementById('mBody').innerHTML = `
    <div class="m-stats">
      <div><span class="m-stat-val">#${{s.rank}}</span><span class="m-stat-lbl">Rank</span></div>
      <div><span class="m-stat-val">${{s.cumulative_pts}}</span><span class="m-stat-lbl">Total pts</span></div>
      <div><span class="m-stat-val">+${{s.episode_pts}}</span><span class="m-stat-lbl">This episode</span></div>
      <div><span class="m-stat-val">${{alive}}</span><span class="m-stat-lbl">Alive</span></div>
    </div>
    <div class="m-lbl">Episode by episode · gold = best week</div>
    <div class="m-trend">${{epChips}}</div>
    <div class="m-lbl">Survivor contributions</div>
    ${{svRows}}
    <div class="m-lbl" style="margin-top:14px">League comparison</div>
    ${{vsRows}}
  `;
  document.getElementById('backdrop').classList.add('open');
}}

function closeModal() {{ document.getElementById('backdrop').classList.remove('open'); }}
function backdropClick(e) {{ if(e.target===document.getElementById('backdrop')) closeModal(); }}
document.addEventListener('keydown', e => {{ if(e.key==='Escape') closeModal(); }});

init();
</script>
</body>
</html>'''


def build_page(cfg: dict, data: dict) -> str:
    return HTML_TEMPLATE.format(
        title=cfg["league_name"],
        short_name=cfg["short_name"],
        this_file=cfg["filename"],
        other_file=cfg["other_file"],
        other_short=cfg["other_short"],
        league_name=cfg["league_name"],
        json_data=json.dumps(data, ensure_ascii=False),
    )


def main():
    load_config()
    conn = get_connection()
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
