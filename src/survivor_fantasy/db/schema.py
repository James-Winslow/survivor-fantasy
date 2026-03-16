"""
DDL for all database tables and indexes.

Layer 1 — Survivor Data Platform (show facts, no league context)
  Core:     seasons, players, tribe_memberships, tribes, episodes,
            tribal_councils, votes, challenges, challenge_participants,
            advantages, confessionals, confessional_text
  Computed: alliance_index, player_season_stats

Layer 2 — Fantasy League Application
  league_players, league_rosters, episode_scores, league_standings

Design principles:
  - Layer 1 has zero knowledge of any fantasy league.
  - Layer 2 references Layer 1 via foreign keys only.
  - All DDL is idempotent (CREATE TABLE IF NOT EXISTS).
  - Tables are created in dependency order.
  - Constraints are explicit — bad data fails loudly at insert time.
  - Every FK and every column appearing in WHERE/JOIN has an index.
  - Computed tables (alliance_index, player_season_stats) are rebuilt
    by pipeline/features.py and never manually edited.
  - confessional_text is a Phase 4 placeholder — empty until NLP work begins.
"""

from survivor_fantasy.db.connect import get_connection

# =============================================================================
# LAYER 1 — CORE TABLES
# =============================================================================

CREATE_SEASONS = """
CREATE TABLE IF NOT EXISTS seasons (
    season_id               INTEGER PRIMARY KEY,
    season_name             VARCHAR NOT NULL,
    season_num              INTEGER NOT NULL UNIQUE,
    year                    INTEGER,
    n_players               INTEGER,
    n_episodes              INTEGER,
    filming_location        VARCHAR,
    merge_episode           INTEGER,
    n_starting_tribes       INTEGER,

    -- Game format classification
    -- Used to condition models on structural differences between eras
    format                  VARCHAR
        CHECK (format IN ('classic', 'new_era', 'returnees', 'mixed', 'unknown')),
    era                     VARCHAR
        CHECK (era IN ('original', 'hd', 'new_era'))
        -- original: S1–S20 (39 days, classic structure)
        -- hd:       S21–S40 (39 days, modern production)
        -- new_era:  S41+    (26 days, revised advantage system)
    ,
    day_count               INTEGER,        -- 26 (new era) or 39 (classic)
    has_redemption_island   BOOLEAN DEFAULT FALSE,
    has_edge_of_extinction  BOOLEAN DEFAULT FALSE,
    has_exile_island        BOOLEAN DEFAULT FALSE,
    n_jury_members          INTEGER         -- varies by season
);
"""

CREATE_PLAYERS = """
CREATE TABLE IF NOT EXISTS players (
    player_id               VARCHAR PRIMARY KEY,
    season_id               INTEGER NOT NULL REFERENCES seasons(season_id),
    full_name               VARCHAR NOT NULL,
    short_name              VARCHAR,
    age                     INTEGER,
    gender                  VARCHAR,
    race_ethnicity          VARCHAR,
    occupation              VARCHAR,
    hometown                VARCHAR,
    starting_tribe          VARCHAR,

    -- Game outcome
    placement               INTEGER,
    jury_votes_received     INTEGER DEFAULT 0,
    boot_episode            INTEGER,
    boot_day                INTEGER,
    exit_type               VARCHAR
        CHECK (exit_type IN (
            'voted_out', 'quit', 'medevac', 'eliminated_challenge',
            'fire_challenge', 'rock_draw', 'winner', 'runner_up', null
        )),

    -- Physical profile
    -- Used by challenge prediction model.
    -- Nullable — backfill from public sources where available.
    height_cm               FLOAT,
    weight_kg               FLOAT,
    -- Manually assigned composite tier (1=low, 2=mid, 3=high physical threat)
    -- based on build, stated athletic background, challenge performance
    physical_tier           INTEGER
        CHECK (physical_tier IN (1, 2, 3) OR physical_tier IS NULL),

    -- Returnee tracking
    is_returnee             BOOLEAN DEFAULT FALSE,
    previous_seasons        VARCHAR,        -- comma-separated season_ids

    -- Phase 4 enrichment
    archetype_label         VARCHAR,        -- e.g. "challenge_beast", "social", "UTR"
    mbti_type               VARCHAR         -- from survivoR castaways dataset
);
"""

CREATE_TRIBES = """
CREATE TABLE IF NOT EXISTS tribes (
    tribe_id                VARCHAR PRIMARY KEY,
    season_id               INTEGER NOT NULL REFERENCES seasons(season_id),
    tribe_name              VARCHAR NOT NULL,
    color_hex               VARCHAR,
    tribe_status            VARCHAR NOT NULL
        CHECK (tribe_status IN ('original', 'swapped', 'swapped2', 'merged')),
    episode_formed          INTEGER,        -- episode this configuration began
    episode_dissolved       INTEGER         -- episode this configuration ended (null if ongoing)
);
"""

CREATE_TRIBE_MEMBERSHIPS = """
CREATE TABLE IF NOT EXISTS tribe_memberships (
    -- One row per player per tribe configuration.
    -- Captures the full tribal movement history including swaps and absorptions.
    -- This is the authoritative source for "what tribe was player X on at episode N?"
    --
    -- To find a player's tribe at a given episode:
    --   WHERE player_id = :pid
    --     AND episode_joined <= :ep
    --     AND (episode_left IS NULL OR episode_left > :ep)
    id                      INTEGER PRIMARY KEY,
    player_id               VARCHAR NOT NULL REFERENCES players(player_id),
    tribe_id                VARCHAR NOT NULL REFERENCES tribes(tribe_id),
    season_id               INTEGER NOT NULL REFERENCES seasons(season_id),
    episode_joined          INTEGER NOT NULL,   -- episode this membership began
    episode_left            INTEGER,            -- episode this membership ended (null = still active)
    reason_joined           VARCHAR
        CHECK (reason_joined IN ('draft', 'swap', 'swap2', 'merge', 'absorbed', 'returnee', null)),
    UNIQUE (player_id, tribe_id, episode_joined)
);
"""

CREATE_EPISODES = """
CREATE TABLE IF NOT EXISTS episodes (
    episode_id              INTEGER PRIMARY KEY,
    season_id               INTEGER NOT NULL REFERENCES seasons(season_id),
    episode_num             INTEGER NOT NULL,
    episode_num_overall     INTEGER,
    title                   VARCHAR,
    air_date                DATE,
    runtime_mins            INTEGER,
    merge_occurred          BOOLEAN DEFAULT FALSE,
    swap_occurred           BOOLEAN DEFAULT FALSE,
    double_elimination      BOOLEAN DEFAULT FALSE,
    recap_episode           BOOLEAN DEFAULT FALSE,
    n_players_start         INTEGER,
    n_players_end           INTEGER,
    UNIQUE (season_id, episode_num)
);
"""

