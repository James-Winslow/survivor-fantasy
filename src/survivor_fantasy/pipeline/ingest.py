"""
survivoR historical data ingestion.

Reads CSVs exported from the survivoR R package (data/survivoR_exports/)
and loads them into Layer 1 DuckDB tables.

Run:
    sf-ingest              (via CLI)
    make ingest            (via Makefile)
    python -m survivor_fantasy.pipeline.ingest  (directly)

Single table test:
    sf-ingest --table seasons

Composite key conventions:
    player_id:    "{castaway_id}_S{season}"   e.g. "US0001_S1"
    challenge_id: "US{season}_{id}"           e.g. "US01_14"
    advantage_id: "US{season}_{id}"           e.g. "US11_1"
"""

import click
import pandas as pd
import numpy as np
from pathlib import Path
import yaml
import logging

from survivor_fantasy.db.connect import get_connection
from survivor_fantasy.db.schema import create_all_tables

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


# =============================================================================
# HELPERS
# =============================================================================

def get_exports_path(config_path="config.yaml"):
    with open(config_path) as f:
        return Path(yaml.safe_load(f)["survivoR_exports_path"])


def read_csv(exports_path, filename):
    path = exports_path / filename
    if not path.exists():
        raise FileNotFoundError(f"Not found: {path}\nRun scripts/export_survivoR.R first.")
    df = pd.read_csv(path, low_memory=False)
    log.info(f"  Read {filename}: {len(df):,} rows, {len(df.columns)} columns")
    return df


def insert_df(conn, table, df):
    """
    Insert DataFrame into table using DuckDB native support.
    Deletes existing rows for the same seasons first (idempotent).
    """
    if df.empty:
        return
    if "season_id" in df.columns:
        vals = df["season_id"].dropna().unique().tolist()
        if vals:
            ph = ",".join("?" * len(vals))
            conn.execute(f"DELETE FROM {table} WHERE season_id IN ({ph})", vals)
    elif "season_num" in df.columns:
        vals = df["season_num"].dropna().unique().tolist()
        if vals:
            ph = ",".join("?" * len(vals))
            conn.execute(f"DELETE FROM {table} WHERE season_num IN ({ph})", vals)
    else:
        conn.execute(f"DELETE FROM {table}")
    conn.register("_insert_df", df)
    conn.execute(f"INSERT INTO {table} SELECT * FROM _insert_df")
    conn.unregister("_insert_df")


def report(table, conn):
    n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    log.info(f"  [OK] {table}: {n:,} rows")


def sint(v):
    try:
        return None if pd.isna(v) else int(v)
    except Exception:
        return None


def sfloat(v):
    try:
        return None if pd.isna(v) else float(v)
    except Exception:
        return None


def sstr(v):
    if v is None:
        return None
    try:
        return None if pd.isna(v) else str(v).strip()
    except Exception:
        return None


def sbool(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, float) and np.isnan(v):
        return None
    return str(v).strip().upper() in ("TRUE", "1", "YES")


# =============================================================================
# TABLE LOADERS
# =============================================================================

def load_seasons(conn, exports_path):
    log.info("Loading seasons...")
    df = read_csv(exports_path, "season_summary.csv")
    df = df[df["version"] == "US"].copy()

    def era(n):
        if n <= 20: return "original"
        if n <= 40: return "hd"
        return "new_era"

    def fmt(row):
        name = str(row.get("season_name", "")).lower()
        if any(x in name for x in ["all-stars","heroes","winners","game changers",
                                    "second chance","cambodia"]):
            return "returnees"
        return "new_era" if row["season"] >= 41 else "classic"

    rows = []
    for _, row in df.iterrows():
        sn = sint(row["season"])
        if not sn: continue
        name = str(row.get("season_name", "")).lower()
        rows.append({
            "season_id":               sn,
            "season_name":             sstr(row.get("season_name")),
            "season_num":              sn,
            "year":                    sint(str(row.get("premiered",""))[:4]) if row.get("premiered") else None,
            "n_players":               sint(row.get("n_cast")),
            "n_episodes":              None,
            "filming_location":        sstr(row.get("location")),
            "merge_episode":           None,
            "n_starting_tribes":       sint(row.get("n_tribes")),
            "format":                  fmt(row),
            "era":                     era(sn),
            "day_count":               26 if sn >= 41 else 39,
            "has_redemption_island":   any(x in name for x in ["redemption","blood vs water"]),
            "has_edge_of_extinction":  "edge" in name,
            "has_exile_island":        "exile" in name,
            "n_jury_members":          sint(row.get("n_jury")),
        })

    insert_df(conn, "seasons", pd.DataFrame(rows))
    report("seasons", conn)


