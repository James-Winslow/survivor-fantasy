"""
pipeline/ingest_s50.py

Loads Season 50 live data into the database:
  - Creates S50 episodes, tribes, tribe_memberships
  - Loads events.csv into confessionals (Layer 1)
  - Loads rosters.csv into league_players + league_rosters (Layer 2)

Usage:
    python pipeline/ingest_s50.py
    python pipeline/ingest_s50.py --reset   # wipe and reload S50 data

Follows project conventions:
  - DELETE WHERE season_id = 50, then INSERT (never INSERT OR REPLACE)
  - conn.register/_insert_df pattern for all bulk inserts
  - Print-based state confirmation at each step
"""

import csv
import argparse
import pandas as pd
from pathlib import Path
from survivor_fantasy.db.connect import get_connection

# =============================================================================
# Constants
# =============================================================================

SEASON_ID    = 50
EVENTS_PATH  = Path("data/season50/events.csv")
ROSTERS_PATH = Path("data/season50/rosters.csv")

# Map display names in CSV files -> DB full_name (from survivoR package)
PLAYER_NAME_MAP = {
    'Benjamin "Coach" Wade':       'Benjamin Wade',
    'Jenna Lewis-Dougherty':       'Jenna Lewis',
    'Ozzy Lusth':                  'Oscar Lusth',
    'Stephenie LaGrossa Kendrick': 'Stephenie LaGrossa',
    'Joseph "Joe" Hunter':         'Joe Hunter',
    'Tiffany Ervin':               'Tiffany Nicole Ervin',
}

# S50 episode metadata — add a row each week after the episode airs
EPISODES = [
    # (episode_num, title, air_date, swap_occurred, n_players_start, n_players_end)
    (1, 'Epic Party',               '2026-02-25', False, 24, 21),
    (2, 'Therapy Carousel',         '2026-03-04', False, 21, 20),
    (3, 'Did You Vote For a Swap?', '2026-03-11', True,  20, 19),
    (4, 'Knife to the Heart',       '2026-03-18', False, 19, 18),
    (5, 'Open Wounds',              '2026-03-25', False, 19, 17),
    (6, 'The Blood Moon',           '2026-04-01', True, 17, 14),
]

# S50 tribe configurations
# (tribe_id, tribe_name, color_hex, tribe_status, episode_formed, episode_dissolved)
TRIBES = [
    ('S50_Cila_orig', 'Cila', '#FF8C00', 'original', 1, 2),
    ('S50_Kalo_orig', 'Kalo', '#00CED1', 'original', 1, 2),
    ('S50_Vatu_orig', 'Vatu', '#FF69B4', 'original', 1, 2),
    ('S50_Cila_swap', 'Cila', '#FF8C00', 'swapped',  3, None),
    ('S50_Kalo_swap', 'Kalo', '#00CED1', 'swapped',  3, None),
    ('S50_Vatu_swap', 'Vatu', '#FF69B4', 'swapped',  3, None),
]

