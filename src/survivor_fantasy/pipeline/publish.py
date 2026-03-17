"""
pipeline/publish.py

Reads scored data from DB and writes self-contained HTML dashboard pages.
JSON data is embedded inline to avoid CORS issues when opening locally.

Output files (in frontend/):
  buffs.html   — In the Buffs League dashboard
  fjv.html     — FJV Survivor Heads League dashboard

Usage:
    python pipeline/publish.py
"""

import json
from pathlib import Path
from survivor_fantasy.db.connect import get_connection, load_config

SEASON_ID  = 50
OUTPUT_DIR = Path("frontend")

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


def fetch_data(conn) -> dict:
    """Pull all data from DB and return as a dict ready for JSON embedding."""

    episodes = conn.execute("""
        SELECT episode_id, episode_num, title, air_date
        FROM episodes WHERE season_id = ?
        ORDER BY episode_num
    """, [SEASON_ID]).fetchall()

    episode_ids = [e[0] for e in episodes]
    latest_ep_id = episode_ids[-1] if episode_ids else None

    data = {"episodes": [], "leagues": {}}
    data["episodes"] = [
        {"episode_id": e[0], "episode_num": e[1], "title": e[2], "air_date": str(e[3])}
        for e in episodes
    ]

    for cfg in LEAGUE_CONFIGS:
        league_name = cfg["league_name"]

        # Standings
        standings = conn.execute("""
            SELECT lp.name, ls.cumulative_pts, ls.episode_pts, ls.rank
            FROM league_standings ls
            JOIN league_players lp ON ls.league_player_id = lp.league_player_id
            WHERE ls.season_id = ? AND ls.episode_id = ? AND lp.league_name = ?
            ORDER BY ls.rank
        """, [SEASON_ID, latest_ep_id, league_name]).fetchall()

        # History (cumulative per episode)
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
                "episode_id": ep_id, "cumulative_pts": cum_pts, "episode_pts": ep_pts
            })

        # Elimination detection: players who appeared in confessionals in any
        # episode but are absent from the latest episode's confessionals.
        # This uses Layer 1 data only — no dependency on episode_scores or
        # players.exit_type (which defaults to voted_out for all S50 returnees).
        eliminated_ids = set(r[0] for r in conn.execute("""
            SELECT DISTINCT c.player_id
            FROM confessionals c
            WHERE c.season_id = ?
              AND c.player_id NOT IN (
                  SELECT player_id FROM confessionals
                  WHERE season_id = ? AND episode_id = ?
              )
        """, [SEASON_ID, SEASON_ID, latest_ep_id]).fetchall())

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

        managers_rosters = {}
        for manager, survivor, total_pts, player_id in roster_rows:
            if manager not in managers_rosters:
                managers_rosters[manager] = {"manager": manager, "survivors": []}
            managers_rosters[manager]["survivors"].append({
                "name": survivor,
                "player_id": player_id,
                "total_pts": total_pts,
                "eliminated": player_id in eliminated_ids,
            })

        data["leagues"][league_name] = {
            "standings":  [
                {"rank": r, "manager": n, "cumulative_pts": c, "episode_pts": e}
                for n, c, e, r in standings
            ],
            "history":    list(managers_history.values()),
            "rosters":    list(managers_rosters.values()),
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
}}

* {{ margin:0; padding:0; box-sizing:border-box; }}

body {{
  background: var(--bg);
  color: var(--text);
  font-family: 'Source Sans 3', sans-serif;
  min-height: 100vh;
  line-height: 1.5;
}}

/* Header */
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

.nav-pill.active {{
  background: var(--gold);
  color: var(--bg);
  border-color: var(--gold);
  font-weight: 500;
}}

.nav-pill.inactive {{
  color: var(--stone);
  border-color: var(--border);
}}

.nav-pill.inactive:hover {{
  color: var(--text);
  border-color: var(--stone);
}}

/* Episode bar */
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

/* Main */
main {{
  max-width: 1140px;
  margin: 0 auto;
  padding: 44px 24px 80px;
  display: flex;
  flex-direction: column;
  gap: 48px;
}}

