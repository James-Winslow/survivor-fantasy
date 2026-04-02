"""
status.py — Run at the start of any session on any machine.
Tells you exactly where the project stands and what needs doing.

Usage:
    python status.py
"""

import subprocess
import csv
from pathlib import Path
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────

EPISODES = [
    (1,  'Epic Party',              '2026-02-25'),
    (2,  'Therapy Carousel',        '2026-03-04'),
    (3,  'Did You Vote For a Swap?','2026-03-11'),
    (4,  'Knife to the Heart',      '2026-03-18'),
    (5,  'Open Wounds',             '2026-03-25'),
    (6,  'The Blood Moon',          '2026-04-01'),
    (7,  'TBD',                     '2026-04-08'),
    (8,  'TBD',                     '2026-04-15'),
    (9,  'TBD',                     '2026-04-22'),
    (10, 'TBD',                     '2026-04-29'),
    (11, 'TBD',                     '2026-05-06'),
    (12, 'TBD',                     '2026-05-13'),
    (13, 'TBD',                     '2026-05-20'),
]

EVENTS_CSV   = Path('data/season50/events.csv')
ROSTERS_CSV  = Path('data/season50/rosters.csv')
STARTERS_CSV = Path('data/season50/starters.csv')
DB_PATH      = Path('data/survivor.duckdb')

# ── Helpers ───────────────────────────────────────────────────────────────────

def git(cmd):
    try:
        return subprocess.check_output(
            f'git {cmd}', shell=True, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return None

def file_mtime(path):
    if not path.exists():
        return None
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')

def latest_episode_in_events():
    if not EVENTS_CSV.exists():
        return None
    try:
        rows = list(csv.DictReader(EVENTS_CSV.open(encoding='utf-8-sig')))
        eps = [int(r['episode']) for r in rows if r.get('episode','').isdigit()]
        return max(eps) if eps else None
    except Exception:
        return None

def latest_episode_aired():
    today = datetime.now().date()
    latest = None
    for num, title, date_str in EPISODES:
        air = datetime.strptime(date_str, '%Y-%m-%d').date()
        if air <= today:
            latest = (num, title, date_str)
    return latest

def dashboard_last_push():
    log = git('log --oneline docs/buffs.html | head -1')
    if not log:
        return None, None
    hash_msg = log.split(' ', 1)
    msg = hash_msg[1] if len(hash_msg) > 1 else ''
    date = git(f'log -1 --format=%ci docs/buffs.html')
    if date:
        date = date[:10]
    return date, msg

def latest_starters_episode():
    if not STARTERS_CSV.exists():
        return None
    try:
        rows = list(csv.DictReader(STARTERS_CSV.open(encoding='utf-8-sig')))
        eps = [int(r['episode']) for r in rows if r.get('episode','').isdigit()]
        return max(eps) if eps else None
    except Exception:
        return None

# ── Colors ───────────────────────────────────────────────────────────────────

G  = '\033[92m'   # green
Y  = '\033[93m'   # yellow
R  = '\033[91m'   # red
B  = '\033[96m'   # cyan/blue
DIM = '\033[2m'
BOLD = '\033[1m'
END = '\033[0m'

def ok(s):    return f'{G}✓ {s}{END}'
def warn(s):  return f'{Y}⚠ {s}{END}'
def err(s):   return f'{R}✗ {s}{END}'
def info(s):  return f'{B}{s}{END}'

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print()
    print(f'{BOLD}━━━ survivor-fantasy status ━━━{END}')
    print()

    # Git state
    branch   = git('branch --show-current') or '?'
    ahead    = git('rev-list --count @{u}..HEAD 2>/dev/null') or '0'
    last_commit = git('log -1 --format="%h %s (%ci)"') or '?'
    print(f'  {DIM}branch:{END}      {branch}')
    print(f'  {DIM}last commit:{END} {last_commit[:80]}')
    if int(ahead) > 0:
        print(f'  {warn(f"{ahead} commit(s) not yet pushed")}')
    else:
        print(f'  {ok("up to date with origin")}')
    print()

    # Episode state
    aired = latest_episode_aired()
    ep_in_events = latest_episode_in_events()
    dash_date, dash_msg = dashboard_last_push()
    ep_in_starters = latest_starters_episode()

    if aired:
        ep_num, ep_title, ep_date = aired
        print(f'  {DIM}latest aired:{END}    Ep{ep_num} "{ep_title}" ({ep_date})')
    else:
        print(f'  {DIM}latest aired:{END}    none yet')

    if ep_in_events:
        if ep_in_events >= ep_num:
            print(f'  {ok(f"events.csv current through ep{ep_in_events}")}')
        else:
            print(f'  {err(f"events.csv only through ep{ep_in_events} — ep{ep_num} data missing!")}')
    else:
        print(f'  {err("events.csv not found — data/ directory may be missing")}')

    if ep_in_starters:
        if ep_in_starters >= ep_num:
            print(f'  {ok(f"starters.csv current through ep{ep_in_starters}")}')
        else:
            print(f'  {warn(f"starters.csv only through ep{ep_in_starters} — run console script for ep{ep_num}")}')
    else:
        print(f'  {warn("starters.csv not found — bench data not yet collected")}')

    if dash_date:
        if dash_date >= ep_date:
            print(f'  {ok(f"dashboard pushed {dash_date}: {dash_msg[:50]}")}')
        else:
            print(f'  {err(f"dashboard last pushed {dash_date} — needs update for ep{ep_num}!")}')
    else:
        print(f'  {err("dashboard never pushed")}')

    print()

    # Data files
    print(f'  {DIM}data files:{END}')
    for path, label in [
        (DB_PATH,      'survivor.duckdb'),
        (EVENTS_CSV,   'events.csv     '),
        (ROSTERS_CSV,  'rosters.csv    '),
        (STARTERS_CSV, 'starters.csv   '),
    ]:
        if path.exists():
            mtime = file_mtime(path)
            size  = f'{path.stat().st_size:,} bytes'
            print(f'    {ok(label)}  {DIM}{mtime}  {size}{END}')
        else:
            print(f'    {err(label)}  NOT FOUND')

    print()

    # Actions needed
    actions = []
    if not EVENTS_CSV.exists():
        actions.append('Create data/season50/ and copy events.csv from other machine')
    elif ep_in_events and ep_in_events < ep_num:
        actions.append(f'Add ep{ep_num} rows to data/season50/events.csv')
        actions.append(f'Add ep{ep_num} to EPISODES list in ingest_s50.py')
    if not ep_in_starters or ep_in_starters < ep_num:
        actions.append(f'Run console script on tribal-council.com for ep{ep_num} starters')
        actions.append(f'Append output to data/season50/starters.csv')
    if dash_date and dash_date < ep_date:
        actions.append('Run pipeline: ingest_s50.py → scorer.py → publish.py')
        actions.append('git add docs/buffs.html docs/fjv.html && git commit && git push')

    if actions:
        print(f'  {BOLD}Actions needed:{END}')
        for i, a in enumerate(actions, 1):
            print(f'    {Y}{i}.{END} {a}')
    else:
        print(f'  {G}{BOLD}All good — nothing to do!{END}')

    print()

if __name__ == '__main__':
    main()
