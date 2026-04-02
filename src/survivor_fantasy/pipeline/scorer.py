"""
pipeline/scorer.py

Reads events.csv + league_rosters, applies config.yaml scoring rules,
writes episode_scores and league_standings tables.

Usage:
    python pipeline/scorer.py
    python pipeline/scorer.py --episode 3   # rescore one episode only

Follows project conventions:
  - DELETE WHERE season_id = 50, then INSERT
  - Config-driven: all point values from config.yaml
  - Print-based state confirmation at each step
"""

import csv
import argparse
import pandas as pd
from pathlib import Path
from collections import defaultdict
from survivor_fantasy.db.connect import get_connection, load_config

SEASON_ID   = 50
EVENTS_PATH = Path("data/season50/events.csv")

PLAYER_NAME_MAP = {
    'Benjamin "Coach" Wade':       'Benjamin Wade',
    'Jenna Lewis-Dougherty':       'Jenna Lewis',
    'Ozzy Lusth':                  'Oscar Lusth',
    'Stephenie LaGrossa Kendrick': 'Stephenie LaGrossa',
    'Joseph "Joe" Hunter':         'Joe Hunter',
    'Tiffany Ervin':               'Tiffany Nicole Ervin',
}

LEAGUE_NAMES = [
    'In the Buffs League',
    'FJV Survivor Heads League',
]


# =============================================================================
# Scoring rules
# Returns list of (event_type, pts, description) for one events.csv row
# =============================================================================

def score_event_row(row: dict, cfg: dict) -> list[tuple[str, int, str]]:
    events = []
    merge = row['merge_status']

    # Survival
    if (int(row['still_in_game']) == 1
            and int(row['voted_out']) == 0
            and int(row['quit']) == 0
            and int(row['medevac']) == 0):
        if merge == 'pre':
            events.append(('survived_pre_merge', cfg['survived_pre_merge_pts'],
                           'Survived pre-merge episode'))
        else:
            events.append(('survived_post_merge', cfg['survived_post_merge_pts'],
                           'Survived post-merge episode'))

    # Reward
    if int(row['reward_participant']) == 1:
        place = int(row['tribe_immunity_place']) if row['tribe_immunity_place'] else 0
        if place == 1:
            events.append(('reward_first_place_bonus', cfg['reward_first_place_bonus_pts'],
                           'Won reward (1st place bonus)'))
        events.append(('reward_participant', cfg['reward_participant_pts'],
                       'Participated in reward'))

    # Team immunity
    if int(row['tribe_won_immunity']) == 1:
        place = int(row['tribe_immunity_place']) if row['tribe_immunity_place'] else 0
        if place == 1:
            events.append(('team_immunity_first_place_bonus', cfg['team_immunity_first_place_bonus_pts'],
                           'Won team immunity (1st place bonus)'))
        events.append(('team_immunity', cfg['team_immunity_pts'],
                       'Tribe won immunity'))

    # Individual challenges
    if int(row['won_individual_reward']) == 1:
        events.append(('wins_individual_reward', cfg['wins_individual_reward_pts'],
                       'Won individual reward'))

    if int(row['had_individual_immunity']) == 1:
        events.append(('wins_individual_immunity', cfg['wins_individual_immunity_pts'],
                       'Won individual immunity'))

    # Idols and advantages
    if int(row['found_idol_clue']) == 1:
        events.append(('gets_idol_clue', cfg['gets_idol_clue_pts'],
                       'Found idol clue / received boomerang idol'))

    if int(row['found_hidden_idol']) == 1:
        events.append(('finds_hidden_idol', cfg['finds_hidden_idol_pts'],
                       'Found hidden immunity idol'))

    if int(row['played_idol']) == 1:
        target = row['played_idol_for'] or 'self'
        events.append(('plays_idol_successfully', cfg['plays_idol_successfully_pts'],
                       f'Played idol for {target}'))

    if int(row['voted_out_holding_idol']) == 1:
        events.append(('voted_out_holding_idol', cfg['voted_out_holding_idol_pts'],
                       'Voted out holding unplayed idol'))

    if int(row['lost_vote']) == 1:
        events.append(('loses_vote', cfg['loses_vote_pts'],
                       'Lost their vote'))

    # Elimination
    if int(row['quit']) == 1:
        events.append(('player_quits', cfg['player_quits_pts'],
                       'Quit the game'))

    if int(row['medevac']) == 1:
        events.append(('medical_removal', cfg['medical_removal_pts'],
                       'Medical evacuation'))

    if int(row['voted_out']) == 1:
        events.append(('voted_out', 0,
                       'Voted out'))  # 0 pts but used for elimination detection

    # New event types
    if int(row.get('received_boomerang_idol', 0)) == 1:
        events.append(('receives_boomerang_idol', cfg.get('receives_boomerang_idol_pts', 3),
                       'Received boomerang idol'))

    if int(row.get('received_extra_vote', 0)) == 1:
        events.append(('earns_extra_vote', cfg.get('earns_extra_vote_pts', 3),
                       'Earned extra vote'))

    if int(row.get('made_fake_idol', 0)) == 1:
        events.append(('makes_fake_idol', cfg.get('makes_fake_idol_pts', 2),
                       'Made fake immunity idol'))

    if int(row.get('journey', 0)) == 1:
        events.append(('participates_in_summit', cfg.get('participates_in_summit_pts', 1),
                       'Participated in journey/summit'))

    if int(row.get('found_twist', 0)) == 1:
        events.append(('finds_twist', cfg.get('participates_in_summit_pts', 3),
                       'Found twist advantage'))

    # End game
    if int(row['received_jury_vote']) == 1:
        events.append(('jury_vote', cfg['jury_vote_pts'],
                       'Received jury vote'))

    if int(row['sole_survivor']) == 1:
        events.append(('sole_survivor', cfg['sole_survivor_pts'],
                       'Sole Survivor'))

    return events


