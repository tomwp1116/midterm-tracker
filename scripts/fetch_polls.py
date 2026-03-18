"""
Fetch 2026 midterm polls from FiveThirtyEight's public CSV data.

FiveThirtyEight publishes continuously-updated CSV files (no auth required):
  Senate:   https://projects.fivethirtyeight.com/polls-page/data/senate_polls.csv
  House:    https://projects.fivethirtyeight.com/polls-page/data/house_polls.csv
  Governor: https://projects.fivethirtyeight.com/polls-page/data/governor_polls.csv

Each CSV has one row per candidate per poll. We group by poll_id, filter for
cycle==2026, and pivot into our canonical poll record format.

Extra fields provided by 538 that RCP did not have:
  - sample_size: number of respondents
  - fte_grade: pollster quality grade (A+, A, B, etc.)
  - population: lv (likely voters), rv (registered voters), a (all adults)
  - stage: 'general' or 'primary' — drives race_id suffix for primaries
"""
import csv
import io
import time
import requests
from datetime import datetime, date
from config import USER_AGENT, REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT

HEADERS = {"User-Agent": USER_AGENT}

FTE_BASE = "https://projects.fivethirtyeight.com/polls-page/data"
FTE_URLS = {
    "senate":   f"{FTE_BASE}/senate_polls.csv",
    "house":    f"{FTE_BASE}/house_polls.csv",
    "governor": f"{FTE_BASE}/governor_polls.csv",
}


def parse_fte_date(date_str):
    """Convert 538 date format (MM/DD/YY or MM/DD/YYYY) to YYYY-MM-DD."""
    if not date_str:
        return None
    date_str = date_str.strip()
    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def build_race_id(chamber, state, seat_number, stage, parties):
    """
    Build canonical race_id from 538 fields.

    For general elections: {chamber}-{STATE}-{year} or {chamber}-{STATE}-{district}-{year}
    For primaries:         primary-{STATE}-{chamber}-{party}-{year}
                           or primary-{STATE}-{chamber}-{district}-{party}-{year} (House)

    chamber:     'senate', 'house', or 'governor'
    state:       two-letter state code (already uppercase from 538)
    seat_number: congressional district number for House; None otherwise
    stage:       'general' or 'primary'
    parties:     set of candidate party codes in this poll (e.g. {'DEM', 'REP'})
    """
    state = state.upper()

    if stage and stage.lower() == "primary":
        has_dem = bool(parties & {"DEM", "D", "DEMOCRATIC"})
        has_rep = bool(parties & {"REP", "R", "REPUBLICAN"})
        if has_dem and not has_rep:
            party_suffix = "D"
        elif has_rep and not has_dem:
            party_suffix = "R"
        else:
            # Mixed-party primary poll — treat as general
            party_suffix = None

        if party_suffix:
            if chamber == "house" and seat_number:
                return f"primary-{state}-{chamber}-{seat_number}-{party_suffix}-2026"
            return f"primary-{state}-{chamber}-{party_suffix}-2026"

    # General election
    if chamber == "house" and seat_number:
        return f"house-{state}-{seat_number}-2026"
    return f"{chamber}-{state}-2026"