/* Section */
.section-header {{
  display: flex;
  align-items: baseline;
  gap: 14px;
  margin-bottom: 18px;
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

/* Leaderboard */
.leaderboard {{ display: flex; flex-direction: column; gap: 6px; }}

.lb-row {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px 20px;
  display: grid;
  grid-template-columns: 40px 1fr auto auto;
  align-items: center;
  gap: 16px;
  transition: all 0.18s;
  animation: slideIn 0.4s ease both;
}}

.lb-row:hover {{
  border-color: var(--gold);
  background: var(--gold-dim);
  transform: translateX(3px);
}}

.lb-row.rank-1 {{ border-left: 3px solid var(--gold); }}
.lb-row.rank-2 {{ border-left: 3px solid var(--stone); }}
.lb-row.rank-3 {{ border-left: 3px solid #C9956A; }}

.lb-rank {{
  font-family: 'DM Mono', monospace;
  font-size: 0.8rem;
  color: var(--stone);
  text-align: center;
}}
.lb-rank.gold {{ color: var(--gold); font-weight: 500; }}
.lb-rank.silver {{ color: #AAA; }}
.lb-rank.bronze {{ color: #C9956A; }}

.lb-name {{
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text);
}}

.lb-ep-pts {{
  font-family: 'DM Mono', monospace;
  font-size: 0.7rem;
  color: var(--stone);
}}

.lb-total {{
  font-family: 'DM Mono', monospace;
  font-size: 1.05rem;
  font-weight: 500;
  color: var(--gold);
  min-width: 72px;
  text-align: right;
}}

/* Chart */
.chart-wrap {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 28px;
}}

#historyChart {{ width: 100%; height: 300px; }}

/* Breakdown table */
.breakdown-wrap {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
}}

table.breakdown {{
  width: 100%;
  border-collapse: collapse;
  font-size: 0.87rem;
}}

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

table.breakdown td {{
  padding: 11px 16px;
  border-bottom: 1px solid var(--border);
  color: var(--text-mute);
}}

table.breakdown tr:last-child td {{ border-bottom: none; }}

table.breakdown tr:hover td {{
  background: var(--gold-dim);
  color: var(--text);
}}

.td-manager {{
  font-weight: 600;
  color: var(--text);
}}

.td-pts {{
  font-family: 'DM Mono', monospace;
  text-align: right;
}}

.pts-pos {{ color: var(--palm); }}
.pts-neg {{ color: var(--ember); }}
.pts-total {{ color: var(--gold); font-weight: 500; }}

/* Roster grid */
.roster-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
}}

.roster-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: visible;
  animation: fadeUp 0.45s ease both;
  transition: border-color 0.2s;
  display: flex;
  flex-direction: column;
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

.rc-name {{
  font-family: 'Cinzel', serif;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--gold);
  letter-spacing: 0.04em;
}}

.rc-total {{
  font-family: 'DM Mono', monospace;
  font-size: 0.75rem;
  color: var(--text-mute);
}}

.rc-survivor {{
  padding: 9px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border);
  font-size: 0.83rem;
  transition: background 0.15s;
}}

.rc-survivor:last-child {{ border-bottom: none; border-radius: 0 0 10px 10px; }}
.rc-survivor:hover {{ background: var(--gold-dim); }}

.rc-survivor.eliminated {{
  opacity: 0.45;
}}
.rc-survivor.eliminated .sv-name {{
  color: var(--stone);
  text-decoration: line-through;
  text-decoration-color: var(--ember);
  text-decoration-thickness: 1px;
}}
.rc-survivor.eliminated .sv-pts {{
  color: var(--stone);
}}
.eliminated-badge {{
  font-family: 'DM Mono', monospace;
  font-size: 0.55rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--ember);
  margin-left: 6px;
  opacity: 0.8;
}}

.sv-name {{ color: var(--text); font-weight: 400; }}

.sv-pts {{
  font-family: 'DM Mono', monospace;
  font-size: 0.78rem;
  font-weight: 500;
  color: var(--text);
}}

.sv-pts.zero {{ color: var(--stone); }}

/* Animations */
@keyframes slideIn {{
  from {{ opacity: 0; transform: translateX(-10px); }}
  to   {{ opacity: 1; transform: translateX(0); }}
}}

@keyframes fadeUp {{
  from {{ opacity: 0; transform: translateY(8px); }}
  to   {{ opacity: 1; transform: translateY(0); }}
}}

/* Footer */
footer {{
  text-align: center;
  padding: 20px;
  font-family: 'DM Mono', monospace;
  font-size: 0.62rem;
  color: var(--stone);
  letter-spacing: 0.08em;
  border-top: 1px solid var(--border);
}}

/* Disclaimer */
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
  ⚠ Scores currently reflect all 8 roster picks per manager. Active/bench tracking (5 starters score, 3 bench do not) is in development — scores will be adjusted once that data is captured.
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
      <span class="section-tag">Per-survivor points · strikethrough = eliminated</span>
    </div>
    <div class="roster-grid" id="rosterGrid"></div>
  </section>