CREATE_TRIBAL_COUNCILS = """
CREATE TABLE IF NOT EXISTS tribal_councils (
    tc_id                   INTEGER PRIMARY KEY,
    episode_id              INTEGER NOT NULL REFERENCES episodes(episode_id),
    season_id               INTEGER NOT NULL REFERENCES seasons(season_id),
    tribe_id                VARCHAR REFERENCES tribes(tribe_id),
    tc_type                 VARCHAR NOT NULL
        CHECK (tc_type IN (
            'pre_merge', 'post_merge', 'split_losing', 'split_winning',
            'mergatory', 'final', 'redemption', 'fire_making'
        )),
    tc_order                INTEGER DEFAULT 1,
    n_players_attending     INTEGER,
    is_jury_phase           BOOLEAN DEFAULT FALSE
);
"""

CREATE_VOTES = """
CREATE TABLE IF NOT EXISTS votes (
    vote_id                 INTEGER PRIMARY KEY,
    tc_id                   INTEGER NOT NULL REFERENCES tribal_councils(tc_id),
    season_id               INTEGER NOT NULL REFERENCES seasons(season_id),
    episode_id              INTEGER NOT NULL REFERENCES episodes(episode_id),
    voter_player_id         VARCHAR REFERENCES players(player_id),
    voted_for_player_id     VARCHAR REFERENCES players(player_id),
    nullified               BOOLEAN DEFAULT FALSE,
    immunity_type           VARCHAR
        CHECK (immunity_type IN ('individual', 'hidden', 'team', 'shot_in_dark', null)),
    vote_event              VARCHAR,
    vote_event_outcome      VARCHAR,
    is_revote               BOOLEAN DEFAULT FALSE,
    vote_order              INTEGER DEFAULT 1,
    voted_out               BOOLEAN DEFAULT FALSE,
    -- Was this voter on the winning side of the vote?
    -- Computed at insert time by ingest pipeline.
    on_majority_side        BOOLEAN
);
"""

CREATE_CHALLENGES = """
CREATE TABLE IF NOT EXISTS challenges (
    challenge_id            INTEGER PRIMARY KEY,
    episode_id              INTEGER NOT NULL REFERENCES episodes(episode_id),
    season_id               INTEGER NOT NULL REFERENCES seasons(season_id),
    challenge_name          VARCHAR,
    challenge_type          VARCHAR NOT NULL
        CHECK (challenge_type IN ('reward', 'immunity', 'reward_immunity')),
    is_individual           BOOLEAN NOT NULL DEFAULT FALSE,
    -- Primary format classification for prediction model
    format                  VARCHAR
        CHECK (format IN (
            'physical', 'puzzle', 'endurance', 'balance',
            'knowledge', 'hybrid', 'social', 'unknown'
        )),
    -- Secondary format flags for multi-component challenges
    -- Most modern challenges are hybrid — these allow granular breakdown
    has_physical_component  BOOLEAN DEFAULT FALSE,
    has_puzzle_component    BOOLEAN DEFAULT FALSE,
    has_endurance_component BOOLEAN DEFAULT FALSE,
    has_balance_component   BOOLEAN DEFAULT FALSE,
    has_swimming_component  BOOLEAN DEFAULT FALSE,
    winner_tribe_id         VARCHAR REFERENCES tribes(tribe_id),
    winner_player_id        VARCHAR REFERENCES players(player_id),
    n_participants          INTEGER,
    -- Finishing positions for 3-tribe seasons (affects reward point tiers)
    second_place_tribe_id   VARCHAR REFERENCES tribes(tribe_id),
    third_place_tribe_id    VARCHAR REFERENCES tribes(tribe_id)
);
"""

CREATE_CHALLENGE_PARTICIPANTS = """
CREATE TABLE IF NOT EXISTS challenge_participants (
    id                      INTEGER PRIMARY KEY,
    challenge_id            INTEGER NOT NULL REFERENCES challenges(challenge_id),
    player_id               VARCHAR NOT NULL REFERENCES players(player_id),
    season_id               INTEGER NOT NULL REFERENCES seasons(season_id),
    tribe_id                VARCHAR REFERENCES tribes(tribe_id),
    participated            BOOLEAN DEFAULT TRUE,
    sat_out                 BOOLEAN DEFAULT FALSE,
    won                     BOOLEAN DEFAULT FALSE,
    placement               INTEGER,
    UNIQUE (challenge_id, player_id)
);
"""

CREATE_ADVANTAGES = """
CREATE TABLE IF NOT EXISTS advantages (
    advantage_id            VARCHAR PRIMARY KEY,
    season_id               INTEGER NOT NULL REFERENCES seasons(season_id),
    advantage_type          VARCHAR NOT NULL
        CHECK (advantage_type IN (
            'hidden_immunity_idol', 'extra_vote', 'steal_a_vote',
            'idol_nullifier', 'legacy_advantage', 'beware_advantage',
            'shot_in_dark', 'boomerang_idol', 'super_idol',
            'safety_without_power', 'knowledge_is_power',
            'lose_your_vote', 'other'
        )),
    -- Discovery
    found_by_player_id      VARCHAR REFERENCES players(player_id),
    found_episode           INTEGER,
    found_day               INTEGER,
    found_via_clue          BOOLEAN DEFAULT FALSE,
    -- Transfer chain (advantages can change hands)
    -- For complex transfers use advantage_movements table (Phase 4 extension)
    current_holder_player_id VARCHAR REFERENCES players(player_id),
    -- Play
    played_by_player_id     VARCHAR REFERENCES players(player_id),
    played_episode          INTEGER,
    played_at_tc_id         INTEGER REFERENCES tribal_councils(tc_id),
    played_for_player_id    VARCHAR REFERENCES players(player_id),
    votes_nullified         INTEGER DEFAULT 0,
    outcome                 VARCHAR
        CHECK (outcome IN (
            'successful', 'wasted', 'voted_out_holding',
            'transferred', 'expired', 'stolen', null
        ))
);
"""

CREATE_CONFESSIONALS = """
CREATE TABLE IF NOT EXISTS confessionals (
    id                      INTEGER PRIMARY KEY,
    player_id               VARCHAR NOT NULL REFERENCES players(player_id),
    episode_id              INTEGER NOT NULL REFERENCES episodes(episode_id),
    season_id               INTEGER NOT NULL REFERENCES seasons(season_id),
    confessional_count      INTEGER DEFAULT 0,
    screen_time_sec         FLOAT,
    -- survivoR normalized cumulative indices
    -- These control for TC attendance and allow cross-player comparison
    index_count             FLOAT,
    index_time              FLOAT,
    -- Expected values given game events (from survivoR)
    expected_count          FLOAT,
    expected_time           FLOAT,
    UNIQUE (player_id, episode_id)
);
"""