def load_players(conn, exports_path):
    log.info("Loading players...")
    castaways = read_csv(exports_path, "castaways.csv")
    details   = read_csv(exports_path, "castaway_details.csv")
    castaways = castaways[castaways["version"] == "US"].copy()
    castaways = (castaways.sort_values("episode")
                 .groupby(["castaway_id","season"], as_index=False).last())
    merged = castaways.merge(
        details[["castaway_id","gender","race","ethnicity","personality_type","occupation"]],
        on="castaway_id", how="left"
    )

    def race_eth(row):
        parts = [sstr(row.get(c)) for c in ["race","ethnicity"]]
        parts = [p for p in parts if p and p.lower() not in ("na","none","nan")]
        return " / ".join(parts) if parts else None

    def exit_type(result, winner):
        if winner: return "winner"
        r = str(result or "").lower()
        if "quit" in r: return "quit"
        if "med" in r or "evacuat" in r: return "medevac"
        if "fire" in r: return "fire_challenge"
        if "rock" in r: return "rock_draw"
        if "runner" in r or "finalist" in r: return "runner_up"
        return "voted_out"

    rows = []
    for _, row in merged.iterrows():
        pid = sstr(row["castaway_id"])
        sn  = sint(row["season"])
        if not pid or not sn: continue
        winner = sbool(row.get("winner")) or False
        rows.append({
            "player_id":           f"{pid}_S{sn}",
            "season_id":           sn,
            "full_name":           sstr(row.get("full_name")),
            "short_name":          sstr(row.get("castaway")),
            "age":                 sint(row.get("age")),
            "gender":              sstr(row.get("gender")),
            "race_ethnicity":      race_eth(row),
            "occupation":          sstr(row.get("occupation")),
            "hometown":            sstr(row.get("city")),
            "starting_tribe":      sstr(row.get("original_tribe")),
            "placement":           sint(row.get("place")),
            "jury_votes_received": 0,
            "boot_episode":        None if winner else sint(row.get("episode")),
            "boot_day":            sint(row.get("day")),
            "exit_type":           exit_type(row.get("result"), winner),
            "height_cm":           None,
            "weight_kg":           None,
            "physical_tier":       None,
            "is_returnee":         False,
            "previous_seasons":    None,
            "archetype_label":     None,
            "mbti_type":           sstr(row.get("personality_type")),
        })

    insert_df(conn, "players", pd.DataFrame(rows))
    conn.execute("""
        UPDATE players SET is_returnee = TRUE
        WHERE SPLIT_PART(player_id, '_S', 1) IN (
            SELECT SPLIT_PART(player_id, '_S', 1)
            FROM players GROUP BY SPLIT_PART(player_id, '_S', 1)
            HAVING COUNT(*) > 1
        )
    """)
    report("players", conn)