def fetch_csv(url):
    """Download a 538 CSV and return as a list of dicts."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        reader = csv.DictReader(io.StringIO(resp.text))
        return list(reader)
    except Exception as e:
        print(f"  [538] Error fetching {url}: {e}")
        return []


def rows_to_polls(rows, chamber):
    """
    Convert 538 CSV rows (one row per candidate) into poll records
    (one record per poll), pivoting candidates into candidate_1/2/3 fields.

    Only includes polls where cycle == 2026.
    Candidates are ordered: DEM first, then REP, then others (by pct desc within group).
    """
    # Group rows by poll_id
    by_poll = {}
    for row in rows:
        if row.get("cycle", "").strip() != "2026":
            continue
        pid = row.get("poll_id", "").strip()
        if not pid:
            continue
        if pid not in by_poll:
            by_poll[pid] = {"meta": row, "candidates": []}

        party = row.get("candidate_party", "").strip().upper()
        name = row.get("candidate_name", "").strip()
        pct_str = row.get("pct", "").strip()
        try:
            pct = float(pct_str) if pct_str else None
        except ValueError:
            pct = None

        if name or pct is not None:
            by_poll[pid]["candidates"].append({"name": name, "party": party, "pct": pct})

    polls = []
    for pid, data in by_poll.items():
        meta = data["meta"]
        candidates = data["candidates"]

        state = meta.get("state", "").strip().upper()
        if not state or state == "US":
            continue

        seat_number = meta.get("seat_number", "").strip() or None
        stage = meta.get("stage", "general").strip().lower()
        parties = {c["party"] for c in candidates}

        race_id = build_race_id(chamber, state, seat_number, stage, parties)

        poll_date = parse_fte_date(meta.get("end_date"))
        if not poll_date:
            continue

        # Sort: DEM first, REP second, others by pct desc
        def sort_key(c):
            order = {"DEM": 0, "REP": 1}.get(c["party"], 2)
            return (order, -(c["pct"] or 0))

        candidates_sorted = sorted(candidates, key=sort_key)

        # Deduplicate by name (538 sometimes repeats candidates across sub-questions)
        seen_names = set()
        unique_candidates = []
        for c in candidates_sorted:
            if c["name"] not in seen_names:
                seen_names.add(c["name"])
                unique_candidates.append(c)

        c1 = unique_candidates[0] if len(unique_candidates) > 0 else {}
        c2 = unique_candidates[1] if len(unique_candidates) > 1 else {}
        c3 = unique_candidates[2] if len(unique_candidates) > 2 else {}

        spread = None
        spread_label = None
        if c1.get("pct") is not None and c2.get("pct") is not None:
            spread = round(c1["pct"] - c2["pct"], 1)
            winner = c1 if spread >= 0 else c2
            loser_pct = abs(spread)
            last_name = winner.get("name", "").split()[-1] if winner.get("name") else ""
            spread_label = f"{last_name} +{loser_pct}" if last_name else None

        sample_size = None
        try:
            ss = meta.get("sample_size", "").strip()
            if ss:
                sample_size = int(float(ss))
        except (ValueError, TypeError):
            pass

        polls.append({
            "race_id": race_id,
            "poll_date": poll_date,
            "pollster": meta.get("pollster", "Unknown").strip(),
            "sample_size": sample_size,
            "candidate_1": c1.get("name"),
            "candidate_1_pct": c1.get("pct"),
            "candidate_2": c2.get("name"),
            "candidate_2_pct": c2.get("pct"),
            "candidate_3": c3.get("name"),
            "candidate_3_pct": c3.get("pct"),
            "spread": spread,
            "spread_label": spread_label,
            "source_url": meta.get("url", "").strip() or None,
            "rcp_url": None,  # no longer sourced from RCP
            "fte_grade": meta.get("fte_grade", "").strip() or None,
            "population": meta.get("population", "").strip() or None,
            "stage": stage,
        })

    return polls


def fetch_all_polls():
    """
    Main entry point: fetch all 2026 polls from FiveThirtyEight CSVs.
    Returns (polls_list, raw_rows_for_archive).
    """
    print("[FiveThirtyEight] Fetching 2026 election polls...")
    all_polls = []
    all_raw_rows = []

    for chamber, url in FTE_URLS.items():
        print(f"  Fetching {chamber} polls from {url}...")
        rows = fetch_csv(url)
        if rows:
            rows_2026 = [r for r in rows if r.get("cycle", "").strip() == "2026"]
            all_raw_rows.extend(rows_2026)
            polls = rows_to_polls(rows, chamber)
            all_polls.extend(polls)
            print(f"    Found {len(polls)} polls ({len(rows_2026)} raw 2026 rows)")
        time.sleep(REQUEST_DELAY_SECONDS)

    # Deduplicate by (race_id, pollster, poll_date)
    seen = set()
    unique_polls = []
    for p in all_polls:
        key = (p["race_id"], p["pollster"], p["poll_date"])
        if key not in seen:
            seen.add(key)
            unique_polls.append(p)

    print(f"  Total unique polls: {len(unique_polls)}")
    return unique_polls, all_raw_rows


if __name__ == "__main__":
    polls, raw = fetch_all_polls()
    for p in polls[:10]:
        grade = f"[{p['fte_grade']}]" if p.get("fte_grade") else ""
        pop = p.get("population", "")
        n = f"n={p['sample_size']}" if p.get("sample_size") else ""
        print(
            f"  {p['poll_date']}  {p['race_id']:32s}  {p['pollster']:25s}  "
            f"{p.get('candidate_1','?')} {p.get('candidate_1_pct','')} vs "
            f"{p.get('candidate_2','?')} {p.get('candidate_2_pct','')}  "
            f"{grade} {pop} {n}".strip()
        )