CREATE_CONFESSIONAL_TEXT = """
CREATE TABLE IF NOT EXISTS confessional_text (
    -- Phase 4 placeholder. Empty until NLP pipeline is built.
    -- One row per individual confessional (multiple per player per episode).
    -- Text sourced from fan transcription projects or CBS official transcripts.
    id                      INTEGER PRIMARY KEY,
    player_id               VARCHAR NOT NULL REFERENCES players(player_id),
    episode_id              INTEGER NOT NULL REFERENCES episodes(episode_id),
    season_id               INTEGER NOT NULL REFERENCES seasons(season_id),
    confessional_num        INTEGER,        -- order within episode for this player
    raw_text                TEXT,
    -- NLP outputs — populated by nlp/confessionals.py
    sentiment_score         FLOAT,          -- -1 (negative) to +1 (positive)
    agency_score            FLOAT,          -- passive to active framing
    loyalty_score           FLOAT,          -- expressed loyalty to named allies
    threat_mentions         VARCHAR,        -- comma-sep player_ids mentioned as threats
    ally_mentions           VARCHAR         -- comma-sep player_ids mentioned as allies
);
"""

# =============================================================================
# LAYER 1 — COMPUTED TABLES (rebuilt by features.py)
# =============================================================================

CREATE_ALLIANCE_INDEX = """
CREATE TABLE IF NOT EXISTS alliance_index (
    id                      INTEGER PRIMARY KEY,
    player_a_id             VARCHAR NOT NULL REFERENCES players(player_id),
    player_b_id             VARCHAR NOT NULL REFERENCES players(player_id),
    episode_id              INTEGER NOT NULL REFERENCES episodes(episode_id),
    season_id               INTEGER NOT NULL REFERENCES seasons(season_id),
    shared_tc_count         INTEGER DEFAULT 0,
    co_vote_count           INTEGER DEFAULT 0,
    -- Delta from previous episode (for detecting alliance shifts)
    co_vote_delta           INTEGER DEFAULT 0,
    alliance_score          FLOAT,
    alliance_score_delta    FLOAT,
    -- Were these players on the same tribe at this episode?
    same_tribe              BOOLEAN,
    CHECK (player_a_id < player_b_id),
    UNIQUE (player_a_id, player_b_id, episode_id)
);
"""

CREATE_PLAYER_SEASON_STATS = """
CREATE TABLE IF NOT EXISTS player_season_stats (
    -- Denormalized per-player per-season summary.
    -- Rebuilt by features.py after each episode.
    -- Primary input to historical survival and challenge models.
    -- One row per player per season, updated cumulatively.
    id                          INTEGER PRIMARY KEY,
    player_id                   VARCHAR NOT NULL REFERENCES players(player_id),
    season_id                   INTEGER NOT NULL REFERENCES seasons(season_id),
    -- Computed through episode_through (allows mid-season snapshots)
    episode_through             INTEGER NOT NULL,

    -- Survival
    episodes_survived           INTEGER DEFAULT 0,
    tc_appearances              INTEGER DEFAULT 0,
    times_at_risk               INTEGER DEFAULT 0,  -- attended TC without immunity

    -- Voting record
    votes_received_total        INTEGER DEFAULT 0,
    votes_received_nullified    INTEGER DEFAULT 0,
    votes_cast_majority         INTEGER DEFAULT 0,  -- voted with winning side
    votes_cast_total            INTEGER DEFAULT 0,
    majority_vote_pct           FLOAT,              -- votes_cast_majority / votes_cast_total

    -- Challenges
    team_challenges_won         INTEGER DEFAULT 0,
    team_challenges_played      INTEGER DEFAULT 0,
    team_challenges_sat_out     INTEGER DEFAULT 0,
    individual_challenges_won   INTEGER DEFAULT 0,
    individual_challenges_played INTEGER DEFAULT 0,
    individual_challenge_win_pct FLOAT,

    -- Advantages
    idols_found                 INTEGER DEFAULT 0,
    idols_played                INTEGER DEFAULT 0,
    idols_played_successfully   INTEGER DEFAULT 0,
    advantages_held             INTEGER DEFAULT 0,

    -- Network (from alliance_index)
    alliance_centrality         FLOAT,              -- eigenvector centrality at episode_through
    alliance_isolation_score    FLOAT,              -- 1 - (allies on same tribe / total allies)
    n_strong_allies             INTEGER,            -- alliance_score >= 0.6

    -- Confessional trajectory
    confessional_total          INTEGER DEFAULT 0,
    confessional_index_final    FLOAT,              -- cumulative normalized index
    confessional_trend          FLOAT,              -- slope of count over last 3 episodes

    -- Threat metrics
    threat_score                FLOAT,              -- composite: votes_received + challenge wins
    jury_similarity_index       FLOAT,              -- Jaccard vs jury members (post-merge only)

    UNIQUE (player_id, season_id, episode_through)
);
"""

# =============================================================================
# LAYER 2 — FANTASY LEAGUE APPLICATION
# =============================================================================

CREATE_LEAGUE_PLAYERS = """
CREATE TABLE IF NOT EXISTS league_players (
    league_player_id        INTEGER PRIMARY KEY,
    name                    VARCHAR NOT NULL UNIQUE,
    email                   VARCHAR
);
"""

CREATE_LEAGUE_ROSTERS = """
CREATE TABLE IF NOT EXISTS league_rosters (
    id                      INTEGER PRIMARY KEY,
    league_player_id        INTEGER NOT NULL REFERENCES league_players(league_player_id),
    survivor_player_id      VARCHAR NOT NULL REFERENCES players(player_id),
    episode_id              INTEGER NOT NULL REFERENCES episodes(episode_id),
    season_id               INTEGER NOT NULL REFERENCES seasons(season_id),
    is_active               BOOLEAN NOT NULL,
    UNIQUE (league_player_id, survivor_player_id, episode_id)
);
"""

CREATE_EPISODE_SCORES = """
CREATE TABLE IF NOT EXISTS episode_scores (
    id                      INTEGER PRIMARY KEY,
    league_player_id        INTEGER NOT NULL REFERENCES league_players(league_player_id),
    episode_id              INTEGER NOT NULL REFERENCES episodes(episode_id),
    season_id               INTEGER NOT NULL REFERENCES seasons(season_id),
    survivor_player_id      VARCHAR NOT NULL REFERENCES players(player_id),
    event_type              VARCHAR NOT NULL,
    pts                     INTEGER NOT NULL,
    event_description       VARCHAR
);
"""

CREATE_LEAGUE_STANDINGS = """
CREATE TABLE IF NOT EXISTS league_standings (
    id                      INTEGER PRIMARY KEY,
    league_player_id        INTEGER NOT NULL REFERENCES league_players(league_player_id),
    episode_id              INTEGER NOT NULL REFERENCES episodes(episode_id),
    season_id               INTEGER NOT NULL REFERENCES seasons(season_id),
    episode_pts             INTEGER DEFAULT 0,
    cumulative_pts          INTEGER DEFAULT 0,
    rank                    INTEGER,
    UNIQUE (league_player_id, episode_id)
);
"""

# =============================================================================
# INDEXES
# =============================================================================
# Every FK, every WHERE column, every JOIN column gets an index.
# Composite indexes for the most common multi-column join patterns.

