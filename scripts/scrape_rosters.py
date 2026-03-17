"""
scrape_rosters.py

Scrapes tribal-council.com to build rosters.csv for the survivor-fantasy project.
Reads cookies directly from your logged-in Chrome browser — no manual paste needed.

Requirements:
    pip install requests beautifulsoup4 browser-cookie3

Usage:
    1. Make sure you are logged into tribal-council.com in Chrome
    2. Run: python scrape_rosters.py

Output: data/season50/rosters.csv
"""

import re
import csv
import time
from pathlib import Path

import requests
import browser_cookie3
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://tribal-council.com/",
}

BASE_URL = "https://tribal-council.com"

LEAGUE_URLS = {
    "In the Buffs League":       f"{BASE_URL}/league/5e332cfb-e13e-4c45-b117-49e25abe9cac",
    "FJV Survivor Heads League": f"{BASE_URL}/league/d6875609-2dee-4d1f-b6e5-dff95e8ae63f",
}

OUTPUT_PATH = Path("data/season50/rosters.csv")


# ── Auth: read cookies directly from Chrome ───────────────────────────────────
def get_session() -> requests.Session:
    print("Loading cookies from Chrome...")
    cookiejar = browser_cookie3.chrome(domain_name=".tribal-council.com")
    session = requests.Session()
    session.cookies.update(cookiejar)
    session.headers.update(HEADERS)

    # Verify auth works
    test = session.get(f"{BASE_URL}/contestants")
    if "login" in test.url:
        raise RuntimeError(
            "Not logged in — make sure you are logged into tribal-council.com in Chrome "
            "and that Chrome is fully closed or try running as the same user."
        )
    print("  Auth OK\n")
    return session


# ── Step 1: Collect all unique contestant UUIDs from both league pages ─────────
def collect_all_uuids(session: requests.Session) -> set[str]:
    all_uuids = set()
    for league_name, url in LEAGUE_URLS.items():
        print(f"  Scanning {league_name} for UUIDs...")
        response = session.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for div in soup.find_all("div", class_="contestant-avatar-img-inline"):
            onclick = div.get("onclick", "")
            uuid_match = re.search(r"/contestants/([a-f0-9\-]{36})", onclick)
            if uuid_match:
                all_uuids.add(uuid_match.group(1))
        time.sleep(0.3)
    print(f"  Found {len(all_uuids)} unique contestant UUIDs across all leagues")
    return all_uuids


# ── Step 2: Fetch each contestant page individually to get their name ──────────
def build_contestant_map(session: requests.Session, uuids: set[str]) -> dict[str, str]:
    contestant_map = {}
    total = len(uuids)
    for i, uuid in enumerate(sorted(uuids), 1):
        url = f"{BASE_URL}/contestants/{uuid}"
        response = session.get(url)

        if "login" in response.url:
            raise RuntimeError(f"Redirected to login fetching contestant {uuid}")

        soup = BeautifulSoup(response.text, "html.parser")

        name = None

        # Try content header title first
        for tag in ["h2", "h1", "h3"]:
            el = soup.find(tag, class_=re.compile(r"content-header-title|contestant"))
            if el:
                name = el.get_text(strip=True)
                break

        # Fallback: page <title> tag
        if not name:
            title_el = soup.find("title")
            if title_el:
                raw = title_el.get_text(strip=True)
                name = raw.split(" - ")[0].split(" | ")[0].strip()
                if name == "Tribal-Council":
                    name = None

        if name:
            name = re.sub(r"\s*Profile\s*$", "", name).strip()
            contestant_map[uuid] = name
            print(f"  [{i}/{total}] {uuid[:8]}... → {name}")
        else:
            print(f"  [{i}/{total}] {uuid[:8]}... → NAME NOT FOUND (saving debug file)")
            Path(f"debug_contestant_{uuid[:8]}.html").write_text(response.text, encoding="utf-8")

        time.sleep(0.3)

    print(f"\n  Resolved {len(contestant_map)}/{total} contestant names")
    return contestant_map


# ── Step 3: Parse a league page into manager → [contestant_uuids] ─────────────
def parse_league_page(session: requests.Session, league_name: str, url: str) -> list[dict]:
    print(f"Fetching {league_name} ...")
    response = session.get(url)
    response.raise_for_status()

    if "login" in response.url:
        raise RuntimeError(f"Redirected to login fetching {league_name}")

    soup = BeautifulSoup(response.text, "html.parser")

    rows = []
    for tr in soup.find_all("tr", class_="league-row"):

        # Manager name: first non-empty <a> pointing to /players/
        manager_name = "Unknown"
        for a in tr.find_all("a", href=True):
            if "/players/" in a["href"]:
                text = a.get_text(strip=True)
                if text:
                    manager_name = text
                    break

        # Points
        points = 0
        points_td = tr.find("td", style=re.compile(r"width:100%"))
        if points_td:
            points_match = re.search(r"(\d+)\s*Points", points_td.get_text())
            if points_match:
                points = int(points_match.group(1))

        # Contestant UUIDs from onclick attributes
        contestant_uuids = []
        for div in tr.find_all("div", class_="contestant-avatar-img-inline"):
            onclick = div.get("onclick", "")
            uuid_match = re.search(r"/contestants/([a-f0-9\-]{36})", onclick)
            if uuid_match:
                contestant_uuids.append(uuid_match.group(1))

        # Skip empty rows
        if not contestant_uuids:
            continue

        rows.append({
            "league": league_name,
            "manager": manager_name,
            "points": points,
            "contestant_uuids": contestant_uuids,
        })
        print(f"  {manager_name}: {len(contestant_uuids)} contestants, {points} pts")

    return rows


# ── Step 4: Resolve UUIDs to names and write rosters.csv ──────────────────────
def write_rosters_csv(
    all_league_rows: list[dict],
    contestant_map: dict[str, str],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["league", "manager", "contestant_name", "contestant_uuid"])

        for row in all_league_rows:
            for uuid in row["contestant_uuids"]:
                name = contestant_map.get(uuid, f"UNKNOWN_{uuid[:8]}")
                writer.writerow([row["league"], row["manager"], name, uuid])

    print(f"\nWrote {output_path}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    session = get_session()

    print("Collecting contestant UUIDs from league pages...")
    all_uuids = collect_all_uuids(session)

    print("\nFetching individual contestant pages to resolve names...")
    contestant_map = build_contestant_map(session, all_uuids)

    print("\nParsing league rosters...")
    all_rows = []
    for league_name, url in LEAGUE_URLS.items():
        rows = parse_league_page(session, league_name, url)
        all_rows.extend(rows)
        time.sleep(0.5)

    write_rosters_csv(all_rows, contestant_map, OUTPUT_PATH)

    print("\n── Summary ──────────────────────────────────────────")
    for row in all_rows:
        resolved = [contestant_map.get(u, f"UNKNOWN_{u[:8]}") for u in row["contestant_uuids"]]
        print(f"  [{row['league']}] {row['manager']}: {', '.join(resolved)}")

    unknown_count = sum(
        1 for row in all_rows
        for u in row["contestant_uuids"]
        if u not in contestant_map
    )
    if unknown_count > 0:
        print(f"\n  WARNING: {unknown_count} UUIDs could not be resolved to names.")


if __name__ == "__main__":
    main()
