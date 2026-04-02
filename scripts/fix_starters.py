"""
scripts/fix_starters.py - One-time fix for ep6 starters.csv errors:
1. Austin Dickman had Jimmy's data duplicated - keep only his real 8
2. Buffs managers were written with FJV league - fix to correct league
"""

import csv
from pathlib import Path

STARTERS_CSV = Path('data/season50/starters.csv')
HEADER = ['episode', 'league', 'manager', 'player_name', 'player_uuid', 'is_starter']

BUFFS_MANAGERS = {
    'Lindsay Beaty', 'Lo', 'Natalie Bailey', 'Joe',
    'The Merpenters', 'Chris Roth', 'rachel fagan', 'Amy'
}

# Austin's real ep6 picks (from the console script output)
AUSTIN_REAL = [
    ('042ee802', '1'),  # Rizo Velovic - starter
    ('ff3e1c53', '1'),  # Joe Hunter - starter
    ('bbf825b0', '1'),  # Kamilla Karthigesu - starter
    ('1e8e16fa', '1'),  # Christian Hubicki - starter
    ('8682d041', '1'),  # Genevieve Mushaluk - starter
    ('ab8ea829', '0'),  # Charlie Davis - bench
    ('20b068a6', '0'),  # Mike White - bench
    ('3376a067', '0'),  # Cirie Fields - bench
]

NAME_MAP = {
    '042ee802': 'Rizo Velovic',
    'ff3e1c53': 'Joseph "Joe" Hunter',
    'bbf825b0': 'Kamilla Karthigesu',
    '1e8e16fa': 'Christian Hubicki',
    '8682d041': 'Genevieve Mushaluk',
    'ab8ea829': 'Charlie Davis',
    '20b068a6': 'Mike White',
    '3376a067': 'Cirie Fields',
}

rows = list(csv.DictReader(STARTERS_CSV.open(encoding='utf-8')))

fixed = []
for row in rows:
    ep = row['episode']
    manager = row['manager']
    league = row['league']

    # Skip ep6 Austin rows entirely - we'll rebuild them
    if ep == '6' and manager == 'Austin Dickman':
        continue

    # Fix Buffs managers written with wrong league
    if ep == '6' and manager in BUFFS_MANAGERS and league == 'FJV Survivor Heads League':
        row['league'] = 'In the Buffs League'

    fixed.append(row)

# Add Austin's correct ep6 rows
for uuid, is_starter in AUSTIN_REAL:
    fixed.append({
        'episode': '6',
        'league': 'FJV Survivor Heads League',
        'manager': 'Austin Dickman',
        'player_name': NAME_MAP[uuid],
        'player_uuid': uuid,
        'is_starter': is_starter,
    })

# Write back
with STARTERS_CSV.open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=HEADER)
    writer.writeheader()
    writer.writerows(fixed)

print(f"Done: {len(fixed)} rows written")

# Verify
print("\nEp6 row counts per manager:")
ep6 = [r for r in fixed if r['episode'] == '6']
managers = {}
for r in ep6:
    key = f"{r['manager']} ({r['league'][:3]})"
    managers[key] = managers.get(key, 0) + 1
for k, v in sorted(managers.items()):
    status = "OK" if v == 8 else f"ERROR: {v} rows"
    print(f"  {status}  {k}")
