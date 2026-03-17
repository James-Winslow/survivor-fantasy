from survivor_fantasy.db.connect import get_connection
conn = get_connection()

print("=== Jenna episode_scores ===")
rows = conn.execute("""
    SELECT es.event_type, es.pts, es.episode_id, lp.name as manager
    FROM episode_scores es
    JOIN league_players lp ON es.league_player_id = lp.league_player_id
    WHERE es.survivor_player_id = 'US0009_S50'
    ORDER BY es.episode_id, es.event_type
""").fetchall()
for r in rows: print(r)

print("\n=== Jenna player record ===")
rows = conn.execute(
    "SELECT player_id, full_name, exit_type, placement FROM players WHERE player_id = 'US0009_S50'"
).fetchall()
for r in rows: print(r)

conn.close()
