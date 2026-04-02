"""
scripts/batch_starters.py

Takes the JSON output from the working console script and writes
all managers' starter/bench data to starters.csv in one shot.

Usage:
    python scripts/batch_starters.py --episode 6 --league FJV
    python scripts/batch_starters.py --episode 6 --league Buffs

Then paste the JSON when prompted.
"""

import csv
import json
import sys
import argparse
from pathlib import Path

ROSTERS_CSV  = Path('data/season50/rosters.csv')
STARTERS_CSV = Path('data/season50/starters.csv')
STARTERS_HEADER = ['episode', 'league', 'manager', 'player_name', 'player_uuid', 'is_starter']

LEAGUE_MAP = {
    'fjv':   'FJV Survivor Heads League',
    'buffs': 'In the Buffs League',
    'FJV':   'FJV Survivor Heads League',
    'Buffs': 'In the Buffs League',
}


def load_uuid_map():
    mapping = {}
    for row in csv.DictReader(ROSTERS_CSV.open(encoding='utf-8-sig')):
        prefix = row.get('contestant_uuid', '').replace('-', '')[:8]
        mapping[prefix] = row['contestant_name']
    return mapping


def load_existing():
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--episode', required=True, help='Episode number')
    parser.add_argument('--league', required=True, help='FJV or Buffs')
    args = parser.parse_args()

    league = LEAGUE_MAP.get(args.league, args.league)
    episode = args.episode

    uuid_map = load_uuid_map()
    existing = load_existing()
    ensure_header()

    print()
    print(f'batch_starters.py — ep{episode} {league}')
    print('=' * 50)
    print('Paste JSON from console script (press Enter twice when done):')

    lines = []
    while True:
        line = input()
        if line == '':
            if lines:
                break
        else:
            lines.append(line)

    try:
        data = json.loads('\n'.join(lines))
    except Exception as e:
        print(f'ERROR parsing JSON: {e}')
        sys.exit(1)

    written = 0
    skipped = 0
    unknown = 0

    with STARTERS_CSV.open('a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=STARTERS_HEADER)

        for manager, rosters in data.items():
            # Handle both formats:
            # {manager: [uuid1..uuid8]} (flat list, first 5 = starters)
            # {manager: {starters:[], bench:[]}} (explicit)
            if isinstance(rosters, list):
                starters = rosters[:5]
                bench    = rosters[5:]
            else:
                starters = rosters.get('starters', [])
                bench    = rosters.get('bench', [])
            all_picks = [(u, True) for u in starters] + [(u, False) for u in bench]

            print(f'\n  {manager}:')
            for uuid_prefix, is_starter in all_picks:
                clean = uuid_prefix.replace('-', '')[:8]
                name  = uuid_map.get(clean)
                if not name:
                    print(f'    ??? {uuid_prefix} — not in rosters.csv')
                    unknown += 1
                    continue

                key = (episode, manager, uuid_prefix)
                if key in existing:
                    skipped += 1
                    continue

                writer.writerow({
                    'episode':     episode,
                    'league':      league,
                    'manager':     manager,
                    'player_name': name,
                    'player_uuid': uuid_prefix,
                    'is_starter':  '1' if is_starter else '0',
                })
                label = 'START' if is_starter else 'bench'
                print(f'    {label}  {name}')
                written += 1

    print()
    print(f'Done: {written} written, {skipped} already existed, {unknown} unknown UUIDs')
    print()


if __name__ == '__main__':
    main()