INDEXES = [
    # seasons
    "CREATE INDEX IF NOT EXISTS idx_seasons_num ON seasons(season_num)",
    "CREATE INDEX IF NOT EXISTS idx_seasons_era ON seasons(era)",

    # players
    "CREATE INDEX IF NOT EXISTS idx_players_season ON players(season_id)",
    "CREATE INDEX IF NOT EXISTS idx_players_name ON players(full_name)",
    "CREATE INDEX IF NOT EXISTS idx_players_boot ON players(boot_episode)",
    "CREATE INDEX IF NOT EXISTS idx_players_placement ON players(placement)",
    "CREATE INDEX IF NOT EXISTS idx_players_season_placement ON players(season_id, placement)",

    # tribe_memberships — critical for "player's tribe at episode N"
    "CREATE INDEX IF NOT EXISTS idx_tm_player ON tribe_memberships(player_id)",
    "CREATE INDEX IF NOT EXISTS idx_tm_tribe ON tribe_memberships(tribe_id)",
    "CREATE INDEX IF NOT EXISTS idx_tm_season ON tribe_memberships(season_id)",
    "CREATE INDEX IF NOT EXISTS idx_tm_player_episode ON tribe_memberships(player_id, episode_joined, episode_left)",
    "CREATE INDEX IF NOT EXISTS idx_tm_season_episode ON tribe_memberships(season_id, episode_joined)",

    # tribes
    "CREATE INDEX IF NOT EXISTS idx_tribes_season ON tribes(season_id)",
    "CREATE INDEX IF NOT EXISTS idx_tribes_status ON tribes(tribe_status)",

    # episodes
    "CREATE INDEX IF NOT EXISTS idx_episodes_season ON episodes(season_id)",
    "CREATE INDEX IF NOT EXISTS idx_episodes_air_date ON episodes(air_date)",
    "CREATE INDEX IF NOT EXISTS idx_episodes_season_num ON episodes(season_id, episode_num)",
    "CREATE INDEX IF NOT EXISTS idx_episodes_merge ON episodes(season_id, merge_occurred)",

    # tribal_councils
    "CREATE INDEX IF NOT EXISTS idx_tc_episode ON tribal_councils(episode_id)",
    "CREATE INDEX IF NOT EXISTS idx_tc_season ON tribal_councils(season_id)",
    "CREATE INDEX IF NOT EXISTS idx_tc_tribe ON tribal_councils(tribe_id)",
    "CREATE INDEX IF NOT EXISTS idx_tc_type ON tribal_councils(tc_type)",
    "CREATE INDEX IF NOT EXISTS idx_tc_season_type ON tribal_councils(season_id, tc_type)",

    # votes — highest query volume table
    "CREATE INDEX IF NOT EXISTS idx_votes_tc ON votes(tc_id)",
    "CREATE INDEX IF NOT EXISTS idx_votes_season ON votes(season_id)",
    "CREATE INDEX IF NOT EXISTS idx_votes_episode ON votes(episode_id)",
    "CREATE INDEX IF NOT EXISTS idx_votes_voter ON votes(voter_player_id)",
    "CREATE INDEX IF NOT EXISTS idx_votes_voted_for ON votes(voted_for_player_id)",
    "CREATE INDEX IF NOT EXISTS idx_votes_nullified ON votes(nullified)",
    "CREATE INDEX IF NOT EXISTS idx_votes_voted_out ON votes(voted_out)",
    # Composite: alliance index computation joins on both player columns
    "CREATE INDEX IF NOT EXISTS idx_votes_tc_voter ON votes(tc_id, voter_player_id)",
    "CREATE INDEX IF NOT EXISTS idx_votes_season_voter ON votes(season_id, voter_player_id)",
    # Majority vote percentage computation
    "CREATE INDEX IF NOT EXISTS idx_votes_voter_majority ON votes(voter_player_id, on_majority_side)",

    # challenges
    "CREATE INDEX IF NOT EXISTS idx_challenges_episode ON challenges(episode_id)",
    "CREATE INDEX IF NOT EXISTS idx_challenges_season ON challenges(season_id)",
    "CREATE INDEX IF NOT EXISTS idx_challenges_type ON challenges(challenge_type)",
    "CREATE INDEX IF NOT EXISTS idx_challenges_format ON challenges(format)",
    "CREATE INDEX IF NOT EXISTS idx_challenges_individual ON challenges(is_individual)",
    "CREATE INDEX IF NOT EXISTS idx_challenges_season_format ON challenges(season_id, format, is_individual)",

    # challenge_participants
    "CREATE INDEX IF NOT EXISTS idx_cp_challenge ON challenge_participants(challenge_id)",
    "CREATE INDEX IF NOT EXISTS idx_cp_player ON challenge_participants(player_id)",
    "CREATE INDEX IF NOT EXISTS idx_cp_season ON challenge_participants(season_id)",
    "CREATE INDEX IF NOT EXISTS idx_cp_won ON challenge_participants(player_id, won)",
    "CREATE INDEX IF NOT EXISTS idx_cp_sat_out ON challenge_participants(player_id, sat_out)",
    # Win rate by format (joins to challenges)
    "CREATE INDEX IF NOT EXISTS idx_cp_player_challenge ON challenge_participants(player_id, challenge_id)",

    # advantages
    "CREATE INDEX IF NOT EXISTS idx_adv_season ON advantages(season_id)",
    "CREATE INDEX IF NOT EXISTS idx_adv_type ON advantages(advantage_type)",
    "CREATE INDEX IF NOT EXISTS idx_adv_found_by ON advantages(found_by_player_id)",
    "CREATE INDEX IF NOT EXISTS idx_adv_holder ON advantages(current_holder_player_id)",
    "CREATE INDEX IF NOT EXISTS idx_adv_played_by ON advantages(played_by_player_id)",
    "CREATE INDEX IF NOT EXISTS idx_adv_played_for ON advantages(played_for_player_id)",
    "CREATE INDEX IF NOT EXISTS idx_adv_outcome ON advantages(outcome)",

    # confessionals
    "CREATE INDEX IF NOT EXISTS idx_conf_player ON confessionals(player_id)",
    "CREATE INDEX IF NOT EXISTS idx_conf_episode ON confessionals(episode_id)",
    "CREATE INDEX IF NOT EXISTS idx_conf_season ON confessionals(season_id)",
    "CREATE INDEX IF NOT EXISTS idx_conf_player_season ON confessionals(player_id, season_id)",

    # confessional_text (Phase 4 — sparse, but index player/episode for joins)
    "CREATE INDEX IF NOT EXISTS idx_ct_player ON confessional_text(player_id)",
    "CREATE INDEX IF NOT EXISTS idx_ct_episode ON confessional_text(episode_id)",
    "CREATE INDEX IF NOT EXISTS idx_ct_season ON confessional_text(season_id)",

    # alliance_index — heavy join target for network analysis
    "CREATE INDEX IF NOT EXISTS idx_ai_player_a ON alliance_index(player_a_id)",
    "CREATE INDEX IF NOT EXISTS idx_ai_player_b ON alliance_index(player_b_id)",
    "CREATE INDEX IF NOT EXISTS idx_ai_episode ON alliance_index(episode_id)",
    "CREATE INDEX IF NOT EXISTS idx_ai_season ON alliance_index(season_id)",
    "CREATE INDEX IF NOT EXISTS idx_ai_score ON alliance_index(alliance_score)",
    # Full adjacency matrix lookup at a given episode
    "CREATE INDEX IF NOT EXISTS idx_ai_season_episode ON alliance_index(season_id, episode_id)",
    # Strong ally count
    "CREATE INDEX IF NOT EXISTS idx_ai_player_a_score ON alliance_index(player_a_id, alliance_score)",
    "CREATE INDEX IF NOT EXISTS idx_ai_player_b_score ON alliance_index(player_b_id, alliance_score)",

    # player_season_stats
    "CREATE INDEX IF NOT EXISTS idx_pss_player ON player_season_stats(player_id)",
    "CREATE INDEX IF NOT EXISTS idx_pss_season ON player_season_stats(season_id)",
    "CREATE INDEX IF NOT EXISTS idx_pss_episode ON player_season_stats(episode_through)",
    "CREATE INDEX IF NOT EXISTS idx_pss_season_episode ON player_season_stats(season_id, episode_through)",
    "CREATE INDEX IF NOT EXISTS idx_pss_threat ON player_season_stats(threat_score)",
    "CREATE INDEX IF NOT EXISTS idx_pss_centrality ON player_season_stats(alliance_centrality)",

    # Layer 2
    "CREATE INDEX IF NOT EXISTS idx_lr_league_player ON league_rosters(league_player_id)",
    "CREATE INDEX IF NOT EXISTS idx_lr_survivor ON league_rosters(survivor_player_id)",
    "CREATE INDEX IF NOT EXISTS idx_lr_episode ON league_rosters(episode_id)",
    "CREATE INDEX IF NOT EXISTS idx_lr_season ON league_rosters(season_id)",
    "CREATE INDEX IF NOT EXISTS idx_lr_active ON league_rosters(league_player_id, is_active, episode_id)",

    "CREATE INDEX IF NOT EXISTS idx_es_league_player ON episode_scores(league_player_id)",
    "CREATE INDEX IF NOT EXISTS idx_es_episode ON episode_scores(episode_id)",
    "CREATE INDEX IF NOT EXISTS idx_es_season ON episode_scores(season_id)",
    "CREATE INDEX IF NOT EXISTS idx_es_survivor ON episode_scores(survivor_player_id)",
    "CREATE INDEX IF NOT EXISTS idx_es_event_type ON episode_scores(event_type)",
    # Dashboard query: all scores for one league player, one episode
    "CREATE INDEX IF NOT EXISTS idx_es_lp_episode ON episode_scores(league_player_id, episode_id)",

    "CREATE INDEX IF NOT EXISTS idx_ls_league_player ON league_standings(league_player_id)",
    "CREATE INDEX IF NOT EXISTS idx_ls_episode ON league_standings(episode_id)",
    "CREATE INDEX IF NOT EXISTS idx_ls_season ON league_standings(season_id)",
    "CREATE INDEX IF NOT EXISTS idx_ls_rank ON league_standings(episode_id, rank)",
]

