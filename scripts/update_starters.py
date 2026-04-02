"""
scripts/update_starters.py

Converts the console script JSON output from tribal-council.com into
rows in data/season50/starters.csv.

Usage:
    python scripts/update_starters.py

You will be prompted for:
  - The episode number
  - The manager name
  - The JSON from the console script (paste and hit Enter twice)

Run once per manager per episode. The UUID→name mapping is loaded
from data/season50/rosters.csv automatically.

starters.csv schema:
  episode, league, manager, player_name, player_uuid, is_starter
"""

import csv
import json
import sys
from pathlib import Path

ROSTERS_CSV  = Path('data/season50/rosters.csv')
STARTERS_CSV = Path('data/season50/starters.csv')

STARTERS_HEADER = ['episode', 'league', 'manager', 'player_name', 'player_uuid', 'is_starter']


def load_uuid_map():
    """Build uuid_prefix → (name, league) from rosters.csv."""
    if not ROSTERS_CSV.exists():
        print(f'ERROR: {ROSTERS_CSV} not found')
        sys.exit(1)
    mapping = {}
    for row in csv.DictReader(ROSTERS_CSV.open(encoding='utf-8-sig')):
        uuid = row.get('contestant_uuid', '').replace('-', '')[:8]
        mapping[uuid] = (row['contestant_name'], row['league'])
    return mapping


def load_existing_starters():
    """Load existing starters.csv rows as a set of (episode, manager, uuid)."""
    existing = set()
    if not STARTERS_CSV.exists():
        return existing
    for row in csv.DictReader(STARTERS_CSV.open(encoding='utf-8-sig')):
        existing.add((row['episode'], row['manager'], row['player_uuid']))
    return existing


def ensure_header():
    if not STARTERS_CSV.exists():
        with STARTERS_CSV.open('w', newline='', encoding='utf-8') as f:
            csv.DictWriter(f, fieldnames=STARTERS_HEADER).writeheader()
        print(f'Created {STARTERS_CSV}')


def main():
    uuid_map  = load_uuid_map()
    existing  = load_existing_starters()
    ensure_header()

    print()
    print('update_starters.py — append bench/starter data')
    print('=' * 50)
    print()

    episode = input('Episode number: ').strip()
    league  = input('League name (FJV / Buffs): ').strip()
    if 'fjv' in league.lower() or 'heads' in league.lower():
        league = 'FJV Survivor Heads League'
    elif 'buff' in league.lower():
        league = 'In the Buffs League'
    manager = input('Manager name (exact): ').strip()

    print()
    print('Paste JSON from console script (press Enter twice when done):')
    lines = []
    while True:
        line = input()
        if line == '':
            break
        lines.append(line)
    raw = '\n'.join(lines)

    try:
        data = json.loads(raw)
        # Handle both {starters:[], bench:[]} and {"Unknown":{starters:[], bench:[]}}
        if 'starters' not in data:
            data = list(data.values())[0]
        starters = data.get('starters', [])
        bench    = data.get('bench', [])
    except Exception as e:
        print(f'ERROR parsing JSON: {e}')
        sys.exit(1)

    rows_written = 0
    rows_skipped = 0

    with STARTERS_CSV.open('a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=STARTERS_HEADER)

        for uuid_prefix, is_starter in [(u, True) for u in starters] + [(u, False) for u in bench]:
            uuid_clean = uuid_prefix.replace('-', '')[:8]
            if uuid_clean not in uuid_map:
                print(f'  WARNING: UUID {uuid_prefix} not in rosters.csv — skipping')
                continue

            name, _ = uuid_map[uuid_clean]
            key = (episode, manager, uuid_prefix)
            if key in existing:
                rows_skipped += 1
                continue

            writer.writerow({
                'episode':      episode,
                'league':       league,
                'manager':      manager,
                'player_name':  name,
                'player_uuid':  uuid_prefix,
                'is_starter':   '1' if is_starter else '0',
            })
            status = 'STARTER' if is_starter else 'bench  '
            print(f'  {status}  {name}')
            rows_written += 1

    print()
    print(f'Done: {rows_written} rows written, {rows_skipped} already existed')
    print()

    # Prompt for another manager
    again = input('Add another manager? (y/n): ').strip().lower()
    if again == 'y':
        main()


if __name__ == '__main__':
    main()