def load_tribes(conn, exports_path):
    log.info("Loading tribes...")
    df = read_csv(exports_path, "tribe_colours.csv")
    df = df[df["version"] == "US"].copy()

    rows = []
    for _, row in df.iterrows():
        sn = sint(row["season"])
        tn = sstr(row["tribe"])
        if not sn or not tn: continue
        sr = str(row.get("tribe_status","original")).lower()
        if "merge" in sr:       status = "merged"
        elif sr == "swapped2":  status = "swapped2"
        elif "swap" in sr:      status = "swapped"
        else:                   status = "original"
        rows.append({
            "tribe_id":          f"US{sn:02d}_{tn}",
            "season_id":         sn,
            "tribe_name":        tn,
            "color_hex":         sstr(row.get("tribe_colour")),
            "tribe_status":      status,
            "episode_formed":    None,
            "episode_dissolved": None,
        })

    out = pd.DataFrame(rows).drop_duplicates(subset=["tribe_id"], keep="last")
    insert_df(conn, "tribes", out)
    report("tribes", conn)


def load_tribe_memberships(conn, exports_path):
    log.info("Loading tribe memberships...")
    df = read_csv(exports_path, "tribe_mapping.csv")
    df = df[df["version"] == "US"].copy()
    df = df.sort_values(["castaway_id","season","episode"])

    rows = []
    for (pid, sn), grp in df.groupby(["castaway_id","season"]):
        grp = grp.sort_values("episode").reset_index(drop=True)
        current_tribe = None
        for i, ep_row in grp.iterrows():
            tn  = sstr(ep_row["tribe"])
            ep  = sint(ep_row["episode"])
            tid = f"US{int(sn):02d}_{tn}" if tn else None
            sr  = str(ep_row.get("tribe_status","")).lower()
            if tn != current_tribe:
                if current_tribe is not None:
                    rows[-1]["episode_left"] = ep
                reason = ("merge" if "merge" in sr
                          else "swap" if "swap" in sr
                          else "draft" if i == 0 else "swap")
                rows.append({
                    "player_id":      f"{pid}_S{int(sn)}",
                    "tribe_id":       tid,
                    "season_id":      int(sn),
                    "episode_joined": ep,
                    "episode_left":   None,
                    "reason_joined":  reason,
                })
                current_tribe = tn

    out = pd.DataFrame(rows).dropna(subset=["tribe_id"])
    out.insert(0, "id", range(1, len(out) + 1))
    insert_df(conn, "tribe_memberships", out)
    report("tribe_memberships", conn)


def load_episodes(conn, exports_path):
    log.info("Loading episodes...")
    df = read_csv(exports_path, "episodes.csv")
    df = df[df["version"] == "US"].copy()

    rows = []
    for _, row in df.iterrows():
        sn = sint(row["season"])
        ep = sint(row["episode"])
        if not sn or not ep: continue
        rows.append({
            "episode_id":           sn * 1000 + ep,
            "season_id":            sn,
            "episode_num":          ep,
            "episode_num_overall":  sint(row.get("episode_number_overall")),
            "title":                sstr(row.get("episode_title")),
            "air_date":             sstr(row.get("episode_date")),
            "runtime_mins":         sint(row.get("episode_length")),
            "merge_occurred":       False,
            "swap_occurred":        False,
            "double_elimination":   False,
            "recap_episode":        "recap" in str(row.get("episode_label","")).lower(),
            "n_players_start":      None,
            "n_players_end":        None,
        })

    insert_df(conn, "episodes", pd.DataFrame(rows))
    conn.execute("""
        UPDATE seasons SET n_episodes = (
            SELECT COUNT(*) FROM episodes e
            WHERE e.season_id = seasons.season_id AND e.recap_episode = FALSE
        )
    """)
    report("episodes", conn)


def load_tribal_councils(conn, exports_path):
    log.info("Loading tribal councils...")
    df = read_csv(exports_path, "vote_history.csv")
    df = df[df["version"] == "US"].copy()

    tcs = (df[df["vote_order"] == 1]
           .groupby(["season","episode","tribe","tribe_status"], dropna=False)
           .agg(n_attending=("castaway_id","nunique"))
           .reset_index())

    rows = []
    for i, row in enumerate(tcs.itertuples(), start=1):
        sn = sint(row.season)
        ep = sint(row.episode)
        tn = sstr(row.tribe)
        if not sn or not ep: continue
        sr = str(row.tribe_status or "").lower()
        rows.append({
            "tc_id":               i,
            "episode_id":          sn * 1000 + ep,
            "season_id":           sn,
            "tribe_id":            f"US{sn:02d}_{tn}" if tn else None,
            "tc_type":             "post_merge" if "merge" in sr else "pre_merge",
            "tc_order":            1,
            "n_players_attending": sint(row.n_attending),
            "is_jury_phase":       "merge" in sr,
        })

    insert_df(conn, "tribal_councils", pd.DataFrame(rows))
    report("tribal_councils", conn)


