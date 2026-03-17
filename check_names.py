from survivor_fantasy.db.connect import get_connection
conn = get_connection()

print("=== S50 confessionals by episode (player_id + episode_id) ===")
rows = conn.execute("""
    SELECT c.player_id, pl.full_name, c.episode_id, c.confessional_count
    FROM confessionals c
    JOIN players pl ON c.player_id = pl.player_id
    WHERE c.season_id = 50
    ORDER BY c.episode_id, pl.full_name
""").fetchall()
for r in rows: print(r)

print("\n=== Players NOT in ep3 confessionals ===")
rows = conn.execute("""
    SELECT DISTINCT c.player_id, pl.full_name
    FROM confessionals c
    JOIN players pl ON c.player_id = pl.player_id
    WHERE c.season_id = 50
      AND c.player_id NOT IN (
          SELECT player_id FROM confessionals
          WHERE season_id = 50 AND episode_id = 50003
      )
    ORDER BY pl.full_name
""").fetchall()
print(f"Found {len(rows)} eliminated players:")
for r in rows: print(r)

print("\n=== Name mapping check: events.csv names vs DB ===")
# Check all unique player names that appear in events.csv
# by looking at what the scorer successfully resolved
rows = conn.execute("""
    SELECT DISTINCT pl.full_name, pl.player_id
    FROM episode_scores es
    JOIN players pl ON es.survivor_player_id = pl.player_id
    WHERE es.season_id = 50
    ORDER BY pl.full_name
""").fetchall()
print(f"Players with episode_scores: {len(rows)}")
for r in rows: print(r)

conn.close()