# =============================================================================
# Main scorer
# =============================================================================

def run_scorer(conn, cfg: dict, target_episode: int | None = None):
    league_cfg = cfg['league']

    # Load lookups
    player_lookup = {
        name: pid for pid, name in conn.execute(
            "SELECT player_id, full_name FROM players WHERE season_id = ?", [SEASON_ID]
        ).fetchall()
    }
    print(f"  Loaded {len(player_lookup)} S50 players")

    episode_lookup = {
        ep_num: ep_id for ep_num, ep_id in conn.execute(
            "SELECT episode_num, episode_id FROM episodes WHERE season_id = ?", [SEASON_ID]
        ).fetchall()
    }
    print(f"  Loaded {len(episode_lookup)} S50 episodes")

    # Roster map: (survivor_player_id, episode_id) -> [league_player_id]
    roster_rows = conn.execute("""
        SELECT lr.league_player_id, lr.survivor_player_id, lr.episode_id
        FROM league_rosters lr
        WHERE lr.season_id = ? AND lr.is_active = true
    """, [SEASON_ID]).fetchall()

    roster_map: dict[tuple, list[int]] = defaultdict(list)
    for lp_id, survivor_id, ep_id in roster_rows:
        roster_map[(survivor_id, ep_id)].append(lp_id)
    print(f"  Loaded {len(roster_rows)} active roster entries")

    # Read events
    events = list(csv.DictReader(EVENTS_PATH.open(encoding='utf-8-sig')))
    print(f"  Read {len(events)} event rows")

    if target_episode is not None:
        events = [r for r in events if int(r['episode']) == target_episode]
        print(f"  Filtered to episode {target_episode}: {len(events)} rows")

    # Clear existing scores
    if target_episode is not None:
        ep_id = episode_lookup.get(target_episode)
        if ep_id:
            conn.execute("DELETE FROM episode_scores  WHERE season_id=? AND episode_id=?",
                         [SEASON_ID, ep_id])
            conn.execute("DELETE FROM league_standings WHERE season_id=? AND episode_id=?",
                         [SEASON_ID, ep_id])
    else:
        conn.execute("DELETE FROM episode_scores  WHERE season_id=?", [SEASON_ID])
        conn.execute("DELETE FROM league_standings WHERE season_id=?", [SEASON_ID])

    # Score events
    score_rows = []
    unmatched_players = set()
    no_roster = set()

    for row in events:
        db_name   = PLAYER_NAME_MAP.get(row['player_name'], row['player_name'])
        player_id = player_lookup.get(db_name)
        ep_num    = int(row['episode'])
        ep_id     = episode_lookup.get(ep_num)

        if player_id is None:
            unmatched_players.add(row['player_name'])
            continue
        if ep_id is None:
            print(f"  WARNING: no episode_id for episode {ep_num}")
            continue

        point_events = score_event_row(row, league_cfg)
        owners = roster_map.get((player_id, ep_id), [])

        if not owners:
            no_roster.add((row['player_name'], ep_num))
            continue

        for lp_id in owners:
            for event_type, pts, description in point_events:
                score_rows.append({
                    'league_player_id':   lp_id,
                    'episode_id':         ep_id,
                    'season_id':          SEASON_ID,
                    'survivor_player_id': player_id,
                    'event_type':         event_type,
                    'pts':                pts,
                    'event_description':  description,
                })

    if unmatched_players:
        print(f"  WARNING: unmatched players: {sorted(unmatched_players)}")
    if no_roster:
        print(f"  NOTE: {len(no_roster)} survivor×episode not on any roster "
              f"(eliminated players expected)")

    print(f"  Generated {len(score_rows)} score events")

    if not score_rows:
        print("  ERROR: no score rows — check events.csv and rosters")
        return

    # Insert episode_scores
    df = pd.DataFrame(score_rows)
    start_id = conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM episode_scores").fetchone()[0]
    df['id'] = range(start_id, start_id + len(df))
    conn.register("_insert_df", df)
    conn.execute("""
        INSERT INTO episode_scores
            (id, league_player_id, episode_id, season_id,
             survivor_player_id, event_type, pts, event_description)
        SELECT id, league_player_id, episode_id, season_id,
               survivor_player_id, event_type, pts, event_description
        FROM _insert_df
    """)
    conn.unregister("_insert_df")
    print(f"  Inserted {conn.execute('SELECT COUNT(*) FROM episode_scores WHERE season_id=?', [SEASON_ID]).fetchone()[0]} episode_score rows")

    # Compute standings per league per episode
    print("\n── Computing league standings ───────────────────────────────────")

    ep_pts_rows = conn.execute("""
        SELECT lp.league_name, es.league_player_id, es.episode_id, SUM(es.pts) as episode_pts
        FROM episode_scores es
        JOIN league_players lp ON es.league_player_id = lp.league_player_id
        WHERE es.season_id = ?
        GROUP BY lp.league_name, es.league_player_id, es.episode_id
        ORDER BY lp.league_name, es.episode_id, es.league_player_id
    """, [SEASON_ID]).fetchall()

    # Build cumulative totals per league
    cumulative: dict[int, int] = defaultdict(int)
    standing_rows = []
    by_league_episode: dict[tuple, list] = defaultdict(list)

    for league_name, lp_id, ep_id, pts in ep_pts_rows:
        cumulative[lp_id] += pts
        row = {
            'league_player_id': lp_id,
            'episode_id':       ep_id,
            'season_id':        SEASON_ID,
            'episode_pts':      pts,
            'cumulative_pts':   cumulative[lp_id],
            'rank':             None,
        }
        standing_rows.append(row)
        by_league_episode[(league_name, ep_id)].append(row)

    # Assign ranks within each league×episode by cumulative pts
    for rows in by_league_episode.values():
        for rank, row in enumerate(
            sorted(rows, key=lambda x: x['cumulative_pts'], reverse=True), 1
        ):
            row['rank'] = rank

    if not standing_rows:
        print("  No standings to insert")
        return

    df_s = pd.DataFrame(standing_rows)
    start_id = conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM league_standings").fetchone()[0]
    df_s['id'] = range(start_id, start_id + len(df_s))
    conn.register("_insert_df", df_s)
    conn.execute("""
        INSERT INTO league_standings
            (id, league_player_id, episode_id, season_id,
             episode_pts, cumulative_pts, rank)
        SELECT id, league_player_id, episode_id, season_id,
               episode_pts, cumulative_pts, rank
        FROM _insert_df
    """)
    conn.unregister("_insert_df")
    print(f"  Inserted {conn.execute('SELECT COUNT(*) FROM league_standings WHERE season_id=?', [SEASON_ID]).fetchone()[0]} league_standings rows")

    # Print standings per league
    latest_ep = max(episode_lookup.values())
    for league_name in LEAGUE_NAMES:
        print(f"\n── {league_name} ────────────────────────────────────────")
        summary = conn.execute("""
            SELECT lp.name, ls.cumulative_pts, ls.rank
            FROM league_standings ls
            JOIN league_players lp ON ls.league_player_id = lp.league_player_id
            WHERE ls.season_id = ? AND ls.episode_id = ? AND lp.league_name = ?
            ORDER BY ls.rank
        """, [SEASON_ID, latest_ep, league_name]).fetchall()
        for name, pts, rank in summary:
            print(f"  {rank:>2}. {name:<22} {pts:>4} pts")


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Score S50 fantasy league")
    parser.add_argument("--episode", type=int, default=None,
                        help="Score only this episode (default: all)")
    args = parser.parse_args()

    config = load_config()
    conn   = get_connection()
    print("Connected to DB")

    run_scorer(conn, config, target_episode=args.episode)

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