</main>

<footer>Survivor 50 Fantasy · Scoring by survivor-fantasy pipeline · Updated after each episode</footer>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<script>
// ── Embedded data (generated by publish.py) ──────────────────────────────────
const ALL_DATA = {json_data};
const LEAGUE   = "{league_name}";

// ── Chart colors ──────────────────────────────────────────────────────────────
const COLORS = [
  '#D4AF37','#2E86AB','#3FA34D','#E4572E','#7A3E9D',
  '#E8B86D','#5BC0EB','#9BC53D','#FA8C16','#C084FC'
];

// ── Init ──────────────────────────────────────────────────────────────────────
function init() {{
  const episodes = ALL_DATA.episodes || [];
  const leagueData = ALL_DATA.leagues?.[LEAGUE] || {{}};
  const standings = leagueData.standings || [];
  const history   = leagueData.history   || [];
  const rosters   = leagueData.rosters   || [];

  const latestEp = episodes[episodes.length - 1];
  document.getElementById('episodeBar').textContent = latestEp
    ? `Through Episode ${{latestEp.episode_num}}: "${{latestEp.title}}"`
    : 'Survivor 50';

  renderLeaderboard(standings);
  renderChart(history, episodes);
  renderBreakdown(history, episodes, standings);
  renderRosters(rosters, standings);
}}

function renderLeaderboard(standings) {{
  const rankClass = r => r === 1 ? 'gold' : r === 2 ? 'silver' : r === 3 ? 'bronze' : '';
  document.getElementById('leaderboard').innerHTML = standings.map((s, i) => `
    <div class="lb-row rank-${{s.rank}}" style="animation-delay:${{i*0.05}}s">
      <div class="lb-rank ${{rankClass(s.rank)}}">${{s.rank}}</div>
      <div class="lb-name">${{s.manager}}</div>
      <div class="lb-ep-pts">+${{s.episode_pts}} this ep</div>
      <div class="lb-total">${{s.cumulative_pts}} pts</div>
    </div>
  `).join('');
}}

function renderChart(history, episodes) {{
  const labels = episodes.map(e => `Ep ${{e.episode_num}}`);
  const datasets = history.map((m, i) => ({{
    label: m.manager,
    data: m.points_by_episode.map(p => p.cumulative_pts),
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
        legend: {{ labels: {{ font: {{ family: 'DM Mono', size: 11 }}, color: '#B8B1A3', boxWidth: 14 }} }},
        tooltip: {{ backgroundColor: '#0B2E2E', borderColor: '#2A4A4A', borderWidth: 1,
                    titleFont: {{ family: 'DM Mono', size: 11 }}, bodyFont: {{ family: 'DM Mono', size: 11 }}, padding: 10 }}
      }},
      scales: {{
        x: {{ grid: {{ color: '#1A4A4A' }}, ticks: {{ font: {{ family: 'DM Mono', size: 11 }}, color: '#5F6F73' }} }},
        y: {{ grid: {{ color: '#1A4A4A' }}, ticks: {{ font: {{ family: 'DM Mono', size: 11 }}, color: '#5F6F73' }} }}
      }}
    }}
  }});
}}

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
    const cells = episodes.map((e, i) => {{
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

function renderRosters(rosters, standings) {{
  const rankMap = {{}};
  standings.forEach(s => rankMap[s.manager] = s.rank);
  const sorted = [...rosters].sort((a,b) => (rankMap[a.manager]||99) - (rankMap[b.manager]||99));

  document.getElementById('rosterGrid').innerHTML = sorted.map((m, i) => {{
    const total = standings.find(s => s.manager === m.manager)?.cumulative_pts || 0;
    const survivors = m.survivors.map(s => `
      <div class="rc-survivor${{s.eliminated ? ' eliminated' : ''}}">
        <span class="sv-name">${{s.name}}${{s.eliminated ? '<span class="eliminated-badge">out</span>' : ''}}</span>
        <span class="sv-pts${{s.total_pts === 0 ? ' zero' : ''}}">${{s.total_pts > 0 ? s.total_pts + ' pts' : '—'}}</span>
      </div>
    `).join('');
    return `
      <div class="roster-card" style="animation-delay:${{i*0.06}}s">
        <div class="rc-header">
          <span class="rc-name">${{m.manager}}</span>
          <span class="rc-total">${{total}} pts total</span>
        </div>
        ${{survivors}}
      </div>
    `;
  }}).join('');
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
