"""
scripts/download_portraits.py

Downloads contestant portraits using the correct image URLs
discovered by parse_episodes.py.

Usage:
    python scripts/download_portraits.py
"""

import csv
import requests
import time
from pathlib import Path

PORTRAIT_CSV  = Path('data/season50/portrait_urls.csv')
PORTRAITS_DIR = Path('data/season50/portraits')


def main():
    if not PORTRAIT_CSV.exists():
        print(f'ERROR: {PORTRAIT_CSV} not found — run parse_episodes.py first')
        return

    PORTRAITS_DIR.mkdir(parents=True, exist_ok=True)

    rows = list(csv.DictReader(PORTRAIT_CSV.open(encoding='utf-8')))
    print(f'Downloading {len(rows)} portraits...')

    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0'
    session.headers['Referer']    = 'https://tribal-council.com/'

    ok = fail = 0
    for row in rows:
        name = row['player_name'].replace(' ', '_').replace('"', '')
        uuid = row['contestant_uuid']
        url  = row['image_url']
        path = PORTRAITS_DIR / f'{name}_{uuid}.jpg'

        if path.exists():
            print(f'  skip  {path.name}')
            ok += 1
            continue

        try:
            r = session.get(url, timeout=10)
            if r.status_code == 200 and len(r.content) > 1000:
                path.write_bytes(r.content)
                print(f'  OK    {path.name} ({len(r.content):,} bytes)')
                ok += 1
            else:
                print(f'  FAIL  {path.name} status={r.status_code}')
                fail += 1
        except Exception as e:
            print(f'  ERROR {path.name}: {e}')
            fail += 1
        time.sleep(0.3)

    print(f'\nDone: {ok} OK, {fail} failed')
    print(f'Portraits at: {PORTRAITS_DIR.absolute()}')


if __name__ == '__main__':
    main()
