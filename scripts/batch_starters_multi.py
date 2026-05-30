"""
scripts/batch_starters_multi.py

Accepts multi-episode JSON from the console script and writes all
episodes to starters.csv in one shot.

Usage:
    python scripts/batch_starters_multi.py --league Buffs
    python scripts/batch_starters_multi.py --league FJV

Then paste the JSON when prompted (Enter twice to finish).
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
        full = row.get('contestant_uuid', '')
        prefix = full.replace('-', '')[:8]
        mapping[full] = row['contestant_name']
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
    parser.add_argument('--league', required=True, help='FJV or Buffs')
    parser.add_argument('--file', required=True, help='Path to JSON file')
    args = parser.parse_args()

    league = LEAGUE_MAP.get(args.league, args.league)
    uuid_map = load_uuid_map()
    existing = load_existing()
    ensure_header()

    print(f'\nbatch_starters_multi.py — {league}')
    content = Path(args.file).read_text(encoding='utf-8')
    json_start = content.find('{')
    if json_start == -1:
        print('ERROR: no JSON object found in file')
        sys.exit(1)
    raw = content[json_start:].strip()

    try:
        data = json.loads(raw)
    except Exception as e:
        print(f'ERROR parsing JSON: {e}')
        sys.exit(1)

    written = skipped = unknown = 0

    with STARTERS_CSV.open('a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=STARTERS_HEADER)

        for ep_str, managers in sorted(data.items(), key=lambda x: int(x[0])):
            episode = str(ep_str)
            print(f'\n  Episode {episode}:')

            for manager, rosters in managers.items():
                if isinstance(rosters, list):
                    starters = rosters[:5]
                    bench    = rosters[5:]
                else:
                    starters = rosters.get('starters', [])
                    bench    = rosters.get('bench', [])

                all_picks = [(u, True) for u in starters] + [(u, False) for u in bench]
                if not all_picks:
                    continue

                print(f'    {manager}:')
                for uuid_val, is_starter in all_picks:
                    clean_prefix = uuid_val.replace('-', '')[:8]
                    name = uuid_map.get(uuid_val) or uuid_map.get(clean_prefix)

                    if not name:
                        print(f'      ??? {uuid_val} — not in rosters.csv')
                        unknown += 1
                        continue

                    key = (episode, manager, uuid_val)
                    if key in existing:
                        skipped += 1
                        continue

                    writer.writerow({
                        'episode':     episode,
                        'league':      league,
                        'manager':     manager,
                        'player_name': name,
                        'player_uuid': uuid_val,
                        'is_starter':  '1' if is_starter else '0',
                    })
                    label = 'START' if is_starter else 'bench'
                    print(f'      {label}  {name}')
                    written += 1

    print(f'\nDone: {written} written, {skipped} already existed, {unknown} unknown UUIDs')


if __name__ == '__main__':
    main()