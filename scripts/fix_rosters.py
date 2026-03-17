"""
fix_rosters.py - cleans up rosters.csv in place
Run from project root: python fix_rosters.py
"""
import csv
from pathlib import Path

BUFFS_MANAGERS = ['Amy','Lindsay Beaty','Lo','Jimmy Winslow','Natalie Bailey','Chris Roth','Joe','The Merpenters','rachel fagan']
FJV_MANAGERS = ['Jimmy Winslow','Sidney','Austin Dickman','Kaitlynn Durham','Alec Hartman']

PATH = Path('data/season50/rosters.csv')

text = PATH.read_text(encoding='utf-8-sig')
rows = list(csv.DictReader(text.splitlines()))
print(f'Read {len(rows)} rows')

buffs = [r for r in rows if r['league'] == 'In the Buffs League']
fjv   = [r for r in rows if r['league'] == 'FJV Survivor Heads League']
print(f'Buffs: {len(buffs)} rows | FJV: {len(fjv)} rows')

def fix_name(name):
    name = name.replace(' Profile', '')
    # fix mojibake for smart quotes
    name = name.encode('latin-1', errors='replace').decode('utf-8', errors='replace')
    name = name.replace('\u201c', '"').replace('\u201d', '"')
    return name.strip()

def assign(league_rows, managers):
    for i, row in enumerate(league_rows):
        row['manager'] = managers[i // 8] if i // 8 < len(managers) else f'Unknown_{i//8}'
        row['contestant_name'] = fix_name(row['contestant_name'])
    return league_rows

all_rows = assign(buffs, BUFFS_MANAGERS) + assign(fjv, FJV_MANAGERS)

with open(PATH, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['league','manager','contestant_name','contestant_uuid'])
    w.writeheader()
    w.writerows(all_rows)

print(f'Wrote {len(all_rows)} rows to {PATH}')
print()
current = None
for r in all_rows:
    if r['manager'] != current:
        current = r['manager']
        print(f"[{r['league']}] {r['manager']}:")
    print(f"  {r['contestant_name']}")