# (player_db_name, tribe_id, episode_joined, episode_left)
# episode_left=None means still active on that tribe configuration
TRIBE_MEMBERSHIPS = [
    # Original Cila (eps 1-2)
    ('Christian Hubicki',    'S50_Cila_orig', 1, 3),
    ('Cirie Fields',         'S50_Cila_orig', 1, 3),
    ('Emily Flippen',        'S50_Cila_orig', 1, 3),
    ('Joe Hunter',           'S50_Cila_orig', 1, 3),
    ('Jenna Lewis',          'S50_Cila_orig', 1, 2),
    ('Oscar Lusth',          'S50_Cila_orig', 1, 3),
    ('Rick Devens',          'S50_Cila_orig', 1, 3),
    ('Savannah Louie',       'S50_Cila_orig', 1, 3),
    # Original Kalo (eps 1-2)
    ('Benjamin Wade',        'S50_Kalo_orig', 1, 3),
    ('Charlie Davis',        'S50_Kalo_orig', 1, 3),
    ('Chrissy Hofbeck',      'S50_Kalo_orig', 1, 3),
    ('Dee Valladares',       'S50_Kalo_orig', 1, 3),
    ('Jonathan Young',       'S50_Kalo_orig', 1, 3),
    ('Kamilla Karthigesu',   'S50_Kalo_orig', 1, 3),
    ('Mike White',           'S50_Kalo_orig', 1, 3),
    ('Tiffany Nicole Ervin', 'S50_Kalo_orig', 1, 3),
    # Original Vatu (eps 1-2)
    ('Angelina Keeley',      'S50_Vatu_orig', 1, 3),
    ('Aubry Bracco',         'S50_Vatu_orig', 1, 3),
    ('Colby Donaldson',      'S50_Vatu_orig', 1, 3),
    ('Genevieve Mushaluk',   'S50_Vatu_orig', 1, 3),
    ('Kyle Fraser',          'S50_Vatu_orig', 1, 1),
    ('Q Burdette',           'S50_Vatu_orig', 1, 3),
    ('Rizo Velovic',         'S50_Vatu_orig', 1, 3),
    ('Stephenie LaGrossa',   'S50_Vatu_orig', 1, 3),
    # Swapped Cila (ep 3+)
    ('Charlie Davis',        'S50_Cila_swap', 3, None),
    ('Cirie Fields',         'S50_Cila_swap', 3, None),
    ('Dee Valladares',       'S50_Cila_swap', 3, None),
    ('Jonathan Young',       'S50_Cila_swap', 3, None),
    ('Kamilla Karthigesu',   'S50_Cila_swap', 3, None),
    ('Rick Devens',          'S50_Cila_swap', 3, None),
    ('Rizo Velovic',         'S50_Cila_swap', 3, None),
    # Swapped Kalo (ep 3+)
    ('Aubry Bracco',         'S50_Kalo_swap', 3, None),
    ('Benjamin Wade',        'S50_Kalo_swap', 3, None),
    ('Chrissy Hofbeck',      'S50_Kalo_swap', 3, None),
    ('Colby Donaldson',      'S50_Kalo_swap', 3, None),
    ('Genevieve Mushaluk',   'S50_Kalo_swap', 3, None),
    ('Joe Hunter',           'S50_Kalo_swap', 3, None),
    ('Tiffany Nicole Ervin', 'S50_Kalo_swap', 3, None),
    # Swapped Vatu (ep 3+)
    ('Angelina Keeley',      'S50_Vatu_swap', 3, None),
    ('Christian Hubicki',    'S50_Vatu_swap', 3, None),
    ('Emily Flippen',        'S50_Vatu_swap', 3, None),
    ('Mike White',           'S50_Vatu_swap', 3, None),
    ('Oscar Lusth',          'S50_Vatu_swap', 3, None),
    ('Q Burdette',           'S50_Vatu_swap', 3, None),
    ('Stephenie LaGrossa',   'S50_Vatu_swap', 3, None),
]

# =============================================================================
# Helpers
# =============================================================================

def build_player_lookup(conn) -> dict:
    rows = conn.execute(
        "SELECT player_id, full_name FROM players WHERE season_id = ?", [SEASON_ID]
    ).fetchall()
    lookup = {name: pid for pid, name in rows}
    print(f"  Loaded {len(lookup)} S50 player IDs from DB")
    return lookup


def resolve_player_id(name: str, player_lookup: dict, context: str = "") -> str | None:
    db_name = PLAYER_NAME_MAP.get(name, name)
    player_id = player_lookup.get(db_name)
    if player_id is None:
        print(f"  WARNING: Could not resolve '{name}' (tried '{db_name}') [{context}]")
    return player_id


def get_next_id(conn, table: str) -> int:
    return conn.execute(f"SELECT COALESCE(MAX(id), 0) + 1 FROM {table}").fetchone()[0]


# =============================================================================
# Step 1: Episodes
# =============================================================================