def load_votes(conn, exports_path):
    log.info("Loading votes...")
    df = read_csv(exports_path, "vote_history.csv")
    df = df[df["version"] == "US"].copy()

    tc_df = conn.execute("""
        SELECT tc_id, season_id, CAST(episode_id % 1000 AS INT) AS ep, tribe_id
        FROM tribal_councils
    """).df()
    tc_map = {}
    for _, r in tc_df.iterrows():
        tn = r["tribe_id"].split("_",1)[1] if pd.notna(r["tribe_id"]) and r["tribe_id"] else None
        tc_map[(int(r["season_id"]), int(r["ep"]), tn)] = int(r["tc_id"])

    rows = []
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        sn = sint(row["season"])
        ep = sint(row["episode"])
        tn = sstr(row.get("tribe"))
        if not sn or not ep: continue
        tc_id = tc_map.get((sn, ep, tn))
        if tc_id is None: continue

        imm = sstr(row.get("immunity","")) or ""
        if "hidden" in imm.lower():    itype = "hidden"
        elif "individual" in imm.lower(): itype = "individual"
        elif "shot" in imm.lower():    itype = "shot_in_dark"
        else:                          itype = None

        voted_out  = sbool(row.get("voted_out")) or False
        nullified  = sbool(row.get("nullified")) or False
        voted_for  = sstr(row.get("voted_out_id")) if voted_out else None
        voter_pid  = f"{sstr(row.get('castaway_id'))}_S{sn}"
        vf_pid     = f"{voted_for}_S{sn}" if voted_for else None

        rows.append({
            "vote_id":             i,
            "tc_id":               tc_id,
            "season_id":           sn,
            "episode_id":          sn * 1000 + ep,
            "voter_player_id":     voter_pid,
            "voted_for_player_id": vf_pid,
            "nullified":           nullified,
            "immunity_type":       itype,
            "vote_event":          sstr(row.get("vote_event")),
            "vote_event_outcome":  sstr(row.get("vote_event_outcome")),
            "is_revote":           (sint(row.get("vote_order",1)) or 1) > 1,
            "vote_order":          sint(row.get("vote_order")) or 1,
            "voted_out":           voted_out,
            "on_majority_side":    None,
        })

    insert_df(conn, "votes", pd.DataFrame(rows))
    report("votes", conn)


def load_challenges(conn, exports_path):
    log.info("Loading challenges...")
    df = read_csv(exports_path, "challenge_description.csv")
    df = df[df["version"] == "US"].copy()

    def fmt(row):
        if sbool(row.get("endurance")):  return "endurance"
        if sbool(row.get("puzzle")):     return "puzzle"
        if sbool(row.get("knowledge")) or sbool(row.get("memory")): return "knowledge"
        if sbool(row.get("balance")):    return "balance"
        if sbool(row.get("strength")) or sbool(row.get("race")): return "physical"
        if sbool(row.get("water_swim")): return "physical"
        return "hybrid"

    rows = []
    for _, row in df.iterrows():
        sn  = sint(row["season"])
        ep  = sint(row["episode"])
        cid = sint(row.get("challenge_id"))
        if not sn or not ep or cid is None: continue

        # Composite key: resets per season
        composite_cid = f"US{sn:02d}_{cid}"

        ct = sstr(row.get("challenge_type","")).lower()
        if "reward" in ct and "immunity" in ct: ctype = "reward_immunity"
        elif "immunity" in ct:                  ctype = "immunity"
        else:                                   ctype = "reward"

        rows.append({
            "challenge_id":            composite_cid,
            "episode_id":              sn * 1000 + ep,
            "season_id":               sn,
            "challenge_name":          sstr(row.get("name")),
            "challenge_type":          ctype,
            "is_individual":           False,
            "format":                  fmt(row),
            "has_physical_component":  bool(sbool(row.get("race")) or sbool(row.get("strength"))),
            "has_puzzle_component":    bool(sbool(row.get("puzzle"))),
            "has_endurance_component": bool(sbool(row.get("endurance"))),
            "has_balance_component":   bool(sbool(row.get("balance"))),
            "has_swimming_component":  bool(sbool(row.get("water_swim"))),
            "winner_tribe_id":         None,
            "winner_player_id":        None,
            "n_participants":          None,
            "second_place_tribe_id":   None,
            "third_place_tribe_id":    None,
        })

    # No dedup needed — composite_cid is now unique
    insert_df(conn, "challenges", pd.DataFrame(rows))
    report("challenges", conn)