# =============================================================================
# TABLE REGISTRY — ordered by dependency
# =============================================================================

LAYER_1_CORE_TABLES: list[str] = [
    CREATE_SEASONS,
    CREATE_PLAYERS,
    CREATE_TRIBES,
    CREATE_TRIBE_MEMBERSHIPS,
    CREATE_EPISODES,
    CREATE_TRIBAL_COUNCILS,
    CREATE_VOTES,
    CREATE_CHALLENGES,
    CREATE_CHALLENGE_PARTICIPANTS,
    CREATE_ADVANTAGES,
    CREATE_CONFESSIONALS,
    CREATE_CONFESSIONAL_TEXT,
]

LAYER_1_COMPUTED_TABLES: list[str] = [
    CREATE_ALLIANCE_INDEX,
    CREATE_PLAYER_SEASON_STATS,
]

LAYER_2_TABLES: list[str] = [
    CREATE_LEAGUE_PLAYERS,
    CREATE_LEAGUE_ROSTERS,
    CREATE_EPISODE_SCORES,
    CREATE_LEAGUE_STANDINGS,
]

ALL_TABLES = LAYER_1_CORE_TABLES + LAYER_1_COMPUTED_TABLES + LAYER_2_TABLES

DROP_ORDER = [
    "league_standings", "episode_scores", "league_rosters", "league_players",
    "player_season_stats", "alliance_index",
    "confessional_text", "confessionals", "advantages",
    "challenge_participants", "challenges",
    "votes", "tribal_councils", "episodes",
    "tribe_memberships", "tribes", "players", "seasons",
]

# =============================================================================
# PUBLIC API
# =============================================================================

def create_all_tables(conn=None) -> None:
    """Create all tables and indexes. Idempotent."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()

    n_l1_core     = len(LAYER_1_CORE_TABLES)
    n_l1_computed = len(LAYER_1_COMPUTED_TABLES)
    n_l1_extended = len(LAYER_1_EXTENDED_TABLES)
    n_l2          = len(LAYER_2_TABLES)
    n_indexes     = len(INDEXES) + len(EXTENDED_INDEXES)

    print(f"Creating Layer 1 core tables ({n_l1_core})...")
    for ddl in LAYER_1_CORE_TABLES:
        conn.execute(ddl)

    print(f"Creating Layer 1 computed tables ({n_l1_computed})...")
    for ddl in LAYER_1_COMPUTED_TABLES:
        conn.execute(ddl)

    print(f"Creating Layer 1 extended story tables ({n_l1_extended})...")
    for ddl in LAYER_1_EXTENDED_TABLES:
        conn.execute(ddl)

    print(f"Creating Layer 2 tables ({n_l2})...")
    for ddl in LAYER_2_TABLES:
        conn.execute(ddl)

    print(f"Creating indexes ({n_indexes})...")
    for idx in INDEXES + EXTENDED_INDEXES:
        conn.execute(idx)

    total = n_l1_core + n_l1_computed + n_l1_extended + n_l2
    print(f"Schema complete: {total} tables, {n_indexes} indexes.")

    if close_after:
        conn.close()


def drop_all_tables(conn=None) -> None:
    """Drop all tables in reverse dependency order. Destructive."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()

    for table in DROP_ORDER:
        conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        print(f"  Dropped: {table}")

    if close_after:
        conn.close()


