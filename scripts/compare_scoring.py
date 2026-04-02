"""
scripts/compare_scoring.py

Compares our events.csv scoring against the tribal-council.com
episode feed to identify missing events and point gaps.

Usage:
    python scripts/compare_scoring.py
"""

import csv
from pathlib import Path
from collections import defaultdict

FEED_CSV   = Path('data/season50/episode_feed.csv')
EVENTS_CSV = Path('data/season50/events.csv')

# Our scoring rules (pts per event type)
OUR_SCORING = {
    'survived_pre_merge':           3,
    'survived_post_merge':          6,
    'team_immunity':                2,
    'team_immunity_first_place_bonus': 1,
    'reward_participant':           2,
    'wins_individual_immunity':     6,
    'wins_individual_reward':       4,
    'finds_hidden_idol':            3,
    'gets_idol_clue':               1,
    'plays_idol_successfully':      6,
    'voted_out_holding_idol':      -6,
    'loses_vote':                  -3,
    'player_quits':                -8,
    'medical_removal':              8,
    'jury_vote':                   10,
    'sole_survivor':               20,
}

# Map TC event text patterns to our event types
TC_TO_OURS = {
    'survived a round':         'survived',
    'wins tribe reward':        'reward',
    'wins team reward':         'reward',
    'wins tribe immunity':      'immunity',
    'wins tribe reward and immunity': 'reward+immunity',
    'picked for journey':       'journey',      # MISSING from our system
    'gets extra vote':          'extra_vote',   # MISSING
    'given boomerang idol':     'boomerang_received',  # MISSING
    'finds boomerang idol':     'boomerang_found',
    'wins advantage':           'advantage',    # MISSING
    'makes fake idol':          'fake_idol',    # MISSING
    'medical removal':          'medical_removal',
    'wins individual immunity': 'individual_immunity',
    'immunity by default':      'individual_immunity',
    'participates in reward':   'reward_participant',
    'finds twist':              'twist',        # MISSING
}


def load_feed():
    """Load episode_feed.csv — TC's ground truth scoring."""
    if not FEED_CSV.exists():
        print(f'ERROR: {FEED_CSV} not found — run parse_episodes.py first')
        return []
    return list(csv.DictReader(FEED_CSV.open(encoding='utf-8')))


def load_our_events():
    """Load events.csv and compute per-player per-episode points."""
    if not EVENTS_CSV.exists():
        print(f'ERROR: {EVENTS_CSV} not found')
        return []
    return list(csv.DictReader(EVENTS_CSV.open(encoding='utf-8-sig')))


def summarize_tc_by_player(feed):
    """Sum TC points by player across all episodes."""
    totals = defaultdict(int)
    by_ep  = defaultdict(lambda: defaultdict(int))
    for row in feed:
        ep    = int(row['episode'])
        name  = row['player_name']
        pts   = int(row['points'])
        if name:
            totals[name] += pts
            by_ep[name][ep] += pts
    return totals, by_ep


def summarize_missing_events(feed):
    """Find event types in TC feed that we don't score."""
    missing = defaultdict(list)
    for row in feed:
        text = row['event_text'].lower()
        pts  = int(row['points'])
        name = row['player_name'] or '[tribe]'
        ep   = row['episode']

        matched = False
        for pattern, event_type in TC_TO_OURS.items():
            if pattern in text:
                if event_type in ('journey', 'extra_vote', 'boomerang_received',
                                  'advantage', 'fake_idol', 'twist'):
                    missing[event_type].append(
                        f"  ep{ep} {name}: {row['event_text']} (+{pts})"
                    )
                matched = True
                break

        if not matched and not row['is_tribe_event'] == '1':
            missing['unmatched'].append(
                f"  ep{ep} {name}: {row['event_text']} (+{pts})"
            )

    return missing


def main():
    feed   = load_feed()
    events = load_our_events()

    if not feed:
        return

    print('═' * 60)
    print('SCORING GAP ANALYSIS')
    print('tribal-council.com vs our events.csv')
    print('═' * 60)

    # Missing event types
    missing = summarize_missing_events(feed)

    print('\n── Events in TC feed NOT in our system ──────────────────')
    missing_pts = 0
    for event_type, entries in sorted(missing.items()):
        if event_type == 'unmatched':
            continue
        pts_each = {
            'journey': 1, 'extra_vote': 3, 'boomerang_received': 3,
            'advantage': 3, 'fake_idol': 2, 'twist': 3
        }.get(event_type, 0)
        total = len(entries) * pts_each
        missing_pts += total
        print(f'\n  {event_type} ({len(entries)} events, ~{total} pts total):')
        for e in entries:
            print(e)

    print(f'\n  Total missing points across all players: ~{missing_pts}')

    # TC totals by player
    tc_totals, tc_by_ep = summarize_tc_by_player(feed)

    print('\n── TC individual scoring by player (excl tribe events) ──')
    for name, total in sorted(tc_totals.items(), key=lambda x: -x[1]):
        by_ep_str = '  '.join(
            f'ep{ep}:{pts}' for ep, pts in sorted(tc_by_ep[name].items())
        )
        print(f'  {name:<25} {total:>4} pts    {by_ep_str}')

    # Our events summary
    print('\n── Our events.csv coverage gaps ──────────────────────────')
    our_fields = {
        'found_idol_clue':     ('gets_idol_clue', 1),
        'found_hidden_idol':   ('finds_hidden_idol', 3),
        'played_idol':         ('plays_idol_successfully', 6),
        'voted_out_holding_idol': ('voted_out_holding_idol', -6),
        'won_individual_reward': ('wins_individual_reward', 4),
        'medevac':             ('medical_removal', 8),
        'quit':                ('player_quits', -8),
        'lost_vote':           ('loses_vote', -3),
        'received_jury_vote':  ('jury_vote', 10),
        'sole_survivor':       ('sole_survivor', 20),
    }

    for ep_num in range(1, 7):
        ep_rows = [r for r in events if int(r['episode']) == ep_num]
        if not ep_rows:
            continue
        special = []
        for row in ep_rows:
            for field, (event_type, pts) in our_fields.items():
                if int(row.get(field, 0)) == 1:
                    special.append(f'{row["player_name"]} {event_type} {pts:+d}')
        if special:
            print(f'\n  Ep{ep_num} special events we DO score:')
            for s in special:
                print(f'    {s}')


if __name__ == '__main__':
    main()