def load_challenge_participants(conn, exports_path):
    log.info("Loading challenge participants...")
    df = read_csv(exports_path, "challenge_results.csv")
    df = df[df["version"] == "US"].copy()

    rows = []
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        sn  = sint(row["season"])
        cid = sint(row.get("challenge_id"))
        pid = sstr(row.get("castaway_id"))
        if not sn or cid is None or not pid: continue

        composite_cid = f"US{sn:02d}_{cid}"
        composite_pid = f"{pid}_S{sn}"
        tn  = sstr(row.get("tribe"))
        tid = f"US{sn:02d}_{tn}" if tn else None
        sat_out = sbool(row.get("sit_out")) or False
        won = any(sbool(row.get(c)) for c in [
            "won","won_tribal_reward","won_tribal_immunity",
            "won_team_reward","won_team_immunity",
            "won_individual_reward","won_individual_immunity","won_duel"
        ])

        otype = sstr(row.get("outcome_type","")).lower()
        if "individual" in otype:
            conn.execute(
                "UPDATE challenges SET is_individual=TRUE WHERE challenge_id=?",
                [composite_cid]
            )
            if won:
                conn.execute(
                    "UPDATE challenges SET winner_player_id=? WHERE challenge_id=?",
                    [composite_pid, composite_cid]
                )
        elif won and tid:
            conn.execute(
                "UPDATE challenges SET winner_tribe_id=? WHERE challenge_id=? AND winner_tribe_id IS NULL",
                [tid, composite_cid]
            )

        rows.append({
            "id":           i,
            "challenge_id": composite_cid,
            "player_id":    composite_pid,
            "season_id":    sn,
            "tribe_id":     tid,
            "participated": not sat_out,
            "sat_out":      sat_out,
            "won":          won,
            "placement":    sint(row.get("order_of_finish")),
        })

    insert_df(conn, "challenge_participants", pd.DataFrame(rows))
    report("challenge_participants", conn)


