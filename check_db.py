from survivor_fantasy.db.connect import get_connection
conn = get_connection()

print("=== S50 players (all) ===")
rows = conn.execute(
    "SELECT player_id, full_name FROM players WHERE season_id=50 ORDER BY full_name"
).fetchall()
for r in rows:
    print(r)

print("\n=== S50 tribes ===")
rows = conn.execute(
    "SELECT tribe_id, tribe_name, tribe_status FROM tribes WHERE season_id=50 ORDER BY tribe_name"
).fetchall()
for r in rows:
    print(r)

conn.close()