def get_table_info(conn=None) -> None:
    """Print row counts for all tables. Useful for pipeline validation."""
    close_after = conn is None
    if conn is None:
        conn = get_connection()

    all_table_names = [
        # Layer 1 core
        "seasons", "players", "tribes", "tribe_memberships", "episodes",
        "tribal_councils", "votes", "challenges", "challenge_participants",
        "advantages", "confessionals", "confessional_text",
        # Layer 1 computed
        "alliance_index", "player_season_stats", "player_trajectories",
        # Layer 1 extended
        "player_pregame_profiles", "player_postseason_statements",
        "player_external_assessments", "edit_classifications",
        "social_media_posts", "player_archetypes",
        "visualization_metadata", "scrape_log",
        # Layer 2
        "league_players", "league_rosters", "episode_scores", "league_standings",
    ]

    print(f"\n{'Table':<30} {'Rows':>10}")
    print("-" * 42)
    for table in all_table_names:
        try:
            result = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            count = result[0] if result else 0
        except Exception:
            count = "N/A"
        print(f"{table:<30} {str(count):>10}")

    if close_after:
        conn.close()


if __name__ == "__main__":
    create_all_tables()
    get_table_info()

# =============================================================================
# LAYER 1 — EXTENDED STORY TABLES
# Added to support post-season data, trajectory analysis,
# external assessments, and visualization metadata.
# =============================================================================

CREATE_PLAYER_PREGAME_PROFILES = """
CREATE TABLE IF NOT EXISTS player_pregame_profiles (
    -- Pre-game identity and stated strategy.
    -- Sourced from cast videos, press interviews, application materials.
    id                          INTEGER PRIMARY KEY,
    player_id                   VARCHAR NOT NULL REFERENCES players(player_id),
    season_id                   INTEGER NOT NULL REFERENCES seasons(season_id),

    -- Self-identification
    stated_strategy             TEXT,
    survivor_experience_level   INTEGER CHECK (survivor_experience_level BETWEEN 1 AND 5),
    self_described_archetype    VARCHAR,
    stated_win_probability      FLOAT,      -- player's own estimate (rare but exists)

    -- Pregame relationships (players who know each other before game)
    known_players               VARCHAR,    -- comma-sep player_ids
    relationship_type           VARCHAR,    -- "friends" / "family" / "fans" / null

    -- Source
    source_url                  VARCHAR,
    source_type                 VARCHAR     -- "cast_video" / "press_interview" / "application"
);
"""

CREATE_PLAYER_POSTSEASON_STATEMENTS = """
CREATE TABLE IF NOT EXISTS player_postseason_statements (
    -- Post-season revelations from interviews, podcasts, social media, AMAs.
    -- The "dark matter" layer — things that happened but weren't shown.
    -- Raw text goes here; NLP outputs are populated by nlp/confessionals.py.
    id                          INTEGER PRIMARY KEY,
    player_id                   VARCHAR NOT NULL REFERENCES players(player_id),
    season_id                   INTEGER NOT NULL REFERENCES seasons(season_id),

    -- Source metadata
    source_type                 VARCHAR NOT NULL
        CHECK (source_type IN (
            'podcast', 'reddit_ama', 'twitter', 'instagram',
            'interview', 'youtube', 'ponderosa', 'jury_speaks', 'other'
        )),
    source_name                 VARCHAR,    -- e.g. "Rob Has A Podcast"
    source_url                  VARCHAR,
    published_date              DATE,

    -- Content
    raw_text                    TEXT,
    statement_type              VARCHAR
        CHECK (statement_type IN (
            'alliance_reveal', 'vote_explanation', 'relationship_reveal',
            'strategy_explain', 'self_assessment', 'other_player_assessment',
            'production_critique', 'game_regret', 'other'
        )),

    -- References to other players discussed
    references_player_ids       VARCHAR,    -- comma-sep player_ids

    -- NLP outputs (populated by pipeline)
    sentiment_score             FLOAT,
    key_claims                  TEXT,       -- JSON array of extracted claims
    verified                    BOOLEAN DEFAULT FALSE,  -- corroborated by another source
    verification_source_id      INTEGER     -- FK to another statement that corroborates
);
"""

CREATE_PLAYER_EXTERNAL_ASSESSMENTS = """
CREATE TABLE IF NOT EXISTS player_external_assessments (
    -- How players assessed each other (pregame rankings, jury comments, etc.)
    -- Also includes journalist/fan expert assessments.
    id                          INTEGER PRIMARY KEY,
    assessed_player_id          VARCHAR NOT NULL REFERENCES players(player_id),
    assessing_player_id         VARCHAR REFERENCES players(player_id),   -- null if fan/journalist
    season_id                   INTEGER NOT NULL REFERENCES seasons(season_id),
    assessment_type             VARCHAR NOT NULL
        CHECK (assessment_type IN (
            'pregame_rank', 'pregame_threat', 'jury_comment',
            'jury_final_vote_reason', 'postseason_rank',
            'fan_assessment', 'journalist_assessment'
        )),
    numeric_score               FLOAT,      -- rank or rating where applicable
    raw_text                    TEXT,
    source_url                  VARCHAR,
    published_date              DATE
);
"""

CREATE_EDIT_CLASSIFICATIONS = """
CREATE TABLE IF NOT EXISTS edit_classifications (
    -- Per-player per-episode edit type classification.
    -- Populated by manual labeling (method='manual') or
    -- the Phase 4 edit classifier (method='classifier').
    id                          INTEGER PRIMARY KEY,
    player_id                   VARCHAR NOT NULL REFERENCES players(player_id),
    episode_id                  INTEGER NOT NULL REFERENCES episodes(episode_id),
    season_id                   INTEGER NOT NULL REFERENCES seasons(season_id),
    edit_type                   VARCHAR
        CHECK (edit_type IN (
            'winner', 'contender', 'narrator', 'villain',
            'complex', 'UTR', 'MORP', 'premerge_boot', 'invisible'
        )),
    -- UTR  = Under the Radar
    -- MORP = Middle of the Road Player
    confidence                  FLOAT,          -- 0-1, model confidence or human certainty
    method                      VARCHAR
        CHECK (method IN ('manual', 'classifier', 'hybrid')),
    notes                       TEXT,
    UNIQUE (player_id, episode_id)
);
"""

CREATE_SOCIAL_MEDIA_POSTS = """
CREATE TABLE IF NOT EXISTS social_media_posts (
    -- Raw scraped social media content from player accounts.
    -- Populated by scraper/ modules. Never manually edited.
    -- NLP outputs appended by nlp/confessionals.py.
    id                          INTEGER PRIMARY KEY,
    player_id                   VARCHAR NOT NULL REFERENCES players(player_id),
    season_id                   INTEGER NOT NULL REFERENCES seasons(season_id),
    platform                    VARCHAR NOT NULL
        CHECK (platform IN ('twitter', 'instagram', 'tiktok', 'reddit', 'youtube', 'other')),
    post_url                    VARCHAR UNIQUE,
    post_date                   TIMESTAMP,
    raw_text                    TEXT,
    -- Engagement (nullable — not always scrapeable)
    likes                       INTEGER,
    comments                    INTEGER,
    shares                      INTEGER,
    -- NLP outputs
    sentiment_score             FLOAT,
    references_player_ids       VARCHAR,    -- comma-sep player_ids mentioned
    topics                      VARCHAR,    -- comma-sep topic tags
    -- Context
    is_during_airing            BOOLEAN,    -- posted while season was airing
    episode_context             INTEGER     -- episode_num if temporally linked
);
"""