def load_advantages(conn, exports_path):
    log.info("Loading advantages...")
    details  = read_csv(exports_path, "advantage_details.csv")
    movement = read_csv(exports_path, "advantage_movement.csv")
    details  = details[details["version"] == "US"].copy()
    movement = movement[movement["version"] == "US"].copy()

    # Summarize movement per advantage (keyed by composite ID)
    mv = {}
    for _, row in movement.iterrows():
        raw_aid = sint(row.get("advantage_id"))
        sn      = sint(row.get("season"))
        if raw_aid is None or not sn: continue
        aid   = f"US{sn:02d}_{raw_aid}"
        event = str(row.get("event","") or "").lower()
        if aid not in mv:
            mv[aid] = {"found_by":None,"found_ep":None,"found_day":None,
                       "played_by":None,"played_ep":None,"played_for_id":None,
                       "current_holder":None,"votes_nullified":0,"success":None}
        s = mv[aid]
        pid = sstr(row.get("castaway_id"))
        spid = f"{pid}_S{sn}" if pid else None
        if "found" in event or "received" in event:
            s["found_by"] = s["current_holder"] = spid
            s["found_ep"] = sint(row.get("episode"))
            s["found_day"] = sint(row.get("day"))
        if "played" in event or "used" in event:
            s["played_by"]       = spid
            s["played_ep"]       = sint(row.get("episode"))
            s["played_for_id"]   = sstr(row.get("played_for_id"))
            s["success"]         = sbool(row.get("success"))
            s["votes_nullified"] = sint(row.get("votes_nullified")) or 0
        if "transfer" in event or "gave" in event:
            s["current_holder"] = spid

    def norm_type(raw):
        r = str(raw or "").lower()
        if "hidden" in r or ("idol" in r and "nullif" not in r): return "hidden_immunity_idol"
        if "extra" in r and "vote" in r: return "extra_vote"
        if "steal" in r: return "steal_a_vote"
        if "nullif" in r: return "idol_nullifier"
        if "legacy" in r: return "legacy_advantage"
        if "beware" in r: return "beware_advantage"
        if "shot" in r: return "shot_in_dark"
        if "boomerang" in r: return "boomerang_idol"
        if "super" in r: return "super_idol"
        if "safety" in r: return "safety_without_power"
        if "knowledge" in r: return "knowledge_is_power"
        return "other"

    # Get existing players for FK safety
    existing_players = set(
        r[0] for r in conn.execute("SELECT player_id FROM players").fetchall()
    )

    rows = []
    for _, row in details.iterrows():
        raw_aid = sint(row.get("advantage_id"))
        sn      = sint(row.get("season"))
        if raw_aid is None or not sn: continue
        aid = f"US{sn:02d}_{raw_aid}"
        s   = mv.get(aid, {})

        def safe_pid(p):
            return p if p in existing_players else None

        outcome = ("successful" if s.get("success") else "wasted") if s.get("played_by") else None
        rows.append({
            "advantage_id":             aid,
            "season_id":                sn,
            "advantage_type":           norm_type(row.get("advantage_type")),
            "found_by_player_id":       safe_pid(s.get("found_by")),
            "found_episode":            s.get("found_ep"),
            "found_day":                s.get("found_day"),
            "found_via_clue":           bool(sstr(row.get("clue_details"))),
            "current_holder_player_id": safe_pid(s.get("current_holder")),
            "played_by_player_id":      safe_pid(s.get("played_by")),
            "played_episode":           s.get("played_ep"),
            "played_at_tc_id":          None,
            "played_for_player_id":     safe_pid(s.get("played_for_id")),
            "votes_nullified":          s.get("votes_nullified", 0),
            "outcome":                  outcome,
        })

    insert_df(conn, "advantages", pd.DataFrame(rows))
    report("advantages", conn)


def load_confessionals(conn, exports_path):
    log.info("Loading confessionals...")
    df = read_csv(exports_path, "confessionals.csv")
    df = df[df["version"] == "US"].copy()

    rows = []
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        sn  = sint(row["season"])
        ep  = sint(row["episode"])
        pid = sstr(row.get("castaway_id"))
        if not sn or not ep or not pid: continue
        rows.append({
            "id":                 i,
            "player_id":          f"{pid}_S{sn}",
            "episode_id":         sn * 1000 + ep,
            "season_id":          sn,
            "confessional_count": sint(row.get("confessional_count")) or 0,
            "screen_time_sec":    sfloat(row.get("confessional_time")),
            "index_count":        sfloat(row.get("exp_count")),
            "index_time":         sfloat(row.get("exp_time")),
            "expected_count":     None,
            "expected_time":      None,
        })

    insert_df(conn, "confessionals", pd.DataFrame(rows))
    report("confessionals", conn)