def ingest_episodes(conn):
    print("\n── Step 1: Episodes ─────────────────────────────────────────────")
    # Delete in FK dependency order
    conn.execute("DELETE FROM league_rosters  WHERE season_id = ?", [SEASON_ID])
    conn.execute("DELETE FROM episode_scores  WHERE season_id = ?", [SEASON_ID])
    conn.execute("DELETE FROM league_standings WHERE season_id = ?", [SEASON_ID])
    conn.execute("DELETE FROM confessionals   WHERE season_id = ?", [SEASON_ID])
    conn.execute("DELETE FROM episodes        WHERE season_id = ?", [SEASON_ID])

    rows = [{
        'episode_id':          SEASON_ID * 1000 + ep_num,
        'season_id':           SEASON_ID,
        'episode_num':         ep_num,
        'episode_num_overall': None,
        'title':               title,
        'air_date':            air_date,
        'runtime_mins':        None,
        'merge_occurred':      False,
        'swap_occurred':       swap_occurred,
        'double_elimination':  False,
        'recap_episode':       False,
        'n_players_start':     n_start,
        'n_players_end':       n_end,
    } for ep_num, title, air_date, swap_occurred, n_start, n_end in EPISODES]

    df = pd.DataFrame(rows)
    conn.register("_insert_df", df)
    conn.execute("""
        INSERT INTO episodes
            (episode_id, season_id, episode_num, episode_num_overall, title, air_date,
             runtime_mins, merge_occurred, swap_occurred, double_elimination,
             recap_episode, n_players_start, n_players_end)
        SELECT episode_id, season_id, episode_num, episode_num_overall, title, air_date,
               runtime_mins, merge_occurred, swap_occurred, double_elimination,
               recap_episode, n_players_start, n_players_end
        FROM _insert_df
    """)
    conn.unregister("_insert_df")

    count = conn.execute(
        "SELECT COUNT(*) FROM episodes WHERE season_id = ?", [SEASON_ID]
    ).fetchone()[0]
    print(f"  Inserted {count} episodes")
    for r in conn.execute(
        "SELECT episode_id, episode_num, title FROM episodes "
        "WHERE season_id = ? ORDER BY episode_num", [SEASON_ID]
    ).fetchall():
        print(f"  episode_id={r[0]}  ep{r[1]}  '{r[2]}'")


# =============================================================================
# Step 2: Tribes
# =============================================================================

def ingest_tribes(conn):
    print("\n── Step 2: Tribes ───────────────────────────────────────────────")
    # Must delete tribe_memberships before tribes due to FK
    conn.execute("DELETE FROM tribe_memberships WHERE season_id = ?", [SEASON_ID])
    conn.execute("DELETE FROM tribes           WHERE season_id = ?", [SEASON_ID])

    rows = [{
        'tribe_id':         tribe_id,
        'season_id':        SEASON_ID,
        'tribe_name':       tribe_name,
        'color_hex':        color_hex,
        'tribe_status':     tribe_status,
        'episode_formed':   ep_formed,
        'episode_dissolved': ep_dissolved,
    } for tribe_id, tribe_name, color_hex, tribe_status, ep_formed, ep_dissolved in TRIBES]

    df = pd.DataFrame(rows)
    conn.register("_insert_df", df)
    conn.execute("""
        INSERT INTO tribes
            (tribe_id, season_id, tribe_name, color_hex,
             tribe_status, episode_formed, episode_dissolved)
        SELECT tribe_id, season_id, tribe_name, color_hex,
               tribe_status, episode_formed, episode_dissolved
        FROM _insert_df
    """)
    conn.unregister("_insert_df")

    count = conn.execute(
        "SELECT COUNT(*) FROM tribes WHERE season_id = ?", [SEASON_ID]
    ).fetchone()[0]
    print(f"  Inserted {count} tribes")


# =============================================================================
# Step 3: Tribe memberships
# =============================================================================

def ingest_tribe_memberships(conn, player_lookup: dict):
    print("\n── Step 3: Tribe memberships ────────────────────────────────────")
    # Already cleared in ingest_tribes

    rows = []
    skipped = 0
    for db_name, tribe_id, ep_joined, ep_left in TRIBE_MEMBERSHIPS:
        player_id = player_lookup.get(db_name)
        if player_id is None:
            print(f"  WARNING: unknown player '{db_name}' in TRIBE_MEMBERSHIPS")
            skipped += 1
            continue
        rows.append({
            'player_id':      player_id,
            'tribe_id':       tribe_id,
            'season_id':      SEASON_ID,
            'episode_joined': ep_joined,
            'episode_left':   ep_left,
            'reason_joined':  'draft' if ep_joined == 1 else 'swap',
        })

    df = pd.DataFrame(rows)
    start_id = get_next_id(conn, "tribe_memberships")
    df['id'] = range(start_id, start_id + len(df))
    conn.register("_insert_df", df)
    conn.execute("""
        INSERT INTO tribe_memberships
            (id, player_id, tribe_id, season_id, episode_joined, episode_left, reason_joined)
        SELECT id, player_id, tribe_id, season_id, episode_joined, episode_left, reason_joined
        FROM _insert_df
    """)
    conn.unregister("_insert_df")

    count = conn.execute(
        "SELECT COUNT(*) FROM tribe_memberships WHERE season_id = ?", [SEASON_ID]
    ).fetchone()[0]
    print(f"  Inserted {count} tribe memberships  (skipped {skipped})")


# =============================================================================
# Step 4: Confessionals from events.csv
# =============================================================================

