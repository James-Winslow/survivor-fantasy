"""
scripts/fix_events.py

1. Adds new columns to events.csv:
   - received_boomerang_idol  (scoring: +3)
   - received_extra_vote      (scoring: +3)
   - made_fake_idol           (scoring: +2)
   - journey                  (scoring: +1)
   - found_twist              (scoring: +3)

2. Fixes wrong existing entries:
   - Genevieve ep1/ep4: found_hidden_idol=1 → found_idol_clue=1 (boomerang found = clue, not idol)
   - Christian ep2: found_hidden_idol=1 → found_idol_clue=1
   - Aubry ep2: found_idol_clue=1 → 0, received_boomerang_idol=1
   - Rizo ep4: found_idol_clue=1 → 0, received_boomerang_idol=1
   - Ozzy ep1: found_idol_clue=1 → 0, received_boomerang_idol=1, received_extra_vote=1

3. Adds missing events:
   - Journey participants ep1: Coach, Ozzy, Q, Mike, Colby, Savannah
   - Savannah ep1: wins advantage → received_extra_vote=1 (closest field)
   - Rick ep2: made_fake_idol=1
   - Ozzy ep6: found_twist=1

Usage:
    python scripts/fix_events.py
"""

import csv
from pathlib import Path

EVENTS_CSV = Path('data/season50/events.csv')
BACKUP_CSV = Path('data/season50/events_backup.csv')

OLD_HEADER = [
    'season','episode','player_name','still_in_game','tribe_name','merge_status',
    'attended_tc','voted_out','votes_received','had_individual_immunity',
    'tribe_won_immunity','tribe_immunity_place','reward_participant',
    'won_individual_reward','found_idol_clue','found_hidden_idol','played_idol',
    'played_idol_for','voted_out_holding_idol','lost_vote','quit','medevac',
    'received_jury_vote','sole_survivor','confessional_count'
]

NEW_HEADER = OLD_HEADER[:-1] + [
    'received_boomerang_idol',
    'received_extra_vote',
    'made_fake_idol',
    'journey',
    'found_twist',
    'confessional_count',  # moved to end
]

# Fixes: (episode, player_name_contains) -> {field: value}
FIXES = {
    # Genevieve ep1: boomerang found = clue (+1), not idol (+3)
    (1, 'Genevieve'):   {'found_hidden_idol': '0', 'found_idol_clue': '1'},
    # Genevieve ep4: same
    (4, 'Genevieve'):   {'found_hidden_idol': '0', 'found_idol_clue': '1'},
    # Christian ep2: same
    (2, 'Christian'):   {'found_hidden_idol': '0', 'found_idol_clue': '1'},
    # Aubry ep2: received boomerang (not found clue)
    (2, 'Aubry'):       {'found_idol_clue': '0', 'received_boomerang_idol': '1'},
    # Rizo ep4: received boomerang (not found clue)
    (4, 'Rizo'):        {'found_idol_clue': '0', 'received_boomerang_idol': '1'},
    # Ozzy ep1: received boomerang + extra vote (not found clue)
    (1, 'Ozzy'):        {'found_idol_clue': '0', 'received_boomerang_idol': '1',
                         'received_extra_vote': '1', 'journey': '1'},
    # Savannah ep1: won advantage on journey
    (1, 'Savannah'):    {'journey': '1', 'received_extra_vote': '1'},
    # Coach ep1: journey
    (1, 'Coach'):       {'journey': '1'},
    # Q ep1: journey
    (1, 'Q Burdette'):  {'journey': '1'},
    # Mike ep1: journey
    (1, 'Mike'):        {'journey': '1'},
    # Colby ep1: journey
    (1, 'Colby'):       {'journey': '1'},
    # Rick ep2: made fake idol
    (2, 'Rick'):        {'made_fake_idol': '1'},
    # Ozzy ep6: found twist
    (6, 'Ozzy'):        {'found_twist': '1'},
}

def find_fix(ep, player_name):
    ep = int(ep)
    for (fix_ep, name_contains), changes in FIXES.items():
        if fix_ep == ep and name_contains.lower() in player_name.lower():
            return changes
    return {}


def main():
    # Backup
    import shutil
    shutil.copy(EVENTS_CSV, BACKUP_CSV)
    print(f'Backed up to {BACKUP_CSV}')

    rows = list(csv.DictReader(EVENTS_CSV.open(encoding='utf-8-sig')))
    print(f'Read {len(rows)} rows')

    fixed_rows = []
    changes_made = 0

    for row in rows:
        # Add new columns with default 0
        row['received_boomerang_idol'] = '0'
        row['received_extra_vote']     = '0'
        row['made_fake_idol']          = '0'
        row['journey']                 = '0'
        row['found_twist']             = '0'

        # Apply fixes
        fix = find_fix(row['episode'], row['player_name'])
        if fix:
            for field, val in fix.items():
                old = row.get(field, '0')
                row[field] = val
                if old != val:
                    print(f"  ep{row['episode']} {row['player_name']}: "
                          f"{field} {old}→{val}")
                    changes_made += 1

        fixed_rows.append(row)

    # Write back
    with EVENTS_CSV.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=NEW_HEADER)
        writer.writeheader()
        writer.writerows(fixed_rows)

    print(f'\nDone: {changes_made} field changes across {len(fixed_rows)} rows')
    print(f'New columns added: received_boomerang_idol, received_extra_vote, '
          f'made_fake_idol, journey, found_twist')
    print(f'\nVerify with: head -1 data/season50/events.csv')


if __name__ == '__main__':
    main()