def load_jury_votes(conn, exports_path):
    log.info("Loading jury votes...")
    df = read_csv(exports_path, "jury_votes.csv")
    df = df[df["version"] == "US"].copy()

    counts = (df[df["vote"] == 1]
              .groupby(["finalist_id","season"])
              .size().reset_index(name="jury_votes"))

    for _, row in counts.iterrows():
        sn  = sint(row["season"])
        pid = f"{sstr(row['finalist_id'])}_S{sn}"
        conn.execute(
            "UPDATE players SET jury_votes_received=? WHERE player_id=? AND season_id=?",
            [sint(row["jury_votes"]), pid, sn]
        )

    total = conn.execute("SELECT SUM(jury_votes_received) FROM players").fetchone()[0] or 0
    log.info(f"  [OK] jury_votes: {total:,} total votes distributed")


# =============================================================================
# VALIDATION
# =============================================================================

def validate(conn):
    log.info("\nValidation checks:")
    checks = [
        ("seasons >= 49",        "SELECT COUNT(*) FROM seasons WHERE season_num >= 49",     lambda n: n >= 1),
        ("players > 700",        "SELECT COUNT(*) FROM players",                             lambda n: n > 700),
        ("votes > 5000",         "SELECT COUNT(*) FROM votes",                               lambda n: n > 5000),
        ("no votes missing tc",  "SELECT COUNT(*) FROM votes WHERE tc_id IS NULL",           lambda n: n == 0),
        ("tribe memberships S1", "SELECT COUNT(*) FROM tribe_memberships WHERE season_id=1", lambda n: n > 0),
        ("confessionals loaded", "SELECT COUNT(*) FROM confessionals",                       lambda n: n > 1000),
        ("challenges loaded",    "SELECT COUNT(*) FROM challenges",                          lambda n: n > 500),
        ("no orphaned players",
         "SELECT COUNT(*) FROM players p LEFT JOIN seasons s ON p.season_id=s.season_id WHERE s.season_id IS NULL",
         lambda n: n == 0),
    ]
    passed = True
    for name, q, check in checks:
        n = conn.execute(q).fetchone()[0]
        ok = check(n)
        log.info(f"  [{'PASS' if ok else 'FAIL'}] {name}: {n}")
        if not ok: passed = False
    return passed


# =============================================================================
# MAIN
# =============================================================================

@click.command()
@click.option("--config",        default="config.yaml")
@click.option("--reset",         is_flag=True, help="Delete and recreate DB file")
@click.option("--validate-only", is_flag=True)
@click.option("--table",         default=None)
def main(config, reset, validate_only, table):
    """Load survivoR historical data into DuckDB."""

    if reset:
        from survivor_fantasy.db.connect import load_config
        db_path = Path(load_config(config)["db_path"])
        if db_path.exists():
            db_path.unlink()
            log.info(f"Deleted {db_path}")
        wal = db_path.with_suffix(".duckdb.wal")
        if wal.exists():
            wal.unlink()

    conn         = get_connection(config)
    exports_path = get_exports_path(config)

    if validate_only:
        raise SystemExit(0 if validate(conn) else 1)

    log.info("Creating schema...")
    create_all_tables(conn)
    log.info(f"\nIngesting from: {exports_path}\n")

    loaders = {
        "seasons":                load_seasons,
        "players":                load_players,
        "tribes":                 load_tribes,
        "tribe_memberships":      load_tribe_memberships,
        "episodes":               load_episodes,
        "tribal_councils":        load_tribal_councils,
        "votes":                  load_votes,
        "challenges":             load_challenges,
        "challenge_participants": load_challenge_participants,
        "advantages":             load_advantages,
        "confessionals":          load_confessionals,
        "jury_votes":             load_jury_votes,
    }

    if table:
        if table not in loaders:
            log.error(f"Unknown table: {table}. Options: {list(loaders.keys())}")
            raise SystemExit(1)
        loaders[table](conn, exports_path)
    else:
        for fn in loaders.values():
            fn(conn, exports_path)
        ok = validate(conn)
        conn.close()
        if ok:
            log.info("\nIngestion complete. Run `make build` next.")
        else:
            log.error("\nIngestion completed with failures.")
            raise SystemExit(1)
        return

    conn.close()


if __name__ == "__main__":
    main()