def ingest_confessionals(conn, player_lookup: dict):
    print("\n── Step 4: Confessionals ────────────────────────────────────────")
    if not EVENTS_PATH.exists():
        print(f"  ERROR: {EVENTS_PATH} not found — skipping")
        return

    # Already cleared in ingest_episodes
    events = list(csv.DictReader(EVENTS_PATH.open(encoding='utf-8-sig')))
    print(f"  Read {len(events)} rows from {EVENTS_PATH}")

    rows = []
    skipped = 0
    for row in events:
        player_id = resolve_player_id(row['player_name'], player_lookup, f"ep{row['episode']}")
        if player_id is None:
            skipped += 1
            continue

        episode_id = conn.execute(
            "SELECT episode_id FROM episodes WHERE season_id = ? AND episode_num = ?",
            [SEASON_ID, int(row['episode'])]
        ).fetchone()
        if episode_id is None:
            print(f"  WARNING: no episode_id for episode {row['episode']}")
            skipped += 1
            continue

        # Skip confessional row for eliminated players in their exit episode.
        # Confessional presence in the latest episode is used as the elimination
        # signal in publish.py — eliminated players must be absent from ep N.
        if int(row['voted_out']) == 1 or int(row['quit']) == 1 or int(row['medevac']) == 1:
            skipped += 1
            continue

        rows.append({
            'player_id':          player_id,
            'episode_id':         episode_id[0],
            'season_id':          SEASON_ID,
            'confessional_count': int(row['confessional_count']),
        })

    df = pd.DataFrame(rows)
    start_id = get_next_id(conn, "confessionals")
    df['id'] = range(start_id, start_id + len(df))
    conn.register("_insert_df", df)
    conn.execute("""
        INSERT INTO confessionals (id, player_id, episode_id, season_id, confessional_count)
        SELECT id, player_id, episode_id, season_id, confessional_count
        FROM _insert_df
    """)
    conn.unregister("_insert_df")

    count = conn.execute(
        "SELECT COUNT(*) FROM confessionals WHERE season_id = ?", [SEASON_ID]
    ).fetchone()[0]
    print(f"  Inserted {count} confessional rows  (skipped {skipped})")


# =============================================================================
# Step 5a: Eliminated players from events.csv
# Stores a clean set of eliminated player_ids derived directly from
# still_in_game=0 rows in events.csv. This is the authoritative source
# for elimination status — not confessional presence, not players.exit_type.
# Handles edge cases: ep1 boots (no prior confessionals), double eliminations,
# medevacs, quits, etc.
# =============================================================================

