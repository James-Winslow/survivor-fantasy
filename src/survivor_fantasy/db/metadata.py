"""
Database metadata registry.

Structured documentation for every table, column, and relationship
in the survivor-fantasy database. This file is the authoritative
reference for:

  - Table grain, layer, role, and centrality
  - Column descriptions, types, sources, and nullability
  - Join relationships with cardinality and join key
  - Which tables are facts vs. dimensions
  - Common join patterns and their intended use
  - Many-to-one join risks and how to avoid them

This metadata is used by:
  - docs/schema.md generation (render_schema_docs())
  - Pipeline validation (assert expected tables/columns exist)
  - Dashboard data lineage display
  - Future: data catalog, automated ER diagram generation

Star Schema Framing
-------------------
This database is not a pure star schema (it's too normalized for that)
but the star schema lens is useful for thinking about join patterns.

  Fact tables (events that happened, high row count, append-only):
    votes, challenge_participants, episode_scores,
    player_postseason_statements, social_media_posts,
    confessional_text, scrape_log, submission_queue

  Dimension tables (descriptive attributes, lower row count, slowly changing):
    seasons, players, tribes, episodes, tribal_councils,
    challenges, advantages, league_players

  Bridge tables (resolve many-to-many relationships):
    tribe_memberships (player ↔ tribe, time-windowed)
    league_rosters (league_player ↔ survivor_player, episode-scoped)
    challenge_participants (player ↔ challenge)

  Computed/materialized tables (rebuilt by features.py, never manually edited):
    alliance_index, player_season_stats, player_trajectories,
    player_archetypes, edit_classifications, visualization_metadata,
    league_standings

Centrality
----------
Central tables are those joined by many other tables — changes to their
schema have the widest blast radius.

  Most central (change carefully):
    players       — referenced by ~15 other tables
    episodes      — referenced by ~10 other tables
    seasons       — referenced by ~12 other tables
    tribal_councils — referenced by votes, advantages

  Moderately central:
    tribes, challenges, league_players, advantages

  Leaf tables (reference others but aren't widely referenced):
    social_media_posts, scrape_log, submission_queue,
    player_pregame_profiles, confessional_text

Join Cardinality Key
--------------------
  1:1   — one row in A matches exactly one row in B
  1:N   — one row in A matches many rows in B
  N:1   — many rows in A match one row in B (watch for fan-out)
  M:N   — many-to-many (always needs a bridge table)

Fan-out Warning
---------------
A "fan-out join" happens when joining a fact table to another fact table
directly, causing row multiplication. The canonical example:
  votes JOIN challenges (both keyed on episode_id) → Cartesian product
Always join through the correct grain key (tc_id, challenge_id)
not through episode_id when working with these tables.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ColumnMeta:
    name: str
    dtype: str
    description: str
    nullable: bool = True
    is_pk: bool = False
    is_fk: bool = False
    fk_table: Optional[str] = None
    fk_column: Optional[str] = None
    source: Optional[str] = None          # "survivoR" / "manual" / "computed" / "scraped"
    example_values: Optional[list] = None


@dataclass
class RelationshipMeta:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    cardinality: str                      # "1:1" / "1:N" / "N:1" / "M:N"
    join_description: str
    fan_out_risk: bool = False
    fan_out_note: Optional[str] = None


@dataclass
class TableMeta:
    name: str
    layer: str                            # "L1_core" / "L1_computed" / "L1_extended" / "L2"
    role: str                             # "fact" / "dimension" / "bridge" / "computed" / "audit"
    grain: str                            # plain-English description of one row
    description: str
    centrality: str                       # "high" / "medium" / "low"
    row_count_estimate: str               # "~750" / "~50k" / "grows weekly"
    is_append_only: bool = False          # facts are append-only; dimensions are updated
    primary_key: Optional[str] = None
    source: Optional[str] = None          # "survivoR" / "manual" / "computed" / "scraped"
    phase_available: int = 1              # which build phase populates this table
    columns: list[ColumnMeta] = field(default_factory=list)
    notes: Optional[str] = None


# =============================================================================
# TABLE REGISTRY
# =============================================================================

TABLES: dict[str, TableMeta] = {

    # ── L1 Core: Dimensions ──────────────────────────────────────────────────

    "seasons": TableMeta(
        name="seasons",
        layer="L1_core",
        role="dimension",
        grain="One row per season of Survivor US.",
        description=(
            "Root dimension table. Every other table references seasons directly "
            "or indirectly. Contains structural metadata that controls model behavior: "
            "era determines which feature weights apply; day_count affects survival "
            "curve shape; format flags enable format-conditional analyses."
        ),
        centrality="high",
        row_count_estimate="~50 rows (one per season)",
        is_append_only=False,
        primary_key="season_id",
        source="survivoR + manual",
        phase_available=1,
        notes=(
            "season_id matches season_num (1-indexed). era is the most important "
            "model conditioning variable — new_era seasons (S41+) have structurally "
            "different elimination patterns due to 26-day format and revised advantages."
        ),
    ),

    "players": TableMeta(
        name="players",
        layer="L1_core",
        role="dimension",
        grain="One row per castaway per season. Returning players have multiple rows.",
        description=(
            "Most-referenced table in the schema. player_id uses the survivoR "
            "castaway_id string (e.g. 'US0001') for traceability. Physical profile "
            "fields are nullable and manually backfilled. archetype_label is a "
            "Phase 4 enrichment — leave null until the classifier runs."
        ),
        centrality="high",
        row_count_estimate="~800 rows (16-20 per season × 50 seasons)",
        is_append_only=False,
        primary_key="player_id",
        source="survivoR + manual",
        phase_available=1,
        notes=(
            "Referenced by ~15 other tables. Schema changes here have the widest "
            "blast radius. boot_episode=NULL means either winner or still active — "
            "distinguish by checking exit_type or placement."
        ),
    ),

    "tribes": TableMeta(
        name="tribes",
        layer="L1_core",
        role="dimension",
        grain="One row per tribe configuration per season.",
        description=(
            "A tribe that gets renamed or reformed after a swap gets a new row. "
            "episode_formed and episode_dissolved define the time window this "
            "configuration was active. color_hex supports the visualization layer."
        ),
        centrality="medium",
        row_count_estimate="~200 rows",
        is_append_only=False,
        primary_key="tribe_id",
        source="survivoR",
        phase_available=1,
    ),

    "episodes": TableMeta(
        name="episodes",
        layer="L1_core",
        role="dimension",
        grain="One row per episode.",
        description=(
            "Time dimension for the entire database. merge_occurred and swap_occurred "
            "are critical flags — they trigger feature weight recalculation in the "
            "model. episode_num_overall enables cross-season temporal analysis."
        ),
        centrality="high",
        row_count_estimate="~750 rows (13-16 per season × 50 seasons)",
        is_append_only=True,
        primary_key="episode_id",
        source="survivoR",
        phase_available=1,
        notes=(
            "Referenced by ~10 other tables. The UNIQUE(season_id, episode_num) "
            "constraint is the primary lookup key — use this pair when joining "
            "from config values (current_season, episode_num) to episode_id."
        ),
    ),

    "tribal_councils": TableMeta(
        name="tribal_councils",
        layer="L1_core",
        role="dimension",
        grain="One row per tribal council. Some episodes have multiple TCs.",
        description=(
            "Intermediate dimension between episodes and votes. tc_type controls "
            "scoring logic — split_losing TCs don't produce jury members in new era. "
            "tc_order distinguishes double elimination TCs within one episode."
        ),
        centrality="medium",
        row_count_estimate="~850 rows",
        is_append_only=True,
        primary_key="tc_id",
        source="survivoR",
        phase_available=1,
        notes=(
            "Do not join votes directly to episodes via episode_id — always join "
            "through tribal_councils to avoid fan-out when an episode has "
            "multiple TCs."
        ),
    ),

    "challenges": TableMeta(
        name="challenges",
        layer="L1_core",
        role="dimension",
        grain="One row per challenge.",
        description=(
            "Challenge metadata including format classification, which feeds the "
            "challenge prediction model. has_*_component boolean flags support "
            "granular format analysis for multi-component challenges. "
            "second/third_place_tribe_id supports 3-tribe scoring."
        ),
        centrality="medium",
        row_count_estimate="~1,200 rows (~2 per episode)",
        is_append_only=True,
        primary_key="challenge_id",
        source="survivoR",
        phase_available=1,
        notes=(
            "Do not join challenge_participants directly to votes — they share "
            "episode_id but have different grains. Fan-out risk is HIGH if you "
            "join both to episodes without filtering."
        ),
    ),

    "advantages": TableMeta(
        name="advantages",
        layer="L1_core",
        role="dimension",
        grain="One row per advantage from discovery through play/expiry.",
        description=(
            "Tracks the full lifecycle of each advantage. current_holder_player_id "
            "is updated as advantages change hands. votes_nullified enables the "
            "vote_cancellation_bonus scoring. outcome drives scoring edge cases "
            "like voted_out_holding."
        ),
        centrality="medium",
        row_count_estimate="~500 rows",
        is_append_only=False,
        primary_key="advantage_id",
        source="survivoR",
        phase_available=1,
    ),

    # ── L1 Core: Facts ───────────────────────────────────────────────────────

    "votes": TableMeta(
        name="votes",
        layer="L1_core",
        role="fact",
        grain="One row per vote cast at a tribal council.",
        description=(
            "Highest-volume fact table. The atomic unit of strategic behavior. "
            "nullified=TRUE means an idol canceled this vote. on_majority_side "
            "is computed at insert time — TRUE if voted_for_player_id was the "
            "player eliminated. vote_order=2 indicates a revote after a tie."
        ),
        centrality="medium",
        row_count_estimate="~8,000 rows (~9 votes per TC × 850 TCs)",
        is_append_only=True,
        primary_key="vote_id",
        source="survivoR",
        phase_available=1,
        notes=(
            "season_id and episode_id are denormalized onto this table (redundant "
            "with tc_id → tribal_councils → episodes) to enable fast partition "
            "pruning by season without multi-hop joins. This is an intentional "
            "denormalization for query performance."
        ),
    ),

    "challenge_participants": TableMeta(
        name="challenge_participants",
        layer="L1_core",
        role="bridge",
        grain="One row per player per challenge.",
        description=(
            "Bridge table resolving the M:N between players and challenges. "
            "Normalizes the sat_out field that would otherwise be a comma-separated "
            "string on challenges. participated=FALSE, sat_out=TRUE means the player "
            "was on the tribe but did not compete."
        ),
        centrality="low",
        row_count_estimate="~9,000 rows",
        is_append_only=True,
        primary_key="id",
        source="survivoR",
        phase_available=1,
    ),

    "confessionals": TableMeta(
        name="confessionals",
        layer="L1_core",
        role="fact",
        grain="One row per player per episode.",
        description=(
            "Aggregate confessional counts. index_count and index_time are "
            "survivoR's normalized cumulative metrics that control for tribal "
            "attendance — a player who attends TC gets more confessionals by "
            "default, so the index removes that structural effect."
        ),
        centrality="low",
        row_count_estimate="~11,000 rows",
        is_append_only=True,
        primary_key="id",
        source="survivoR",
        phase_available=1,
    ),

    "confessional_text": TableMeta(
        name="confessional_text",
        layer="L1_core",
        role="fact",
        grain="One row per individual confessional.",
        description=(
            "Phase 4 placeholder. Empty until NLP pipeline is built. "
            "Text sourced from fan transcription projects. NLP output columns "
            "are populated by nlp/confessionals.py after text is loaded."
        ),
        centrality="low",
        row_count_estimate="empty until Phase 4",
        is_append_only=True,
        primary_key="id",
        source="scraped",
        phase_available=4,
    ),

    # ── L1 Bridge ────────────────────────────────────────────────────────────

    "tribe_memberships": TableMeta(
        name="tribe_memberships",
        layer="L1_core",
        role="bridge",
        grain="One row per player per tribe configuration, with episode range.",
        description=(
            "The authoritative source for 'what tribe was player X on at episode N'. "
            "Time-windowed: episode_joined and episode_left define the valid range. "
            "Query pattern: WHERE player_id = :pid AND episode_joined <= :ep "
            "AND (episode_left IS NULL OR episode_left > :ep). "
            "reason_joined='swap' is the most analytically important value — "
            "post-swap tribal compositions drive isolation scores."
        ),
        centrality="medium",
        row_count_estimate="~1,500 rows",
        is_append_only=False,
        primary_key="id",
        source="survivoR + manual",
        phase_available=1,
        notes=(
            "This table resolves what would otherwise be an impossible join: "
            "'what was the tribal composition at this specific episode?' "
            "Without it, post-swap network analysis and challenge prediction "
            "both require string parsing of tribe history. "
            "The idx_tm_player_episode composite index is critical for performance."
        ),
    ),

    # ── L1 Computed ──────────────────────────────────────────────────────────

    "alliance_index": TableMeta(
        name="alliance_index",
        layer="L1_computed",
        role="computed",
        grain="One row per player pair per episode (cumulative through that episode).",
        description=(
            "Co-vote frequency between every pair of players who attended the same "
            "tribal council through a given episode. alliance_score = co_vote_count "
            "/ shared_tc_count, ranges 0-1. Canonical ordering (player_a_id < "
            "player_b_id) prevents duplicate pairs. alliance_score_delta captures "
            "changes from the prior episode — sudden drops signal alliance fractures."
        ),
        centrality="medium",
        row_count_estimate="~50,000 rows (grows quadratically with active players)",
        is_append_only=False,
        primary_key="id",
        source="computed",
        phase_available=2,
        notes=(
            "Rebuilt in full by features.py after each episode. Do not manually "
            "edit. The canonical ordering constraint is enforced by the DB — "
            "inserts with player_a_id > player_b_id will fail."
        ),
    ),

    "player_season_stats": TableMeta(
        name="player_season_stats",
        layer="L1_computed",
        role="computed",
        grain="One row per player per season per episode (cumulative snapshot).",
        description=(
            "Denormalized summary of all measurable player behaviors through a "
            "given episode. Primary input to the historical survival and challenge "
            "models. The model never queries raw tables — it reads from here. "
            "episode_through enables mid-season snapshots for temporal analysis."
        ),
        centrality="medium",
        row_count_estimate="~40,000 rows",
        is_append_only=False,
        primary_key="id",
        source="computed",
        phase_available=2,
    ),

    "player_trajectories": TableMeta(
        name="player_trajectories",
        layer="L1_computed",
        role="computed",
        grain="One row per player per episode — full multidimensional state vector.",
        description=(
            "The state representation used for sequence similarity analysis. "
            "Enables 'find historical players in a similar position at this "
            "point in their season.' survived_this_episode and episodes_remaining "
            "are populated retroactively for historical data, allowing the model "
            "to learn from completed trajectories."
        ),
        centrality="low",
        row_count_estimate="~11,000 rows",
        is_append_only=False,
        primary_key="id",
        source="computed",
        phase_available=3,
    ),

    # ── L1 Extended ──────────────────────────────────────────────────────────

    "player_pregame_profiles": TableMeta(
        name="player_pregame_profiles",
        layer="L1_extended",
        role="dimension",
        grain="One row per player per season.",
        description=(
            "Pre-game identity and stated strategy from cast videos and press. "
            "Baseline for 'stated vs. actual' analyses — did the player execute "
            "the strategy they described before the game?"
        ),
        centrality="low",
        row_count_estimate="~200 rows (backfill where available)",
        is_append_only=False,
        primary_key="id",
        source="manual + scraped",
        phase_available=3,
    ),

    "player_postseason_statements": TableMeta(
        name="player_postseason_statements",
        layer="L1_extended",
        role="fact",
        grain="One row per statement from a post-season source.",
        description=(
            "Post-season revelations — the dark matter of unaired strategy. "
            "verified=FALSE until corroborated by a second source. "
            "Raw text is stored; NLP outputs are appended by the pipeline. "
            "This table is the primary input to post-season model recalibration."
        ),
        centrality="low",
        row_count_estimate="grows with scraping activity",
        is_append_only=True,
        primary_key="id",
        source="scraped + manual",
        phase_available=3,
    ),

    "player_external_assessments": TableMeta(
        name="player_external_assessments",
        layer="L1_extended",
        role="fact",
        grain="One row per assessment of one player by one source.",
        description=(
            "How players assessed each other (pregame rankings, jury comments) "
            "and how external analysts rated them. jury_final_vote_reason is "
            "particularly valuable — the explicit reasoning behind the million "
            "dollar vote, often revealed in interviews."
        ),
        centrality="low",
        row_count_estimate="~500 rows",
        is_append_only=True,
        primary_key="id",
        source="scraped + manual",
        phase_available=3,
    ),

    "edit_classifications": TableMeta(
        name="edit_classifications",
        layer="L1_extended",
        role="computed",
        grain="One row per player per episode.",
        description=(
            "Edit type classification — winner/contender/narrator/villain/UTR etc. "
            "method='manual' for human labels; method='classifier' for Phase 4 "
            "model outputs. Confidence score allows filtering to high-certainty "
            "labels for model training."
        ),
        centrality="low",
        row_count_estimate="~11,000 rows",
        is_append_only=False,
        primary_key="id",
        source="manual + computed",
        phase_available=3,
    ),

    "social_media_posts": TableMeta(
        name="social_media_posts",
        layer="L1_extended",
        role="fact",
        grain="One row per social media post from a player account.",
        description=(
            "Raw scraped content from player social media during and after "
            "their season. is_during_airing distinguishes live-reaction posts "
            "(high NDA sensitivity, often cryptic) from post-season content. "
            "NLP outputs appended by pipeline."
        ),
        centrality="low",
        row_count_estimate="grows with scraping",
        is_append_only=True,
        primary_key="id",
        source="scraped",
        phase_available=4,
    ),

    "player_archetypes": TableMeta(
        name="player_archetypes",
        layer="L1_extended",
        role="dimension",
        grain="One row per player per season.",
        description=(
            "Structured archetype classification across three axes: primary type, "
            "challenge profile, and social/strategic profile. More granular than "
            "the single archetype_label on players. Used by the challenge prediction "
            "model and trajectory clustering."
        ),
        centrality="low",
        row_count_estimate="~800 rows",
        is_append_only=False,
        primary_key="id",
        source="manual + computed",
        phase_available=3,
    ),

    "visualization_metadata": TableMeta(
        name="visualization_metadata",
        layer="L1_extended",
        role="computed",
        grain="One row per player per episode.",
        description=(
            "Pre-computed layout hints for the network visualization. Stores island "
            "positions, node coordinates, thumbnail URLs, and storytelling flags. "
            "story_beat_type and story_beat_description are the TikTok content feed — "
            "the pipeline surfaces anomalies here automatically."
        ),
        centrality="low",
        row_count_estimate="~11,000 rows",
        is_append_only=False,
        primary_key="id",
        source="computed",
        phase_available=2,
    ),

    "scrape_log": TableMeta(
        name="scrape_log",
        layer="L1_extended",
        role="audit",
        grain="One row per scraping attempt.",
        description=(
            "Audit trail for all web scraping. Enables incremental scraping "
            "(skip URLs with status='success'), rate limit debugging, and "
            "attribution tracking. scraper_version allows correlating data "
            "quality issues with specific scraper releases."
        ),
        centrality="low",
        row_count_estimate="grows with scraping",
        is_append_only=True,
        primary_key="id",
        source="computed",
        phase_available=3,
    ),

    # ── L2 Tables ────────────────────────────────────────────────────────────

    "league_players": TableMeta(
        name="league_players",
        layer="L2",
        role="dimension",
        grain="One row per fantasy league participant.",
        description="Fantasy league participants. Small, stable, manually managed.",
        centrality="medium",
        row_count_estimate="~10 rows",
        is_append_only=False,
        primary_key="league_player_id",
        source="manual",
        phase_available=1,
    ),

    "league_rosters": TableMeta(
        name="league_rosters",
        layer="L2",
        role="bridge",
        grain="One row per (league_player, survivor_player, episode).",
        description=(
            "Full roster history including bench changes. is_active=TRUE means "
            "starter (scoring); FALSE means bench. Capturing per-episode roster "
            "state enables what-if queries: 'what would I have scored if I'd "
            "started X instead of Y in episode 3?'"
        ),
        centrality="medium",
        row_count_estimate="~500 rows per season",
        is_append_only=True,
        primary_key="id",
        source="manual",
        phase_available=1,
    ),

    "episode_scores": TableMeta(
        name="episode_scores",
        layer="L2",
        role="fact",
        grain="One row per scoring event (not per player per episode).",
        description=(
            "Line-item scoring events. Summing pts over (league_player_id, episode_id) "
            "gives episode total. event_type matches config.yaml keys exactly — "
            "no point values are hardcoded here. event_description is the human- "
            "readable string rendered on the dashboard scorecard."
        ),
        centrality="low",
        row_count_estimate="~200 rows per episode",
        is_append_only=True,
        primary_key="id",
        source="computed",
        phase_available=1,
    ),

    "league_standings": TableMeta(
        name="league_standings",
        layer="L2",
        role="computed",
        grain="One row per league player per episode (cumulative).",
        description=(
            "Materialized standings rebuilt after each episode. Stores both "
            "episode_pts and cumulative_pts for efficient dashboard queries — "
            "no aggregation needed at render time."
        ),
        centrality="low",
        row_count_estimate="~150 rows per season",
        is_append_only=False,
        primary_key="id",
        source="computed",
        phase_available=1,
    ),

    "submission_queue": TableMeta(
        name="submission_queue",
        layer="L2",
        role="audit",
        grain="One row per external data submission awaiting review.",
        description=(
            "Staging table for all external contributions. Raw payloads never "
            "go directly to Layer 1 — they sit here until reviewed and approved. "
            "destination_table and destination_id track where approved data lands. "
            "extracted_claims is populated by the Claude-assisted Phase 4 pipeline."
        ),
        centrality="low",
        row_count_estimate="rolling — approved rows age out",
        is_append_only=False,
        primary_key="id",
        source="external",
        phase_available=2,
    ),
}

# =============================================================================
# RELATIONSHIP REGISTRY
# =============================================================================

RELATIONSHIPS: list[RelationshipMeta] = [

    # seasons → everything
    RelationshipMeta("players", "season_id", "seasons", "season_id", "N:1",
        "Every player belongs to one season."),
    RelationshipMeta("tribes", "season_id", "seasons", "season_id", "N:1",
        "Every tribe belongs to one season."),
    RelationshipMeta("episodes", "season_id", "seasons", "season_id", "N:1",
        "Every episode belongs to one season."),

    # episodes → downstream
    RelationshipMeta("tribal_councils", "episode_id", "episodes", "episode_id", "N:1",
        "Most episodes have one TC; double eliminations have two. "
        "Join via tc_id not episode_id when working with votes.",
        fan_out_risk=True,
        fan_out_note="Joining votes to challenges via episode_id causes fan-out. "
                     "Always join votes→tribal_councils→episodes and "
                     "challenges→episodes separately."),
    RelationshipMeta("challenges", "episode_id", "episodes", "episode_id", "N:1",
        "Each episode has 1-2 challenges (reward + immunity or combined)."),
    RelationshipMeta("confessionals", "episode_id", "episodes", "episode_id", "N:1",
        "One confessional aggregate row per player per episode."),

    # tribe_memberships — time-windowed bridge
    RelationshipMeta("tribe_memberships", "player_id", "players", "player_id", "N:1",
        "Each membership record belongs to one player."),
    RelationshipMeta("tribe_memberships", "tribe_id", "tribes", "tribe_id", "N:1",
        "Each membership record belongs to one tribe configuration."),

    # votes → tribal_councils (not episodes directly)
    RelationshipMeta("votes", "tc_id", "tribal_councils", "tc_id", "N:1",
        "Every vote belongs to one tribal council. "
        "Use this join, not votes→episodes, to avoid fan-out."),
    RelationshipMeta("votes", "voter_player_id", "players", "player_id", "N:1",
        "The player who cast this vote."),
    RelationshipMeta("votes", "voted_for_player_id", "players", "player_id", "N:1",
        "The player this vote was cast against."),

    # challenge_participants — bridge
    RelationshipMeta("challenge_participants", "challenge_id", "challenges", "challenge_id", "N:1",
        "Each participation record belongs to one challenge."),
    RelationshipMeta("challenge_participants", "player_id", "players", "player_id", "N:1",
        "Each participation record belongs to one player."),

    # advantages
    RelationshipMeta("advantages", "found_by_player_id", "players", "player_id", "N:1",
        "The player who found this advantage."),
    RelationshipMeta("advantages", "played_at_tc_id", "tribal_councils", "tc_id", "N:1",
        "The TC at which this advantage was played."),

    # alliance_index — computed pair scores
    RelationshipMeta("alliance_index", "player_a_id", "players", "player_id", "N:1",
        "First player in the alliance pair (lexicographically smaller ID)."),
    RelationshipMeta("alliance_index", "player_b_id", "players", "player_id", "N:1",
        "Second player in the alliance pair."),
    RelationshipMeta("alliance_index", "episode_id", "episodes", "episode_id", "N:1",
        "Scores are cumulative through this episode."),

    # L2 joins
    RelationshipMeta("league_rosters", "league_player_id", "league_players", "league_player_id", "N:1",
        "Each roster entry belongs to one fantasy league player."),
    RelationshipMeta("league_rosters", "survivor_player_id", "players", "player_id", "N:1",
        "Each roster entry references one Survivor player."),
    RelationshipMeta("episode_scores", "league_player_id", "league_players", "league_player_id", "N:1",
        "Each score event belongs to one fantasy league player."),
    RelationshipMeta("episode_scores", "survivor_player_id", "players", "player_id", "N:1",
        "Each score event is caused by one Survivor player."),
    RelationshipMeta("league_standings", "league_player_id", "league_players", "league_player_id", "N:1",
        "Each standing row belongs to one fantasy league player."),
]

# =============================================================================
# COMMON JOIN PATTERNS
# =============================================================================

JOIN_PATTERNS: dict[str, dict] = {

    "player_tribe_at_episode": {
        "description": "What tribe was a player on at a given episode?",
        "tables": ["players", "tribe_memberships", "tribes"],
        "pattern": """
            SELECT p.full_name, t.tribe_name, t.color_hex
            FROM players p
            JOIN tribe_memberships tm
              ON tm.player_id = p.player_id
             AND tm.episode_joined <= :episode_num
             AND (tm.episode_left IS NULL OR tm.episode_left > :episode_num)
            JOIN tribes t ON tm.tribe_id = t.tribe_id
            WHERE p.player_id = :player_id
        """,
        "fan_out_risk": False,
        "notes": "The time-windowed join on tribe_memberships is the correct pattern. "
                 "Never use players.starting_tribe for post-swap analysis.",
    },

    "votes_received_by_episode": {
        "description": "How many votes has a player received through episode N?",
        "tables": ["votes", "tribal_councils", "episodes"],
        "pattern": """
            SELECT v.voted_for_player_id, COUNT(*) AS votes_received
            FROM votes v
            JOIN tribal_councils tc ON v.tc_id = tc.tc_id
            JOIN episodes e ON tc.episode_id = e.episode_id
            WHERE e.season_id = :season_id
              AND e.episode_num <= :episode_num
              AND v.nullified = FALSE
            GROUP BY v.voted_for_player_id
        """,
        "fan_out_risk": False,
        "notes": "Always filter nullified=FALSE unless you specifically want voided votes.",
    },

    "alliance_matrix_at_episode": {
        "description": "Full alliance score matrix for all active players at episode N.",
        "tables": ["alliance_index", "players", "episodes"],
        "pattern": """
            SELECT
                pa.full_name AS player_a,
                pb.full_name AS player_b,
                ai.alliance_score,
                ai.same_tribe
            FROM alliance_index ai
            JOIN players pa ON ai.player_a_id = pa.player_id
            JOIN players pb ON ai.player_b_id = pb.player_id
            JOIN episodes e ON ai.episode_id = e.episode_id
            WHERE e.season_id = :season_id
              AND e.episode_num = :episode_num
              AND ai.alliance_score >= :min_score
            ORDER BY ai.alliance_score DESC
        """,
        "fan_out_risk": False,
    },

    "league_scorecard_episode": {
        "description": "Full score breakdown for one league player in one episode.",
        "tables": ["episode_scores", "players", "episodes", "league_players"],
        "pattern": """
            SELECT
                p.full_name    AS survivor,
                es.event_type,
                es.pts,
                es.event_description
            FROM episode_scores es
            JOIN players p       ON es.survivor_player_id = p.player_id
            JOIN league_players lp ON es.league_player_id = lp.league_player_id
            WHERE lp.name = :league_player_name
              AND es.season_id = :season_id
              AND es.episode_id = (
                  SELECT episode_id FROM episodes
                  WHERE season_id = :season_id AND episode_num = :episode_num
              )
            ORDER BY p.full_name, es.pts DESC
        """,
        "fan_out_risk": False,
    },

    "active_players_at_episode": {
        "description": "All players still in the game at the start of episode N.",
        "tables": ["players", "seasons", "episodes"],
        "pattern": """
            SELECT p.*
            FROM players p
            JOIN seasons s ON p.season_id = s.season_id
            WHERE s.season_num = :season_num
              AND (p.boot_episode IS NULL OR p.boot_episode >= :episode_num)
              AND p.exit_type != 'winner'   -- exclude winner from mid-season queries
               OR p.boot_episode IS NULL    -- still active
        """,
        "fan_out_risk": False,
        "notes": "boot_episode >= episode_num includes the player for the episode "
                 "in which they were eliminated (they were active at the start).",
    },

    "DANGER_votes_x_challenges": {
        "description": "DANGEROUS: joining votes and challenges via episode_id.",
        "tables": ["votes", "challenges", "episodes"],
        "pattern": """
            -- DO NOT DO THIS:
            SELECT * FROM votes v
            JOIN challenges c ON v.episode_id = c.episode_id  -- FAN-OUT!
            -- votes has ~9 rows per TC; challenges has ~2 per episode
            -- This produces 9 × 2 = 18 rows per TC instead of 9
            -- INSTEAD: join them separately to episodes, never to each other
        """,
        "fan_out_risk": True,
        "notes": "votes and challenges share episode_id but have different grains. "
                 "Joining them directly multiplies rows. Always aggregate one before "
                 "joining to the other.",
    },
}

# =============================================================================
# PUBLIC API
# =============================================================================

def get_table(name: str) -> TableMeta:
    if name not in TABLES:
        raise KeyError(f"Table '{name}' not in metadata registry.")
    return TABLES[name]


def get_relationships_for(table: str) -> list[RelationshipMeta]:
    return [r for r in RELATIONSHIPS if r.from_table == table or r.to_table == table]


def get_fan_out_risks() -> list[RelationshipMeta]:
    return [r for r in RELATIONSHIPS if r.fan_out_risk]


def get_tables_by_layer(layer: str) -> list[TableMeta]:
    return [t for t in TABLES.values() if t.layer == layer]


def get_tables_by_centrality(centrality: str) -> list[TableMeta]:
    return [t for t in TABLES.values() if t.centrality == centrality]


def get_tables_by_phase(phase: int) -> list[TableMeta]:
    return [t for t in TABLES.values() if t.phase_available <= phase]


def render_summary() -> None:
    """Print a human-readable summary of the schema metadata."""
    print(f"\n{'='*70}")
    print("SURVIVOR-FANTASY DATABASE METADATA SUMMARY")
    print(f"{'='*70}")

    layers = ["L1_core", "L1_computed", "L1_extended", "L2"]
    for layer in layers:
        tables = get_tables_by_layer(layer)
        print(f"\n── {layer} ({len(tables)} tables) {'─'*(50-len(layer))}")
        for t in tables:
            role_str = f"[{t.role:<10}]"
            central_str = f"centrality={t.centrality:<6}"
            phase_str = f"phase={t.phase_available}"
            print(f"  {t.name:<35} {role_str} {central_str} {phase_str}")

    print(f"\n── Relationships ({len(RELATIONSHIPS)}) {'─'*40}")
    fans = get_fan_out_risks()
    if fans:
        print(f"\n  ⚠ Fan-out risks ({len(fans)}):")
        for r in fans:
            print(f"    {r.from_table} → {r.to_table} via {r.from_column}")
            print(f"      {r.fan_out_note}")

    print(f"\n── High-centrality tables {'─'*40}")
    for t in get_tables_by_centrality("high"):
        refs = len(get_relationships_for(t.name))
        print(f"  {t.name} ({refs} relationships)")

    print()


if __name__ == "__main__":
    render_summary()