CREATE_PLAYER_ARCHETYPES = """
CREATE TABLE IF NOT EXISTS player_archetypes (
    -- Structured archetype classification per player per season.
    -- More granular than the single archetype_label on players table.
    -- Rebuilt by Phase 4 classifier or populated manually.
    id                          INTEGER PRIMARY KEY,
    player_id                   VARCHAR NOT NULL REFERENCES players(player_id),
    season_id                   INTEGER NOT NULL REFERENCES seasons(season_id),

    -- Primary classification axes
    primary_archetype           VARCHAR
        CHECK (primary_archetype IN (
            'challenge_beast', 'social_player', 'strategist',
            'narrator', 'villain', 'goat', 'UTR', 'wildcard', 'other'
        )),
    secondary_archetype         VARCHAR,

    -- Sub-profiles
    challenge_profile           VARCHAR
        CHECK (challenge_profile IN (
            'physical_dominant', 'puzzle_specialist', 'endurance_specialist',
            'balanced', 'weak', 'unknown'
        )),
    social_profile              VARCHAR
        CHECK (social_profile IN (
            'alliance_builder', 'free_agent', 'loyal_soldier',
            'narrator', 'UTR', 'abrasive', 'unknown'
        )),
    strategic_profile           VARCHAR
        CHECK (strategic_profile IN (
            'aggressive', 'conservative', 'reactive', 'adaptive', 'unknown'
        )),

    -- Confidence and method
    confidence                  FLOAT,
    method                      VARCHAR CHECK (method IN ('manual', 'classifier', 'hybrid')),
    UNIQUE (player_id, season_id)
);
"""

CREATE_PLAYER_TRAJECTORIES = """
CREATE TABLE IF NOT EXISTS player_trajectories (
    -- Pre-computed trajectory state vector for each player at each episode.
    -- One row per player per episode — the full multidimensional state
    -- that defines where a player is in their arc at that moment.
    -- Built by features.py, used for sequence similarity / DTW analysis.
    -- Enables "find historical players who were in a similar position."
    id                          INTEGER PRIMARY KEY,
    player_id                   VARCHAR NOT NULL REFERENCES players(player_id),
    season_id                   INTEGER NOT NULL REFERENCES seasons(season_id),
    episode_id                  INTEGER NOT NULL REFERENCES episodes(episode_id),
    episode_num                 INTEGER NOT NULL,

    -- Game position
    merge_status                VARCHAR,    -- "pre_merge" / "post_merge"
    tribe_majority              BOOLEAN,    -- in majority on current tribe?
    days_from_merge             INTEGER,    -- negative = pre-merge, positive = post

    -- Threat state
    cumulative_votes_received   INTEGER,
    threat_percentile           FLOAT,      -- vs. other active players this episode
    idol_possessed              BOOLEAN,
    votes_lost_cumulative       INTEGER,

    -- Social capital
    alliance_centrality         FLOAT,
    n_strong_allies             INTEGER,
    cross_tribe_bonds           INTEGER,    -- allies on other tribes (post-swap)
    isolation_score             FLOAT,

    -- Challenge state
    individual_immunity_streak  INTEGER,    -- consecutive individual immunity wins
    team_challenge_win_rate     FLOAT,      -- rolling, last 3 episodes

    -- Narrative position
    confessional_trajectory     FLOAT,      -- slope of confessionals over last 3 eps
    edit_type_current           VARCHAR,    -- from edit_classifications

    -- Outcome (populated retroactively for historical data)
    survived_this_episode       BOOLEAN,
    episodes_remaining          INTEGER,    -- how many more they lasted

    UNIQUE (player_id, episode_id)
);
"""

CREATE_VISUALIZATION_METADATA = """
CREATE TABLE IF NOT EXISTS visualization_metadata (
    -- Pre-computed layout hints for the network visualization.
    -- Stores island positions, player thumbnail URLs, and
    -- graph layout coordinates so the frontend doesn't recompute them.
    -- Rebuilt by viz/ pipeline after each episode.
    id                          INTEGER PRIMARY KEY,
    episode_id                  INTEGER NOT NULL REFERENCES episodes(episode_id),
    season_id                   INTEGER NOT NULL REFERENCES seasons(season_id),
    player_id                   VARCHAR NOT NULL REFERENCES players(player_id),

    -- Island position (tribe spatial layout)
    tribe_id                    VARCHAR REFERENCES tribes(tribe_id),
    island_x                    FLOAT,      -- normalized 0-1 canvas position
    island_y                    FLOAT,
    -- Player position within island
    node_x                      FLOAT,
    node_y                      FLOAT,

    -- Visual properties
    thumbnail_url               VARCHAR,    -- CBS cast photo or similar
    node_color                  VARCHAR,    -- hex, derived from tribe color
    node_opacity                FLOAT DEFAULT 1.0,  -- fades on elimination
    is_eliminated               BOOLEAN DEFAULT FALSE,

    -- Storytelling flags — moments worth surfacing in UI/TikTok
    is_anomaly                  BOOLEAN DEFAULT FALSE,  -- something unusual happened
    anomaly_description         VARCHAR,    -- "received 11th vote, still survived"
    story_beat_type             VARCHAR
        CHECK (story_beat_type IN (
            'elimination', 'idol_play', 'blindside', 'swap',
            'merge', 'immunity_run', 'alliance_flip', 'record', null
        )),
    story_beat_description      VARCHAR,    -- human-readable, used in TikTok captions

    UNIQUE (player_id, episode_id)
);
"""

CREATE_SCRAPE_LOG = """
CREATE TABLE IF NOT EXISTS scrape_log (
    -- Audit trail for all web scraping activity.
    -- Enables incremental scraping (don't re-scrape what we have),
    -- debugging, and rate limit tracking.
    id                          INTEGER PRIMARY KEY,
    scrape_timestamp            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_type                 VARCHAR NOT NULL,
    source_url                  VARCHAR,
    player_id                   VARCHAR REFERENCES players(player_id),
    season_id                   INTEGER REFERENCES seasons(season_id),
    status                      VARCHAR
        CHECK (status IN ('success', 'failed', 'rate_limited', 'not_found', 'skipped')),
    rows_written                INTEGER DEFAULT 0,
    error_message               VARCHAR,
    scraper_version             VARCHAR     -- track which version of scraper ran
);
"""

# ── Extended indexes ───────────────────────────────────────────────────────────