def ingest_eliminated_players(conn, player_lookup: dict):
    print("\n── Step 5a: Eliminated players ──────────────────────────────────")
    if not EVENTS_PATH.exists():
        print(f"  ERROR: {EVENTS_PATH} not found — skipping")
        return

    events = list(csv.DictReader(EVENTS_PATH.open(encoding='utf-8-sig')))

    # A player is eliminated if any row has still_in_game=0
    eliminated = set()
    for row in events:
        if int(row['still_in_game']) == 0:
            player_id = resolve_player_id(
                row['player_name'], player_lookup, f"ep{row['episode']}"
            )
            if player_id:
                eliminated.add(player_id)

    # Store in a simple key-value table using DuckDB
    # We use a temp view since we don't need a persistent table —
    # publish.py will query this via a Python set passed from ingest context.
    # Instead, write to a lightweight season_state table.
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS season_state (
                season_id  INTEGER NOT NULL,
                key        VARCHAR NOT NULL,
                value      VARCHAR NOT NULL,
                PRIMARY KEY (season_id, key, value)
            )
        """)
    except Exception:
        pass

    conn.execute("DELETE FROM season_state WHERE season_id = ? AND key = 'eliminated'",
                 [SEASON_ID])

    if eliminated:
        import pandas as pd
        df = pd.DataFrame([
            {'season_id': SEASON_ID, 'key': 'eliminated', 'value': pid}
            for pid in eliminated
        ])
        conn.register("_insert_df", df)
        conn.execute("""
            INSERT INTO season_state (season_id, key, value)
            SELECT season_id, key, value FROM _insert_df
        """)
        conn.unregister("_insert_df")

    print(f"  Stored {len(eliminated)} eliminated player IDs: "
          f"{[player_lookup.get(p, p) for p in sorted(eliminated)]}")


# =============================================================================
# Step 5: League players from rosters.csv
# league_players has one row per manager PER LEAGUE so Jimmy Winslow
# appears twice — once for each league he's in.
# =============================================================================

def ingest_league_players(conn) -> dict:
    print("\n── Step 5: League players ───────────────────────────────────────")
    if not ROSTERS_PATH.exists():
        print(f"  ERROR: {ROSTERS_PATH} not found — skipping")
        return {}

    roster_rows = list(csv.DictReader(ROSTERS_PATH.open(encoding='utf-8-sig')))

    # Add league_name column if it doesn't exist yet
    conn.execute("DROP TABLE IF EXISTS league_standings CASCADE")
    conn.execute("DROP TABLE IF EXISTS episode_scores   CASCADE")
    conn.execute("DROP TABLE IF EXISTS league_rosters   CASCADE")
    conn.execute("DROP TABLE IF EXISTS league_players   CASCADE")
    conn.execute("""
        CREATE TABLE league_players (
            league_player_id INTEGER PRIMARY KEY,
            name             VARCHAR NOT NULL,
            league_name      VARCHAR,
            email            VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE league_rosters (
            id                  INTEGER PRIMARY KEY,
            league_player_id    INTEGER NOT NULL REFERENCES league_players(league_player_id),
            survivor_player_id  VARCHAR NOT NULL REFERENCES players(player_id),
            episode_id          INTEGER NOT NULL REFERENCES episodes(episode_id),
            season_id           INTEGER NOT NULL,
            is_active           BOOLEAN NOT NULL,
            UNIQUE (league_player_id, survivor_player_id, episode_id)
        )
    """)
    conn.execute("""
        CREATE TABLE episode_scores (
            id                  INTEGER PRIMARY KEY,
            league_player_id    INTEGER NOT NULL REFERENCES league_players(league_player_id),
            episode_id          INTEGER NOT NULL REFERENCES episodes(episode_id),
            season_id           INTEGER NOT NULL,
            survivor_player_id  VARCHAR NOT NULL REFERENCES players(player_id),
            event_type          VARCHAR NOT NULL,
            pts                 INTEGER NOT NULL,
            event_description   VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE league_standings (
            id                  INTEGER PRIMARY KEY,
            league_player_id    INTEGER NOT NULL REFERENCES league_players(league_player_id),
            episode_id          INTEGER NOT NULL REFERENCES episodes(episode_id),
            season_id           INTEGER NOT NULL,
            episode_pts         INTEGER DEFAULT 0,
            cumulative_pts      INTEGER DEFAULT 0,
            rank                INTEGER,
            UNIQUE (league_player_id, episode_id)
        )
    """)

    # Collect unique (manager_name, league_name) pairs
    seen = set()
    unique_managers = []
    for row in roster_rows:
        if not row['manager']:
            continue
        key = (row['manager'], row['league'])
        if key not in seen:
            seen.add(key)
            unique_managers.append({'name': row['manager'], 'league_name': row['league']})

    unique_managers.sort(key=lambda x: (x['league_name'], x['name']))
    print(f"  Found {len(unique_managers)} manager×league combinations")

    df = pd.DataFrame(unique_managers)
    df['league_player_id'] = range(1, len(df) + 1)
    df['email'] = None

    conn.register("_insert_df", df)
    conn.execute("""
        INSERT INTO league_players (league_player_id, name, league_name, email)
        SELECT league_player_id, name, league_name, email
        FROM _insert_df
    """)
    conn.unregister("_insert_df")

    # Return lookup keyed by (name, league_name) -> league_player_id
    rows = conn.execute(
        "SELECT league_player_id, name, league_name FROM league_players"
    ).fetchall()
    lookup = {(name, league): lp_id for lp_id, name, league in rows}
    print(f"  Inserted {len(lookup)} league players:")
    for (name, league), lp_id in sorted(lookup.items(), key=lambda x: x[0]):
        print(f"    [{lp_id:>2}] {name:<22} ({league})")
    return lookup


# =============================================================================
# Step 6: League rosters
# =============================================================================

def ingest_league_rosters(conn, player_lookup: dict, lp_lookup: dict):
    print("\n── Step 6: League rosters ───────────────────────────────────────")
    if not ROSTERS_PATH.exists():
        print(f"  ERROR: {ROSTERS_PATH} not found — skipping")
        return

    roster_rows = list(csv.DictReader(ROSTERS_PATH.open(encoding='utf-8-sig')))
    # Already cleared in ingest_episodes

    episode_num_to_id = {
        ep_num: ep_id for ep_num, ep_id in conn.execute(
            "SELECT episode_num, episode_id FROM episodes WHERE season_id = ?", [SEASON_ID]
        ).fetchall()
    }
    n_episodes = len(episode_num_to_id)

    rows = []
    skipped = 0
    for row in roster_rows:
        manager_name    = row['manager']
        contestant_name = row['contestant_name']
        league_name     = row['league']

        if not manager_name:
            skipped += 1
            continue

        lp_id = lp_lookup.get((manager_name, league_name))
        if lp_id is None:
            print(f"  WARNING: unknown manager '{manager_name}' in '{league_name}'")
            skipped += 1
            continue

        player_id = resolve_player_id(
            contestant_name, player_lookup, f"roster:{manager_name}"
        )
        if player_id is None:
            skipped += 1
            continue

        for ep_num, ep_id in episode_num_to_id.items():
            rows.append({
                'league_player_id':   lp_id,
                'survivor_player_id': player_id,
                'episode_id':         ep_id,
                'season_id':          SEASON_ID,
                'is_active':          True,
            })

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=['league_player_id', 'survivor_player_id', 'episode_id'])
    start_id = get_next_id(conn, "league_rosters")
    df['id'] = range(start_id, start_id + len(df))

    conn.register("_insert_df", df)
    conn.execute("""
        INSERT INTO league_rosters
            (id, league_player_id, survivor_player_id, episode_id, season_id, is_active)
        SELECT id, league_player_id, survivor_player_id, episode_id, season_id, is_active
        FROM _insert_df
    """)
    conn.unregister("_insert_df")

    count = conn.execute(
        "SELECT COUNT(*) FROM league_rosters WHERE season_id = ?", [SEASON_ID]
    ).fetchone()[0]
    print(f"  Inserted {count} league roster rows  (skipped {skipped})")


# =============================================================================
# Validation
# =============================================================================

def validate(conn):
    print("\n── Validation ───────────────────────────────────────────────────")
    checks = [
        ("episodes",          f"SELECT COUNT(*) FROM episodes WHERE season_id={SEASON_ID}"),
        ("tribes",            f"SELECT COUNT(*) FROM tribes WHERE season_id={SEASON_ID}"),
        ("tribe_memberships", f"SELECT COUNT(*) FROM tribe_memberships WHERE season_id={SEASON_ID}"),
        ("confessionals",     f"SELECT COUNT(*) FROM confessionals WHERE season_id={SEASON_ID}"),
        ("league_players",    "SELECT COUNT(*) FROM league_players"),
        ("league_rosters",    f"SELECT COUNT(*) FROM league_rosters WHERE season_id={SEASON_ID}"),
    ]
    all_ok = True
    for label, sql in checks:
        count = conn.execute(sql).fetchone()[0]
        status = "OK" if count > 0 else "EMPTY"
        if status == "EMPTY":
            all_ok = False
        print(f"  {label:<22} {count:>6}  [{status}]")
    if all_ok:
        print("\n  All checks passed.")
    else:
        print("\n  WARNING: some tables are empty.")


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Ingest S50 live data")
    parser.add_argument("--reset", action="store_true",
                        help="Delete all S50 data before reloading")
    args = parser.parse_args()

    conn = get_connection()
    print("Connected to DB")

    if args.reset:
        print("\nReset: deleting all S50 data in FK order...")
        for table, condition in [
            ("league_rosters",   f"season_id = {SEASON_ID}"),
            ("episode_scores",   f"season_id = {SEASON_ID}"),
            ("league_standings", f"season_id = {SEASON_ID}"),
            ("confessionals",    f"season_id = {SEASON_ID}"),
            ("tribe_memberships",f"season_id = {SEASON_ID}"),
            ("tribes",           f"season_id = {SEASON_ID}"),
            ("episodes",         f"season_id = {SEASON_ID}"),
            ("league_players",   "1=1"),
        ]:
            conn.execute(f"DELETE FROM {table} WHERE {condition}")
            print(f"  Cleared {table}")

    player_lookup = build_player_lookup(conn)

    ingest_episodes(conn)
    ingest_tribes(conn)
    ingest_tribe_memberships(conn, player_lookup)
    ingest_confessionals(conn, player_lookup)
    ingest_eliminated_players(conn, player_lookup)
    lp_lookup = ingest_league_players(conn)
    ingest_league_rosters(conn, player_lookup, lp_lookup)

    validate(conn)
    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
