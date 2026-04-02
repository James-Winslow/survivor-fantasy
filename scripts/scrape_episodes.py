"""
scripts/scrape_episodes.py

Scrapes tribal-council.com episode pages to extract:
1. Per-manager roster (starters vs bench) for each episode
2. Scoring events for each episode (for events.csv validation)

Requires session cookies from your logged-in browser session.

Usage:
    python scripts/scrape_episodes.py

You will be prompted to paste your session cookies.
To get cookies:
    1. Go to tribal-council.com (logged in)
    2. Open DevTools → Application → Cookies → tribal-council.com
    3. Copy the values for: tribal_council_session, XSRF-TOKEN
"""

import requests
import json
import re
import csv
from pathlib import Path

# ── Episode URLs ──────────────────────────────────────────────────────────────

EPISODES = {
    1: 'https://tribal-council.com/episodes/b902d8e2-38cb-4af7-a4f2-b7ff1ec13074',
    2: 'https://tribal-council.com/episodes/60a6226b-2001-46ab-b400-e68e0cc5d842',
    3: 'https://tribal-council.com/episodes/94982834-0c48-4218-a12d-ddbcd2689935',
    4: 'https://tribal-council.com/episodes/b9def262-1aa0-43a9-9d4e-ef7c19b6901f',
    5: 'https://tribal-council.com/episodes/d98b0fec-8151-45d9-b47e-46b0cf51851c',
    6: 'https://tribal-council.com/episodes/current',
}

LEAGUES = {
    'FJV':   'd6875609-2dee-4d1f-b6e5-dff95e8ae63f',
    'Buffs': '5e332cfb-e13e-4c45-b117-49e25abe9cac',
}

STARTERS_CSV = Path('data/season50/starters.csv')
STARTERS_HEADER = ['episode', 'league', 'manager', 'player_name', 'player_uuid', 'is_starter']

ROSTERS_CSV = Path('data/season50/rosters.csv')

LEAGUE_NAMES = {
    'FJV':   'FJV Survivor Heads League',
    'Buffs': 'In the Buffs League',
}

# UUID → name from rosters.csv
def load_uuid_map():
    mapping = {}
    for row in csv.DictReader(ROSTERS_CSV.open(encoding='utf-8-sig')):
        prefix = row.get('contestant_uuid', '').replace('-', '')[:8]
        mapping[prefix] = row['contestant_name']
    return mapping


def get_cookies():
    print()
    print('── Cookie Setup ─────────────────────────────────────────────')
    print('1. Go to tribal-council.com (logged in)')
    print('2. Open DevTools (F12) → Application tab → Cookies → tribal-council.com')
    print('3. Find and copy these two cookie values:')
    print()
    session = input('  tribal_council_session value: ').strip()
    xsrf    = input('  XSRF-TOKEN value: ').strip()
    print()
    return {
        'tribal_council_session': session,
        'XSRF-TOKEN': xsrf,
    }


def fetch_page(url, cookies):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Referer': 'https://tribal-council.com/',
    }
    r = requests.get(url, cookies=cookies, headers=headers, timeout=15)
    return r.text if r.status_code == 200 else None


def extract_uuids_from_html(html):
    """Find all contestant UUIDs in page HTML."""
    pattern = r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
    return [m[:8] for m in re.findall(pattern, html)]


def extract_scores_from_html(html):
    """Extract scoring events from episode page."""
    scores = []
    # Look for scoring event patterns in the HTML
    # tribal-council.com renders events as list items with player name + points
    event_pattern = r'([A-Z][a-z]+ [A-Z][a-z]+).*?(\+|-)\s*(\d+)\s*points?'
    for m in re.finditer(event_pattern, html):
        scores.append({
            'player': m.group(1),
            'direction': m.group(2),
            'points': int(m.group(3)),
        })
    return scores


def extract_json_data(html):
    """Try to extract any embedded JSON data from the page."""
    # Look for JavaScript data objects
    patterns = [
        r'var\s+leagueData\s*=\s*({.*?});',
        r'var\s+rosterData\s*=\s*({.*?});',
        r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
        r'data-props="({.*?})"',
    ]
    for pattern in patterns:
        m = re.search(pattern, html, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                continue
    return None


def ensure_header():
    if not STARTERS_CSV.exists():
        with STARTERS_CSV.open('w', newline='', encoding='utf-8') as f:
            csv.DictWriter(f, fieldnames=STARTERS_HEADER).writeheader()


def main():
    uuid_map = load_uuid_map()
    ensure_header()

    cookies = get_cookies()

    # Test authentication
    print('Testing authentication...')
    test_html = fetch_page('https://tribal-council.com/league/d6875609-2dee-4d1f-b6e5-dff95e8ae63f', cookies)
    if not test_html or 'Log in' in test_html[:500]:
        print('ERROR: Not authenticated. Check your cookie values.')
        return
    print('  Authenticated successfully!')
    print()

    # Save raw HTML for inspection
    raw_dir = Path('data/season50/raw_html')
    raw_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    for ep_num, url in EPISODES.items():
        print(f'── Episode {ep_num} ──────────────────────────────────')
        html = fetch_page(url, cookies)
        if not html:
            print(f'  FAILED to fetch ep{ep_num}')
            continue

        # Save raw HTML for debugging
        raw_path = raw_dir / f'ep{ep_num}.html'
        raw_path.write_text(html, encoding='utf-8')
        print(f'  Saved raw HTML: {raw_path} ({len(html):,} chars)')

        # Try to extract JSON
        json_data = extract_json_data(html)
        if json_data:
            print(f'  Found embedded JSON data')
            results[ep_num] = {'json': json_data}

        # Extract all UUIDs
        uuids = extract_uuids_from_html(html)
        known = [u for u in uuids if u in uuid_map]
        print(f'  Found {len(known)} known contestant UUIDs: {known[:5]}...')

        # Extract scoring events
        scores = extract_scores_from_html(html)
        if scores:
            print(f'  Found {len(scores)} scoring events')
            for s in scores[:3]:
                print(f'    {s}')

        results[ep_num] = {
            'url': url,
            'html_length': len(html),
            'contestant_uuids': known,
            'scores': scores,
        }
        print()

    # Save results summary
    summary_path = Path('data/season50/scrape_results.json')
    summary_path.write_text(json.dumps(results, indent=2, default=str))
    print(f'Results saved to {summary_path}')
    print()
    print('Next step: check data/season50/raw_html/ to see what the pages look like')
    print('and we can refine the extraction logic.')


if __name__ == '__main__':
    main()
