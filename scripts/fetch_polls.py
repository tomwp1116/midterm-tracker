"""
Fetch 2026 midterm election polling data from Wikipedia articles.

Wikipedia hosts polling tables for major election races. We use the
MediaWiki API to fetch article HTML and parse wikitables.

API: https://en.wikipedia.org/w/api.php
Bot policy: https://en.wikipedia.org/wiki/Wikipedia:Bot_policy
User-Agent: per Wikimedia policy, must identify project + contact URL.

STRATEGY:
  1. For each tracked Senate/Governor race, compute the expected Wikipedia
     article title (e.g. "2026 United States Senate election in Georgia")
  2. Fetch parsed HTML via the MediaWiki action=parse API
  3. Find wikitables whose headers look like polling tables
  4. Identify D/R columns by background-color CSS on header cells (most
     reliable signal) with a text-label fallback
  5. Parse each data row into a canonical poll record
"""
import re
import sys
import time
import requests
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    WIKIPEDIA_API, WIKIPEDIA_USER_AGENT,
    SENATE_STATES_2026, GOVERNOR_STATES_2026,
    REQUEST_TIMEOUT,
)

HEADERS = {"User-Agent": WIKIPEDIA_USER_AGENT}

STATE_NAMES = {
    "AL": "Alabama",       "AK": "Alaska",        "AZ": "Arizona",
    "AR": "Arkansas",      "CA": "California",    "CO": "Colorado",
    "CT": "Connecticut",   "DE": "Delaware",      "FL": "Florida",
    "GA": "Georgia",       "HI": "Hawaii",        "ID": "Idaho",
    "IL": "Illinois",      "IN": "Indiana",       "IA": "Iowa",
    "KS": "Kansas",        "KY": "Kentucky",      "LA": "Louisiana",
    "ME": "Maine",         "MD": "Maryland",      "MA": "Massachusetts",
    "MI": "Michigan",      "MN": "Minnesota",     "MS": "Mississippi",
    "MO": "Missouri",      "MT": "Montana",       "NE": "Nebraska",
    "NV": "Nevada",        "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico",    "NY": "New York",      "NC": "North Carolina",
    "ND": "North Dakota",  "OH": "Ohio",          "OK": "Oklahoma",
    "OR": "Oregon",        "PA": "Pennsylvania",  "RI": "Rhode Island",
    "SC": "South Carolina","SD": "South Dakota",  "TN": "Tennessee",
    "TX": "Texas",         "UT": "Utah",          "VT": "Vermont",
    "VA": "Virginia",      "WA": "Washington",    "WV": "West Virginia",
    "WI": "Wisconsin",     "WY": "Wyoming",
}

# Wikipedia background colors that indicate party columns.
# Sorted by specificity — hex codes first, named colors last.
_DEM_COLORS = {
    "#3333ff", "#0000ff", "#003399", "#0047ab", "#0000cd", "#0000dc",
    "#00008b", "#3030ff", "#3366cc", "#6699ff", "#99b3ff", "#5555ff",
    "#4169e1", "#0d3b7d", "#1b3a8c", "blue",
}
_REP_COLORS = {
    "#ff0000", "#cc0000", "#ff3333", "#dd0000", "#cc3333", "#b22222",
    "#8b0000", "#dc143c", "#ff6666", "#e81b23", "#c0392b", "#e74c3c",
    "#bf0a30", "red",
}


# ── Article title helpers ──────────────────────────────────────────────────────

def _article_info(race_id):
    """
    Return (wikipedia_title, article_url) for a race_id, or None if unmappable.
    Handles senate-{STATE}-2026 and governor-{STATE}-2026.
    """
    parts = race_id.split("-")
    chamber = parts[0]
    state = parts[1] if len(parts) > 1 else None
    if not state or state not in STATE_NAMES:
        return None
    name = STATE_NAMES[state]

    if chamber == "senate":
        title = f"2026 United States Senate election in {name}"
    elif chamber == "governor":
        title = f"2026 {name} gubernatorial election"
    else:
        return None

    url = "https://en.wikipedia.org/wiki/" + title.replace(" ", "_")
    return title, url


# ── Wikipedia API fetch ────────────────────────────────────────────────────────

