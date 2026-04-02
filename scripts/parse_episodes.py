"""
scripts/parse_episodes.py

Parses downloaded raw HTML to extract scoring events and portrait URLs.

Usage:
    python scripts/parse_episodes.py
"""

import csv
import re
from pathlib import Path

RAW_DIR      = Path('data/season50/raw_html')
FEED_CSV     = Path('data/season50/episode_feed.csv')
PORTRAIT_CSV = Path('data/season50/portrait_urls.csv')
FEED_HEADER  = ['episode', 'player_uuid', 'player_name', 'event_text', 'points', 'is_tribe_event']

CONTESTANT_UUID_MAP = {
    '8646857f': 'Benjamin Wade',        'c5d0e6ea': 'Oscar Lusth',
    'c0e1bafb': 'Q Burdette',          '8682d041': 'Genevieve Mushaluk',
    '20b068a6': 'Mike White',          '12e3e212': 'Colby Donaldson',
    '57b968cf': 'Savannah Louie',      '1e8e16fa': 'Christian Hubicki',
    'f02b7a71': 'Aubry Bracco',        '3ba2b294': 'Rick Devens',
    '042ee802': 'Rizo Velovic',        'd794dd7f': 'Jonathan Young',
    '24577db8': 'Dee Valladares',      '3376a067': 'Cirie Fields',
    'ab8ea829': 'Charlie Davis',       '1a580ce6': 'Emily Flippen',
    'bbf825b0': 'Kamilla Karthigesu',  'ff3e1c53': 'Joe Hunter',
    '25bb2e7a': 'Stephenie LaGrossa',  '74a71cac': 'Chrissy Hofbeck',
    '81b746c1': 'Tiffany Nicole Ervin','00902f8a': 'Angelina Keeley',
    '17880c85': 'Jenna Lewis',         'fbced418': 'Kyle Fraser',
}

def parse_episode(html, ep_num):
    events   = []
    portraits = {}

    # Split on feed-item boundaries — each starts with <div class="feed-item
    blocks = re.split(r'(?=<div class="feed-item)', html)

    for block in blocks:
        if 'feed-item' not in block:
            continue

        # Extract contestant UUID from onclick
        contestant_uuid = None
        m = re.search(
            r"onclick=\"location\.href='https://tribal-council\.com/contestants/([a-f0-9-]{36})'\"",
            block
        )
        if m:
            contestant_uuid = m.group(1)[:8]

        # Extract portrait image URL
        img_m = re.search(r'src="/uploads/contestants/([a-f0-9-]{36})\.jpg"', block)
        if img_m and contestant_uuid:
            portraits[contestant_uuid] = (
                f"https://tribal-council.com/uploads/contestants/{img_m.group(1)}.jpg"
            )

        # Extract text from feed-subject
        subj_m = re.search(r'<div class="feed-subject">\s*<p>(.*?)</p>', block, re.DOTALL)
        if not subj_m:
            continue

        raw = subj_m.group(1)
        # Strip HTML tags and normalize whitespace
        text = re.sub(r'<[^>]+>', ' ', raw)
        text = re.sub(r'\s+', ' ', text).strip()

        # Skip non-scoring entries
        if any(skip in text for skip in ['MOVED Out Of Game', 'MOVED TO', 'GAME UPDATE']):
            continue

        # Extract points
        pts_m = re.search(r'\((\d+)\s*points?\)', text)
        points = int(pts_m.group(1)) if pts_m else 0

        # Clean event text
        event_text = re.sub(r'\(\d+\s*points?\)', '', text).strip()
        event_text = re.sub(r'\s+', ' ', event_text)

        if not event_text or points == 0:
            continue

        is_tribe = contestant_uuid is None and 'Tribe' in event_text
        player_name = CONTESTANT_UUID_MAP.get(contestant_uuid, '') if contestant_uuid else ''

        events.append({
            'episode':        ep_num,
            'player_uuid':    contestant_uuid or '',
            'player_name':    player_name,
            'event_text':     event_text,
            'points':         points,
            'is_tribe_event': '1' if is_tribe else '0',
        })

    return events, portraits


def main():
    all_events   = []
    all_portraits = {}

    for ep_num in range(1, 7):
        path = RAW_DIR / f'ep{ep_num}.html'
        if not path.exists():
            print(f'  MISSING: ep{ep_num}.html')
            continue

        html   = path.read_text(encoding='utf-8', errors='replace')
        events, portraits = parse_episode(html, ep_num)
        all_events.extend(events)
        all_portraits.update(portraits)

        print(f'\nEp{ep_num}: {len(events)} events, {len(portraits)} portraits')
        for e in events:
            name = e['player_name'] or '[tribe/game]'
            print(f'  {name:<25} {e["event_text"][:55]:<55} +{e["points"]}')

    # Write feed CSV
    with FEED_CSV.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FEED_HEADER)
        writer.writeheader()
        writer.writerows(all_events)
    print(f'\nWrote {len(all_events)} events to {FEED_CSV}')

    # Write portrait URLs
    with PORTRAIT_CSV.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['contestant_uuid','player_name','image_url'])
        writer.writeheader()
        for uuid, url in sorted(all_portraits.items()):
            writer.writerow({
                'contestant_uuid': uuid,
                'player_name':     CONTESTANT_UUID_MAP.get(uuid, ''),
                'image_url':       url,
            })
    print(f'Wrote {len(all_portraits)} portrait URLs to {PORTRAIT_CSV}')


if __name__ == '__main__':
    main()
