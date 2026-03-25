"""
bootstrap_s50.py

Creates a minimal survivor.duckdb with just the schema and S50 season/player
data needed to run the weekly scoring pipeline. Does NOT require the full
survivoR R exports or historical S1-S49 data.

Use this on machines where you only need the weekly pipeline (e.g. Mac on the go).
The Windows machine has the full historical DB built by ingest.py.

Usage:
    python bootstrap_s50.py

After this runs, proceed with the normal weekly pipeline:
    python src/survivor_fantasy/pipeline/ingest_s50.py
    python src/survivor_fantasy/pipeline/scorer.py
    python src/survivor_fantasy/pipeline/publish.py
"""

from survivor_fantasy.db.connect import get_connection
from survivor_fantasy.db.schema import create_all_tables

# =============================================================================
# S50 season record
# =============================================================================

S50_SEASON = {
    'season_id':            50,
    'season_name':          'Survivor: In the Hands of the Fans',
    'season_num':           50,
    'year':                 2026,
    'n_players':            24,
    'n_episodes':           None,
    'filming_location':     'Fiji',
    'merge_episode':        None,
    'n_starting_tribes':    3,
    'format':               'returnees',
    'era':                  'new_era',
    'day_count':            26,
    'has_redemption_island': False,
    'has_edge_of_extinction': False,
    'has_exile_island':     False,
    'n_jury_members':       None,
}

# =============================================================================
# S50 players — all 24 cast members
# player_id format: "{castaway_id}_S{season_num}"
# These IDs match the survivoR package exactly
# =============================================================================

S50_PLAYERS = [
    ('US0554_S50', 'Angelina Keeley',           'Angelina',   50),
    ('US0477_S50', 'Aubry Bracco',              'Aubry',      50),
    ('US0277_S50', 'Benjamin Wade',             'Coach',      50),
    ('US0682_S50', 'Charlie Davis',             'Charlie',    50),
    ('US0515_S50', 'Chrissy Hofbeck',           'Chrissy',    50),
    ('US0550_S50', 'Christian Hubicki',         'Christian',  50),
    ('US0179_S50', 'Cirie Fields',              'Cirie',      50),
    ('US0031_S50', 'Colby Donaldson',           'Colby',      50),
    ('US0666_S50', 'Dee Valladares',            'Dee',        50),
    ('US0668_S50', 'Emily Flippen',             'Emily',      50),
    ('US0703_S50', 'Genevieve Mushaluk',        'Genevieve',  50),
    ('US0009_S50', 'Jenna Lewis',               'Jenna',      50),
    ('US0722_S50', 'Joe Hunter',                'Joe',        50),
    ('US0615_S50', 'Jonathan Young',            'Jonathan',   50),
    ('US0724_S50', 'Kamilla Karthigesu',        'Kamilla',    50),
    ('US0726_S50', 'Kyle Fraser',               'Kyle',       50),
    ('US0555_S50', 'Mike White',                'Mike',       50),
    ('US0201_S50', 'Oscar Lusth',               'Ozzy',       50),
    ('US0691_S50', 'Q Burdette',                'Q',          50),
    ('US0560_S50', 'Rick Devens',               'Rick',       50),
    ('US0745_S50', 'Rizo Velovic',              'Rizo',       50),
    ('US0747_S50', 'Savannah Louie',            'Savannah',   50),
    ('US0144_S50', 'Stephenie LaGrossa',        'Stephenie',  50),
    ('US0695_S50', 'Tiffany Nicole Ervin',      'Tiffany',    50),
]


def main():
    import pandas as pd

    conn = get_connection()
    print("Connected to DB")

    print("Creating schema...")
    create_all_tables(conn)

    # Check if already bootstrapped
    count = conn.execute(
        "SELECT COUNT(*) FROM seasons WHERE season_id = 50"
    ).fetchone()[0]
    if count > 0:
        print("S50 data already present — skipping bootstrap.")
        print("To reset: delete data/survivor.duckdb and re-run.")
        conn.close()
        return

    # Insert S50 season
    print("Inserting S50 season...")
    df_season = pd.DataFrame([S50_SEASON])
    conn.register("_insert_df", df_season)
    conn.execute("""
        INSERT INTO seasons (
            season_id, season_name, season_num, year, n_players, n_episodes,
            filming_location, merge_episode, n_starting_tribes, format, era,
            day_count, has_redemption_island, has_edge_of_extinction,
            has_exile_island, n_jury_members
        )
        SELECT
            season_id, season_name, season_num, year, n_players, n_episodes,
            filming_location, merge_episode, n_starting_tribes, format, era,
            day_count, has_redemption_island, has_edge_of_extinction,
            has_exile_island, n_jury_members
        FROM _insert_df
    """)
    conn.unregister("_insert_df")
    print("  Inserted 1 season")

    # Insert S50 players
    print("Inserting S50 players...")
    rows = []
    for player_id, full_name, short_name, season_id in S50_PLAYERS:
        rows.append({
            'player_id':    player_id,
            'season_id':    season_id,
            'full_name':    full_name,
            'short_name':   short_name,
            'is_returnee':  True,
        })

    df_players = pd.DataFrame(rows)
    conn.register("_insert_df", df_players)
    conn.execute("""
        INSERT INTO players (player_id, season_id, full_name, short_name, is_returnee)
        SELECT player_id, season_id, full_name, short_name, is_returnee
        FROM _insert_df
    """)
    conn.unregister("_insert_df")
    print(f"  Inserted {len(rows)} players")

    conn.close()

    print("""
Bootstrap complete. This DB contains S50 data only.
The full historical DB (S1-S49) is on the Windows machine.

Next steps:
    python src/survivor_fantasy/pipeline/ingest_s50.py
    python src/survivor_fantasy/pipeline/scorer.py
    python src/survivor_fantasy/pipeline/publish.py
""")


if __name__ == "__main__":
    main()
