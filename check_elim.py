from survivor_fantasy.db.connect import get_connection
conn = get_connection()

print("=== voted_out/quit/medevac events in episode_scores ===")
rows = conn.execute("""
    SELECT DISTINCT es.survivor_player_id, pl.full_name, es.event_type
    FROM episode_scores es
    JOIN players pl ON es.survivor_player_id = pl.player_id
    WHERE es.event_type IN ('voted_out', 'player_quits', 'medical_removal')
    ORDER BY pl.full_name
""").fetchall()
print(f"Found {len(rows)} elimination events")
for r in rows: print(r)

print("\n=== Savannah events ===")
rows = conn.execute("""
    SELECT es.event_type, es.pts, es.episode_id, lp.name
    FROM episode_scores es
    JOIN league_players lp ON es.league_player_id = lp.league_player_id
    WHERE es.survivor_player_id = 'US0747_S50'
    ORDER BY es.episode_id, es.event_type
""").fetchall()
for r in rows: print(r)

print("\n=== Q Burdette events ===")
rows = conn.execute("""
    SELECT es.event_type, es.pts, es.episode_id, lp.name
    FROM episode_scores es
    JOIN league_players lp ON es.league_player_id = lp.league_player_id
    WHERE es.survivor_player_id = 'US0691_S50'
    ORDER BY es.episode_id, es.event_type
""").fetchall()
for r in rows: print(r)

conn.close()