EXTENDED_INDEXES = [
    # player_pregame_profiles
    "CREATE INDEX IF NOT EXISTS idx_pgp_player ON player_pregame_profiles(player_id)",
    "CREATE INDEX IF NOT EXISTS idx_pgp_season ON player_pregame_profiles(season_id)",

    # player_postseason_statements
    "CREATE INDEX IF NOT EXISTS idx_pss2_player ON player_postseason_statements(player_id)",
    "CREATE INDEX IF NOT EXISTS idx_pss2_season ON player_postseason_statements(season_id)",
    "CREATE INDEX IF NOT EXISTS idx_pss2_type ON player_postseason_statements(statement_type)",
    "CREATE INDEX IF NOT EXISTS idx_pss2_source ON player_postseason_statements(source_type)",
    "CREATE INDEX IF NOT EXISTS idx_pss2_verified ON player_postseason_statements(verified)",

    # player_external_assessments
    "CREATE INDEX IF NOT EXISTS idx_pea_assessed ON player_external_assessments(assessed_player_id)",
    "CREATE INDEX IF NOT EXISTS idx_pea_assessing ON player_external_assessments(assessing_player_id)",
    "CREATE INDEX IF NOT EXISTS idx_pea_type ON player_external_assessments(assessment_type)",
    "CREATE INDEX IF NOT EXISTS idx_pea_season ON player_external_assessments(season_id)",

    # edit_classifications
    "CREATE INDEX IF NOT EXISTS idx_ec_player ON edit_classifications(player_id)",
    "CREATE INDEX IF NOT EXISTS idx_ec_episode ON edit_classifications(episode_id)",
    "CREATE INDEX IF NOT EXISTS idx_ec_season ON edit_classifications(season_id)",
    "CREATE INDEX IF NOT EXISTS idx_ec_type ON edit_classifications(edit_type)",
    "CREATE INDEX IF NOT EXISTS idx_ec_player_season ON edit_classifications(player_id, season_id)",

    # social_media_posts
    "CREATE INDEX IF NOT EXISTS idx_smp_player ON social_media_posts(player_id)",
    "CREATE INDEX IF NOT EXISTS idx_smp_platform ON social_media_posts(platform)",
    "CREATE INDEX IF NOT EXISTS idx_smp_date ON social_media_posts(post_date)",
    "CREATE INDEX IF NOT EXISTS idx_smp_airing ON social_media_posts(is_during_airing)",

    # player_archetypes
    "CREATE INDEX IF NOT EXISTS idx_pa_player ON player_archetypes(player_id)",
    "CREATE INDEX IF NOT EXISTS idx_pa_season ON player_archetypes(season_id)",
    "CREATE INDEX IF NOT EXISTS idx_pa_primary ON player_archetypes(primary_archetype)",

    # player_trajectories
    "CREATE INDEX IF NOT EXISTS idx_pt_player ON player_trajectories(player_id)",
    "CREATE INDEX IF NOT EXISTS idx_pt_season ON player_trajectories(season_id)",
    "CREATE INDEX IF NOT EXISTS idx_pt_episode ON player_trajectories(episode_id)",
    "CREATE INDEX IF NOT EXISTS idx_pt_player_episode ON player_trajectories(player_id, episode_id)",
    "CREATE INDEX IF NOT EXISTS idx_pt_threat ON player_trajectories(threat_percentile)",
    "CREATE INDEX IF NOT EXISTS idx_pt_centrality ON player_trajectories(alliance_centrality)",
    "CREATE INDEX IF NOT EXISTS idx_pt_survived ON player_trajectories(survived_this_episode)",
    # Trajectory similarity queries — need fast scans on state vectors
    "CREATE INDEX IF NOT EXISTS idx_pt_merge_status ON player_trajectories(merge_status, episode_num)",

    # visualization_metadata
    "CREATE INDEX IF NOT EXISTS idx_vm_episode ON visualization_metadata(episode_id)",
    "CREATE INDEX IF NOT EXISTS idx_vm_player ON visualization_metadata(player_id)",
    "CREATE INDEX IF NOT EXISTS idx_vm_season ON visualization_metadata(season_id)",
    "CREATE INDEX IF NOT EXISTS idx_vm_anomaly ON visualization_metadata(is_anomaly)",
    "CREATE INDEX IF NOT EXISTS idx_vm_story_beat ON visualization_metadata(story_beat_type)",

    # scrape_log
    "CREATE INDEX IF NOT EXISTS idx_sl_player ON scrape_log(player_id)",
    "CREATE INDEX IF NOT EXISTS idx_sl_url ON scrape_log(source_url)",
    "CREATE INDEX IF NOT EXISTS idx_sl_status ON scrape_log(status)",
    "CREATE INDEX IF NOT EXISTS idx_sl_timestamp ON scrape_log(scrape_timestamp)",
]

# Append extended tables and indexes to registries
LAYER_1_EXTENDED_TABLES: list[str] = [
    CREATE_PLAYER_PREGAME_PROFILES,
    CREATE_PLAYER_POSTSEASON_STATEMENTS,
    CREATE_PLAYER_EXTERNAL_ASSESSMENTS,
    CREATE_EDIT_CLASSIFICATIONS,
    CREATE_SOCIAL_MEDIA_POSTS,
    CREATE_PLAYER_ARCHETYPES,
    CREATE_PLAYER_TRAJECTORIES,
    CREATE_VISUALIZATION_METADATA,
    CREATE_SCRAPE_LOG,
]

# Extend the drop order
DROP_ORDER.extend([
    "scrape_log",
    "visualization_metadata",
    "player_trajectories",
    "player_archetypes",
    "social_media_posts",
    "edit_classifications",
    "player_external_assessments",
    "player_postseason_statements",
    "player_pregame_profiles",
])

# =============================================================================
# COLLABORATIVE DATA LAYER — submission queue
# =============================================================================

CREATE_SUBMISSION_QUEUE = """
CREATE TABLE IF NOT EXISTS submission_queue (
    -- Staging table for all external data contributions.
    -- Nothing external ever writes directly to Layer 1.
    -- All submissions sit here until reviewed and approved.
    id                      INTEGER PRIMARY KEY,
    submitted_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    submitted_by            VARCHAR,
    submission_type         VARCHAR NOT NULL
        CHECK (submission_type IN (
            'episode_event', 'external_source', 'correction',
            'social_media', 'transcript', 'pregame_profile'
        )),
    target_player_id        VARCHAR REFERENCES players(player_id),
    target_season_id        INTEGER REFERENCES seasons(season_id),
    target_episode_id       INTEGER REFERENCES episodes(episode_id),
    -- Raw payload as submitted (JSON blob)
    raw_payload             TEXT,
    -- Structured claims extracted by Claude pipeline (Phase 4)
    extracted_claims        TEXT,
    status                  VARCHAR DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'needs_review')),
    reviewed_at             TIMESTAMP,
    review_notes            VARCHAR,
    -- Where approved data lands
    destination_table       VARCHAR,
    destination_id          INTEGER
);
"""

SUBMISSION_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_sq_status ON submission_queue(status)",
    "CREATE INDEX IF NOT EXISTS idx_sq_type ON submission_queue(submission_type)",
    "CREATE INDEX IF NOT EXISTS idx_sq_player ON submission_queue(target_player_id)",
    "CREATE INDEX IF NOT EXISTS idx_sq_submitted ON submission_queue(submitted_at)",
]

# Append to existing registries
LAYER_2_TABLES.append(CREATE_SUBMISSION_QUEUE)
DROP_ORDER.insert(0, "submission_queue")
