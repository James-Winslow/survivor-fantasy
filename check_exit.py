from survivor_fantasy.db.connect import get_connection
conn = get_connection()

print("=== S50 player exit_types ===")
rows = conn.execute("""
    SELECT full_name, exit_type, placement
    FROM players WHERE season_id = 50
    ORDER BY full_name
""").fetchall()
for r in rows: print(r)
conn.close()

print("\n=== voted_out events in episode_scores ===")
rows = conn.execute("""
    SELECT es.survivor_player_id, pl.full_name, es.event_type, es.episode_id, lp.name
    FROM episode_scores es
    JOIN players pl ON es.survivor_player_id = pl.player_id
    JOIN league_players lp ON es.league_player_id = lp.league_player_id
    WHERE es.event_type IN ('voted_out','player_quits','medical_removal')
    ORDER BY es.episode_id, pl.full_name
""").fetchall()
for r in rows: print(r)