def _fetch_html(title):
    """
    Fetch parsed HTML for a Wikipedia article via the MediaWiki action=parse
    endpoint. Returns HTML string or None (404 / missing article / network err).
    """
    params = {
        "action": "parse",
        "page": title,
        "prop": "text",
        "format": "json",
        "disableeditsection": "1",
        "redirects": "1",
    }
    try:
        resp = requests.get(
            WIKIPEDIA_API, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            return None   # article doesn't exist yet
        return data["parse"]["text"]["*"]
    except Exception as e:
        print(f"  [Wiki] Error fetching '{title}': {e}")
        return None


# ── Column-party detection ─────────────────────────────────────────────────────

def _col_party(th_tag, header_text):
    """
    Return 'D', 'R', or None for a <th> cell.
    Primary signal: background-color CSS value.
    Fallback: party keywords in the header text.
    """
    style = (th_tag.get("style") or "").lower()
    bg_match = re.search(r"background(?:-color)?:\s*([#\w]+)", style)
    if bg_match:
        color = bg_match.group(1).lower()
        if color in _DEM_COLORS:
            return "D"
        if color in _REP_COLORS:
            return "R"

    t = header_text.lower()
    if any(kw in t for kw in ("democrat", "(d)", " dem", "dem.")):
        return "D"
    if any(kw in t for kw in ("republican", "(r)", " rep", "rep.", "gop")):
        return "R"
    return None


# ── Date / number parsers ──────────────────────────────────────────────────────

def _parse_date(s):
    """
    Parse Wikipedia date strings to YYYY-MM-DD (end date of ranges).
    Handles: "January 5–10, 2026", "Jan 5–10, 2026", "January 5, 2026",
             "2026-01-05", "March 1–5, 2026", etc.
    Returns None on failure.
    """
    if not s:
        return None
    s = re.sub(r"\[.*?\]", "", s).strip()   # strip citation markers
    s = re.sub(r"\s+", " ", s)

    if re.match(r"\d{4}-\d{2}-\d{2}", s):
        return s[:10]

    year_m = re.search(r"\b(202\d)\b", s)
    year = year_m.group(1) if year_m else "2026"

    # End of range (e.g. "5–10" → 10) or single day
    end_day_m = re.search(r"[–\-]\s*(\d{1,2})\s*,?\s*" + year, s)
    if end_day_m:
        day = end_day_m.group(1).zfill(2)
    else:
        day_m = re.search(r"(\d{1,2})\s*,?\s*" + year, s)
        day = day_m.group(1).zfill(2) if day_m else None

    if not day:
        return None

    months = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "may": "05", "jun": "06", "jul": "07", "aug": "08",
        "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    }
    month = next(
        (num for abbr, num in months.items() if re.search(abbr, s, re.I)),
        None
    )
    if not month:
        return None

    return f"{year}-{month}-{day}"


def _parse_sample(s):
    """'800 LV', '1,200', 'N/A' → int or None."""
    if not s:
        return None
    m = re.search(r"\d[\d,]*", s.replace(",", ""))
    if m:
        n = int(m.group().replace(",", ""))
        return n if n > 0 else None
    return None


def _parse_pct(s):
    """'52.3', '52.3%', '–', 'N/A' → float or None."""
    if not s:
        return None
    s = s.strip().replace("%", "")
    if s in ("–", "-", "N/A", "na", "n/a", "*", ""):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _cell_text(cells, idx):
    if idx is None or idx >= len(cells):
        return ""
    raw = cells[idx].get_text(" ", strip=True)
    # Strip Wikipedia citation/footnote markers: [1], [A], [note 2], etc.
    raw = re.sub(r"\s*\[[^\]]{1,10}\]", "", raw).strip()
    return raw


# ── Table parser ───────────────────────────────────────────────────────────────

def _parse_table(table, race_id, article_url):
    """
    Parse one wikitable. Returns list of poll record dicts, or [] if the
    table doesn't look like a polling table or lacks D/R columns.
    """
    rows = table.find_all("tr")
    if not rows:
        return []

    # Collect header rows (rows where ≥ half the cells are <th>)
    header_rows = []
    for row in rows[:4]:
        ths = row.find_all("th")
        tds = row.find_all("td")
        if ths and len(ths) >= len(tds):
            header_rows.append(ths)

    if not header_rows:
        return []

    # Use the last header row for column mapping (handles multi-row headers)
    col_ths = header_rows[-1]
    col_texts = [
        re.sub(r"\s*\[[^\]]{1,10}\]", "", th.get_text(" ", strip=True)).strip()
        for th in col_ths
    ]

    # Must look like a polling table
    lower_texts = [t.lower() for t in col_texts]
    if not any(kw in t for t in lower_texts for kw in ("poll", "firm", "source", "survey")):
        if not any(kw in t for t in lower_texts for kw in ("date", "field", "conduct")):
            return []

    # --- Map column indices ---
    pollster_col = date_col = sample_col = dem_col = rep_col = None

    for i, (th, text) in enumerate(zip(col_ths, col_texts)):
        t = text.lower()
        party = _col_party(th, text)

        if party == "D" and dem_col is None:
            dem_col = i
        elif party == "R" and rep_col is None:
            rep_col = i
        elif pollster_col is None and any(
            kw in t for kw in ("poll", "firm", "source", "survey", "organization")
        ):
            pollster_col = i
        elif date_col is None and any(
            kw in t for kw in ("date", "field", "conduct", "period")
        ):
            date_col = i
        elif sample_col is None and any(
            kw in t for kw in ("sample", "size", "n=", "respondent")
        ):
            sample_col = i

    # Text-based party fallback (if color detection missed)
    if dem_col is None or rep_col is None:
        for i, text in enumerate(col_texts):
            t = text.lower()
            if dem_col is None and any(kw in t for kw in ("dem", "democratic", "(d)")):
                dem_col = i
            if rep_col is None and any(kw in t for kw in ("rep", "republican", "(r)", "gop")):
                rep_col = i

    if dem_col is None and rep_col is None:
        return []

    dem_name = col_texts[dem_col] if dem_col is not None else "Democratic"
    rep_name = col_texts[rep_col] if rep_col is not None else "Republican"

    # --- Parse data rows ---
    polls = []
    for row in rows:
        cells = row.find_all(["td", "th"])
        # Skip pure header rows
        if not row.find("td"):
            continue

        n_cols = max(filter(None, [pollster_col, date_col, sample_col, dem_col, rep_col, 0]))
        if len(cells) <= n_cols:
            continue

        pollster  = _cell_text(cells, pollster_col) or "Unknown"
        poll_date = _parse_date(_cell_text(cells, date_col))
        sample    = _parse_sample(_cell_text(cells, sample_col)) if sample_col is not None else None
        dem_pct   = _parse_pct(_cell_text(cells, dem_col)) if dem_col is not None else None
        rep_pct   = _parse_pct(_cell_text(cells, rep_col)) if rep_col is not None else None

        if dem_pct is None and rep_pct is None:
            continue

        # Skip aggregate/average rows Wikipedia sometimes includes
        if re.search(r"\baverage\b|\baggregate\b", pollster.lower()):
            continue

        spread = round(dem_pct - rep_pct, 1) if (dem_pct is not None and rep_pct is not None) else None
        if spread is not None:
            lead = dem_name.split()[-1] if spread >= 0 else rep_name.split()[-1]
            spread_label = f"{lead} +{abs(spread)}"
        else:
            spread_label = None

        polls.append({
            "race_id":          race_id,
            "poll_date":        poll_date,
            "pollster":         pollster,
            "sample_size":      sample,
            "candidate_1":      dem_name,
            "candidate_1_pct":  dem_pct,
            "candidate_2":      rep_name,
            "candidate_2_pct":  rep_pct,
            "candidate_3":      None,
            "candidate_3_pct":  None,
            "spread":           spread,
            "spread_label":     spread_label,
            "source_url":       article_url,
            "rcp_url":          None,
            "fte_grade":        None,
            "population":       None,
            "stage":            "general",
        })

    return polls


# ── Per-race fetcher ───────────────────────────────────────────────────────────

def fetch_polls_for_race(race_id):
    """Fetch and parse all polling tables for one race. Returns list of polls."""
    info = _article_info(race_id)
    if info is None:
        return []
    title, url = info

    html = _fetch_html(title)
    if html is None:
        return []

    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table", class_=re.compile(r"wikitable"))

    polls = []
    for table in tables:
        polls.extend(_parse_table(table, race_id, url))

    # Deduplicate by (pollster, poll_date)
    seen, unique = set(), []
    for p in polls:
        key = (p["pollster"], p["poll_date"])
        if key not in seen:
            seen.add(key)
            unique.append(p)

    return unique


# ── Main entry point ───────────────────────────────────────────────────────────

def fetch_all_polls():
    """
    Main entry point — same API as the old FiveThirtyEight fetcher.
    Returns (polls_list, raw_rows) where raw_rows is [] (no separate archive).
    """
    print("[Wikipedia] Fetching 2026 election polls...")

    race_ids = (
        [f"senate-{s}-2026"   for s in SENATE_STATES_2026] +
        [f"governor-{s}-2026" for s in GOVERNOR_STATES_2026]
    )

    all_polls = []
    found = 0
    for race_id in race_ids:
        polls = fetch_polls_for_race(race_id)
        if polls:
            all_polls.extend(polls)
            found += 1
            print(f"  {race_id}: {len(polls)} polls")
        time.sleep(0.5)   # polite delay between API calls

    print(f"  Done: {len(all_polls)} polls from {found}/{len(race_ids)} races")
    return all_polls, []


if __name__ == "__main__":
    polls, _ = fetch_all_polls()
    for p in polls[:20]:
        print(
            f"  {p['poll_date']}  {p['race_id']:32s}  {p['pollster']:25s}  "
            f"D:{p['candidate_1_pct']}  R:{p['candidate_2_pct']}  "
            f"n={p['sample_size']}"
        )
    print(f"\nTotal: {len(polls)} polls")
